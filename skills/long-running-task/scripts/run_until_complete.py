"""Start a state-driven Codex long-run supervisor until done or blocked.

This wrapper is intentionally small and conservative. It shields the skill from
minor `longrun_supervisor` CLI flag drift, initializes state when needed, and
can detach the supervisor so a normal Codex tool call does not have to remain
open for the whole task.
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
    args = parser.parse_args()

    project = args.project.resolve()
    if not project.exists():
        fail(f"project does not exist: {project}")

    if args.dry_run:
        command = build_run_command(args, project)
        print_json({"ok": True, "mode": "dry_run", "command": command})
        return 0

    state = load_state(project)
    needs_init = args.force_init or state is None or str(state.get("phase_status") or "") in {"done", "blocked"}
    if needs_init:
        if not args.objective.strip():
            fail("--objective is required when state is missing, done, blocked, or --force-init is used")
        run_checked(
            [
                args.python,
                "-m",
                "longrun_supervisor",
                "--project",
                str(project),
                "init",
                "--objective",
                args.objective,
                "--force",
            ]
        )

    if not args.skip_doctor:
        doctor = run_capture([args.python, "-m", "longrun_supervisor", "--project", str(project), "doctor"])
        if doctor.returncode != 0:
            fail("longrun_supervisor doctor failed", details=process_details(doctor))

    validate = run_capture([args.python, "-m", "longrun_supervisor", "--project", str(project), "validate"])
    if validate.returncode != 0:
        fail("longrun state validation failed", details=process_details(validate))

    command = build_run_command(args, project)
    if args.detach:
        payload = start_detached(command, project)
        print_json(payload)
        return 0

    completed = run_capture(command)
    payload = {
        "ok": completed.returncode == 0,
        "mode": "foreground",
        "returncode": completed.returncode,
        "command": command,
        "stdout_tail": tail(completed.stdout),
        "stderr_tail": tail(completed.stderr),
    }
    print_json(payload)
    return 0 if payload["ok"] else completed.returncode or 1


def build_run_command(args: argparse.Namespace, project: Path) -> list[str]:
    command = [
        args.python,
        "-m",
        "longrun_supervisor",
        "--project",
        str(project),
        "run",
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
        command.extend(["--objective", args.objective])
    if args.codex_bin.strip():
        command.extend(["--codex-bin", args.codex_bin])
    if args.model.strip():
        command.extend(["--model", args.model])
    command.append("--full-auto" if args.full_auto else "--no-full-auto")
    if args.dangerously_bypass_approvals_and_sandbox:
        command.append("--dangerously-bypass-approvals-and-sandbox")
    return command


def start_detached(command: list[str], project: Path) -> dict[str, Any]:
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
        "status_command": [
            sys.executable,
            "-m",
            "longrun_supervisor",
            "--project",
            str(project),
            "status",
        ],
        "report_command": [
            sys.executable,
            "-m",
            "longrun_supervisor",
            "--project",
            str(project),
            "report",
        ],
    }
    meta_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def load_state(project: Path) -> dict[str, Any] | None:
    path = project / ".codex-longrun" / "state.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def run_checked(command: list[str]) -> None:
    completed = run_capture(command)
    if completed.returncode != 0:
        fail("command failed", details=process_details(completed))


def run_capture(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
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


def fail(message: str, *, details: Any | None = None) -> None:
    payload = {"ok": False, "error": message}
    if details is not None:
        payload["details"] = details
    print_json(payload)
    raise SystemExit(1)


def print_json(payload: dict[str, Any]) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    try:
        sys.stdout.write(text)
    except UnicodeEncodeError:
        sys.stdout.buffer.write(text.encode("utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
