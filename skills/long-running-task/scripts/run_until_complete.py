"""Start a state-driven Codex long-run supervisor until done or blocked.

This wrapper now supports:
1) explicit fallback resolution when `longrun_supervisor` is unavailable, and
2) optional automatic ServerChan notification when the run stops.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


NOTIFY_DEFAULT_TITLE = "长任务已停止，等待验收"
NOTIFY_DEFAULT_SHORT = "Codex 长任务需要人工查看"
NOTIFY_DEFAULT_TIMEOUT = 10
TERMINAL_PHASE_STATUSES = {"done", "blocked"}


class RunFailure(RuntimeError):
    def __init__(self, message: str, *, details: Any | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": False, "error": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path("."))
    parser.add_argument("--objective", default="", help="Objective used when state must be initialized.")
    parser.add_argument("--force-init", action="store_true", help="Reinitialize .codex-longrun state before running.")
    parser.add_argument("--detach", action="store_true", help="Start supervisor in the background and return immediately.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--codex-bin", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--sandbox", default="workspace-write")
    parser.add_argument("--full-auto", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dangerously-bypass-approvals-and-sandbox", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=999999)
    parser.add_argument("--max-runtime-seconds", type=int, default=0)
    parser.add_argument("--per-run-timeout-seconds", type=int, default=1800)
    parser.add_argument("--max-stagnant-runs", type=int, default=999999)
    parser.add_argument("--skip-doctor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--supervisor-script",
        default=os.environ.get("LONGRUN_SUPERVISOR_PY", "").strip(),
        help="Optional path to supervisor.py when the longrun_supervisor module is not installed.",
    )
    parser.add_argument("--notify-on-exit", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--notify-script", default=str(Path(__file__).resolve().with_name("notify_serverchan.py")))
    parser.add_argument("--notify-title", default=NOTIFY_DEFAULT_TITLE)
    parser.add_argument("--notify-short", default=NOTIFY_DEFAULT_SHORT)
    parser.add_argument("--notify-timeout", type=int, default=NOTIFY_DEFAULT_TIMEOUT)
    parser.add_argument("--notify-message", default="")
    parser.add_argument("--notify-dry-run", action="store_true")
    parser.add_argument("--detached-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    project = args.project.resolve()
    if not project.exists():
        payload = {"ok": False, "error": f"project does not exist: {project}"}
        print_json(payload)
        return 1

    try:
        supervisor_invocation = resolve_supervisor_invocation(args.python, project, args.supervisor_script)

        if args.dry_run:
            command = build_run_command(args, project, supervisor_invocation)
            print_json(
                {
                    "ok": True,
                    "mode": "dry_run",
                    "command": command,
                    "supervisor_invocation": supervisor_invocation,
                }
            )
            return 0

        if args.detach and not args.detached_worker:
            worker_command = build_detached_worker_command(args, project)
            payload = start_detached(
                worker_command,
                project,
                status_command=build_supervisor_command(supervisor_invocation, project, "status"),
                report_command=build_supervisor_command(supervisor_invocation, project, "report"),
            )
            print_json(payload)
            return 0

        return run_foreground(args, project, supervisor_invocation)
    except RunFailure as exc:
        payload = exc.to_payload()
        payload["mode"] = "detached_worker" if args.detached_worker else "foreground"
        state_after = load_state(project) or {}
        status = resolve_notification_status(state_after, returncode=1)
        summary = args.notify_message.strip() or default_notify_message(
            project=project,
            returncode=1,
            state=state_after,
            note=exc.message,
        )
        payload["notification"] = maybe_send_notification(
            args=args,
            project=project,
            status=status,
            summary=summary,
        )
        print_json(payload)
        return 1


def run_foreground(args: argparse.Namespace, project: Path, supervisor_invocation: list[str]) -> int:
    state_before = load_state(project)
    needs_init = args.force_init or state_before is None or str(state_before.get("phase_status") or "") in TERMINAL_PHASE_STATUSES
    if needs_init:
        if not args.objective.strip():
            raise RunFailure("--objective is required when state is missing, done, blocked, or --force-init is used")
        run_checked(
            build_supervisor_command(
                supervisor_invocation,
                project,
                "init",
                ["--objective", args.objective, "--force"],
            ),
            cwd=project,
        )

    if not args.skip_doctor:
        doctor = run_capture(build_supervisor_command(supervisor_invocation, project, "doctor"), cwd=project)
        if doctor.returncode != 0:
            raise RunFailure("longrun_supervisor doctor failed", details=process_details(doctor))

    validate = run_capture(build_supervisor_command(supervisor_invocation, project, "validate"), cwd=project)
    if validate.returncode != 0:
        raise RunFailure("longrun state validation failed", details=process_details(validate))

    command = build_run_command(args, project, supervisor_invocation)
    completed = run_capture(command, cwd=project)
    state_after = load_state(project) or {}
    status = resolve_notification_status(state_after, returncode=completed.returncode)
    summary = args.notify_message.strip() or default_notify_message(project=project, returncode=completed.returncode, state=state_after)
    notification = maybe_send_notification(args=args, project=project, status=status, summary=summary)

    payload = {
        "ok": completed.returncode == 0,
        "mode": "detached_worker" if args.detached_worker else "foreground",
        "returncode": completed.returncode,
        "command": command,
        "supervisor_invocation": supervisor_invocation,
        "stdout_tail": tail(completed.stdout),
        "stderr_tail": tail(completed.stderr),
        "notification": notification,
    }
    print_json(payload)
    return 0 if payload["ok"] else completed.returncode or 1


def resolve_supervisor_invocation(python_exec: str, project: Path, supervisor_script: str) -> list[str]:
    if supervisor_script.strip():
        script = Path(supervisor_script).expanduser().resolve()
        if script.exists():
            return [python_exec, str(script)]
        raise RunFailure(
            "supervisor script path does not exist",
            details={"path": str(script)},
        )

    if has_module(python_exec, "longrun_supervisor"):
        return [python_exec, "-m", "longrun_supervisor"]

    discovered = discover_supervisor_script(project)
    if discovered is not None:
        return [python_exec, str(discovered)]

    raise RunFailure(
        "longrun_supervisor is unavailable",
        details={
            "hint": (
                "Install the supervisor repository in your Python environment "
                "(for example `pip install -e <repo-root>`), or pass --supervisor-script <path-to-supervisor.py>, "
                "or set LONGRUN_SUPERVISOR_PY."
            )
        },
    )


def discover_supervisor_script(project: Path) -> Path | None:
    # Lightweight local search only; avoid expensive full-disk crawling.
    roots: list[Path] = []
    roots.append(project)
    roots.extend(project.parents[:4])
    home = Path.home()
    roots.extend([home / "AI", home / "code", home / "src"])

    checked: set[Path] = set()
    for root in roots:
        if root in checked:
            continue
        checked.add(root)
        candidates = [
            root / "supervisor.py",
            root / "longrun_supervisor" / "supervisor.py",
            root / "long-running-task" / "supervisor.py",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
    return None


def has_module(python_exec: str, module_name: str) -> bool:
    probe = run_capture(
        [
            python_exec,
            "-c",
            (
                "import importlib.util, sys; "
                f"sys.exit(0 if importlib.util.find_spec('{module_name}') else 1)"
            ),
        ]
    )
    return probe.returncode == 0


def build_supervisor_command(
    supervisor_invocation: list[str],
    project: Path,
    action: str,
    extra_args: list[str] | None = None,
) -> list[str]:
    command = [*supervisor_invocation, "--project", str(project), action]
    if extra_args:
        command.extend(extra_args)
    return command


def build_run_command(args: argparse.Namespace, project: Path, supervisor_invocation: list[str]) -> list[str]:
    extra = [
        "--max-iterations",
        str(max(1, args.max_iterations)),
        "--max-runtime-seconds",
        str(max(0, args.max_runtime_seconds)),
        "--per-run-timeout-seconds",
        str(max(0, args.per_run_timeout_seconds)),
        "--max-stagnant-runs",
        str(max(1, args.max_stagnant_runs)),
        "--sandbox",
        str(args.sandbox),
    ]
    if args.objective.strip():
        extra.extend(["--objective", args.objective])
    if args.codex_bin.strip():
        extra.extend(["--codex-bin", args.codex_bin])
    if args.model.strip():
        extra.extend(["--model", args.model])
    extra.append("--full-auto" if args.full_auto else "--no-full-auto")
    if args.dangerously_bypass_approvals_and_sandbox:
        extra.append("--dangerously-bypass-approvals-and-sandbox")
    return build_supervisor_command(supervisor_invocation, project, "run", extra)


def build_detached_worker_command(args: argparse.Namespace, project: Path) -> list[str]:
    script_path = Path(__file__).resolve()
    command = [
        args.python,
        str(script_path),
        "--project",
        str(project),
        "--python",
        args.python,
        "--sandbox",
        str(args.sandbox),
        "--max-iterations",
        str(max(1, args.max_iterations)),
        "--max-runtime-seconds",
        str(max(0, args.max_runtime_seconds)),
        "--per-run-timeout-seconds",
        str(max(0, args.per_run_timeout_seconds)),
        "--max-stagnant-runs",
        str(max(1, args.max_stagnant_runs)),
        "--notify-timeout",
        str(max(1, args.notify_timeout)),
        "--notify-title",
        args.notify_title,
        "--notify-short",
        args.notify_short,
        "--notify-script",
        args.notify_script,
        "--detached-worker",
    ]

    if args.objective.strip():
        command.extend(["--objective", args.objective])
    if args.force_init:
        command.append("--force-init")
    if args.codex_bin.strip():
        command.extend(["--codex-bin", args.codex_bin])
    if args.model.strip():
        command.extend(["--model", args.model])
    command.append("--full-auto" if args.full_auto else "--no-full-auto")
    if args.dangerously_bypass_approvals_and_sandbox:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    if args.skip_doctor:
        command.append("--skip-doctor")
    if args.supervisor_script.strip():
        command.extend(["--supervisor-script", args.supervisor_script])
    if args.notify_message.strip():
        command.extend(["--notify-message", args.notify_message])
    if args.notify_dry_run:
        command.append("--notify-dry-run")
    command.append("--notify-on-exit" if args.notify_on_exit else "--no-notify-on-exit")
    return command


def start_detached(
    command: list[str],
    project: Path,
    *,
    status_command: list[str],
    report_command: list[str],
) -> dict[str, Any]:
    run_root = project / ".codex-longrun" / "supervisor"
    run_root.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = run_root / f"run_{stamp}.log"
    meta_path = run_root / "last_run.json"
    log_handle = log_path.open("a", encoding="utf-8")
    creationflags = 0
    start_new_session = False
    if os.name == "nt":
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        start_new_session = True
    process = subprocess.Popen(
        command,
        cwd=str(project),
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creationflags,
        start_new_session=start_new_session,
    )
    log_handle.close()
    payload = {
        "ok": True,
        "mode": "detached",
        "pid": process.pid,
        "command": command,
        "log_path": str(log_path),
        "meta_path": str(meta_path),
        "status_command": status_command,
        "report_command": report_command,
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def maybe_send_notification(
    *,
    args: argparse.Namespace,
    project: Path,
    status: str,
    summary: str,
) -> dict[str, Any]:
    if not args.notify_on_exit:
        return {"attempted": False, "reason": "notify_on_exit_disabled"}

    notify_script = Path(args.notify_script).expanduser().resolve()
    if not notify_script.exists():
        return {
            "attempted": False,
            "ok": False,
            "error": f"notify script not found: {notify_script}",
        }

    command = [
        args.python,
        str(notify_script),
        "--project",
        str(project),
        "--status",
        status,
        "--title",
        args.notify_title,
        "--short",
        args.notify_short,
        "--message",
        summary,
        "--timeout",
        str(max(1, int(args.notify_timeout))),
    ]
    if args.notify_dry_run:
        command.append("--dry-run")

    completed = run_capture(command, cwd=project)
    parsed_stdout = try_parse_json(completed.stdout)
    parsed_stderr = try_parse_json(completed.stderr)
    return {
        "attempted": True,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": command,
        "response": parsed_stdout if parsed_stdout is not None else tail(completed.stdout),
        "error": parsed_stderr if parsed_stderr is not None else tail(completed.stderr),
    }


def resolve_notification_status(state: dict[str, Any], *, returncode: int) -> str:
    phase_status = str(state.get("phase_status") or "").strip().lower()
    if phase_status in TERMINAL_PHASE_STATUSES:
        return phase_status
    return "stopped" if returncode == 0 else "blocked"


def default_notify_message(*, project: Path, returncode: int, state: dict[str, Any], note: str = "") -> str:
    objective = str(state.get("objective") or "long-running task")
    current_phase = str(state.get("current_phase") or "unknown")
    phase_status = str(state.get("phase_status") or "unknown")
    base = (
        f"run_until_complete exited with return code {returncode}; "
        f"phase_status={phase_status}; current_phase={current_phase}; objective={objective}; project={project}"
    )
    if note.strip():
        return f"{base}; note={note.strip()}"
    return base


def try_parse_json(value: str) -> Any | None:
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def load_state(project: Path) -> dict[str, Any] | None:
    path = project / ".codex-longrun" / "state.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    completed = run_capture(command, cwd=cwd)
    if completed.returncode != 0:
        raise RunFailure("command failed", details=process_details(completed))


def run_capture(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def process_details(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    return {
        "returncode": completed.returncode,
        "args": list(completed.args) if isinstance(completed.args, list) else completed.args,
        "stdout_tail": tail(completed.stdout),
        "stderr_tail": tail(completed.stderr),
    }


def tail(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


def print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
