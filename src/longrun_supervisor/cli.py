from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

from .config import apply_cli_overrides, load_run_settings
from .codex_cli import CodexCliOptions, run_codex_exec
from .doctor import checks_to_json, checks_to_text, run_doctor, worst_status
from .events import failure_signature, summarize_jsonl, write_summary
from .prompts import continuation_prompt, initial_prompt
from .report import build_report, report_to_text
from .state import (
    LongrunPaths,
    append_markdown,
    classify_state,
    ensure_state,
    load_state,
    snapshot_state,
    state_fingerprint,
    summarize_state,
    validate_state,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Supervise state-driven long-running Codex tasks.")
    parser.add_argument("--project", help="Target project directory.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize .codex-longrun state.")
    init_parser.add_argument("--objective", required=True, help="Long-running task objective.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing state.json.")

    subparsers.add_parser("status", help="Print state summary.")
    subparsers.add_parser("validate", help="Validate .codex-longrun/state.json.")
    doctor_parser = subparsers.add_parser("doctor", help="Check local longrun supervisor environment.")
    doctor_parser.add_argument("--codex-bin", default="codex", help="Codex executable.")
    doctor_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    doctor_parser.add_argument("--strict", action="store_true", help="Return non-zero for warnings.")
    report_parser = subparsers.add_parser("report", help="Print current state and latest run summary.")
    report_parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")

    run_parser = subparsers.add_parser("run", help="Run Codex until state is done, blocked, or limits hit.")
    run_parser.add_argument("--config", help="JSON or TOML config file for run defaults.")
    run_parser.add_argument("--objective", help="Objective used when state does not exist.")
    run_parser.add_argument("--max-iterations", type=int, help="Maximum Codex runs.")
    run_parser.add_argument("--max-runtime-seconds", type=int, help="Overall runtime cap; 0 disables.")
    run_parser.add_argument("--per-run-timeout-seconds", type=int, help="Single Codex run timeout; 0 disables.")
    run_parser.add_argument("--max-stagnant-runs", type=int, help="Stop after this many unchanged state runs.")
    run_parser.add_argument("--codex-bin", help="Codex executable.")
    run_parser.add_argument("--model", help="Model passed to codex exec.")
    run_parser.add_argument("--sandbox", help="Sandbox passed to codex exec.")
    run_parser.add_argument(
        "--full-auto",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Pass --full-auto to codex exec.",
    )
    run_parser.add_argument(
        "--dangerously-bypass-approvals-and-sandbox",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Pass Codex's dangerous bypass flag. Use only inside an external sandbox.",
    )
    run_parser.add_argument("--dry-run", action="store_true", help="Print the next prompt without running Codex.")

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    paths = LongrunPaths.from_project(args.project or ".")
    created = ensure_state(paths, args.objective, force=args.force)
    print(("Initialized" if created else "Already initialized") + f": {paths.root}")
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    paths = LongrunPaths.from_project(args.project or ".")
    if not paths.state.exists():
        print(f"State not found: {paths.state}")
        return 2
    print(json.dumps(summarize_state(load_state(paths)), indent=2, ensure_ascii=False))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    paths = LongrunPaths.from_project(args.project or ".")
    if not paths.state.exists():
        print(f"State not found: {paths.state}")
        return 2
    errors = validate_state(load_state(paths))
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {paths.state}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    checks = run_doctor(args.project or ".", codex_bin=args.codex_bin)
    print(checks_to_json(checks) if args.json else checks_to_text(checks))
    status = worst_status(checks)
    if status == 2 and not args.strict:
        return 0
    return status


def cmd_report(args: argparse.Namespace) -> int:
    paths = LongrunPaths.from_project(args.project or ".")
    report = build_report(paths)
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else report_to_text(report))
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    try:
        settings = apply_cli_overrides(load_run_settings(args.config), args)
    except (FileNotFoundError, ValueError, TypeError) as exc:
        print(f"Config error: {exc}")
        return 2

    paths = LongrunPaths.from_project(settings.project)
    if not paths.state.exists():
        if not settings.objective:
            print("--objective is required when state does not exist")
            return 2
        ensure_state(paths, settings.objective)

    options = CodexCliOptions(
        codex_bin=settings.codex_bin,
        model=settings.model,
        sandbox=settings.sandbox,
        full_auto=settings.full_auto,
        dangerously_bypass_approvals_and_sandbox=settings.dangerously_bypass_approvals_and_sandbox,
    )

    started = time.monotonic()
    stagnant_runs = 0
    repeated_failure_signature = ""
    repeated_failure_runs = 0

    for iteration in range(1, settings.max_iterations + 1):
        state = load_state(paths)
        errors = validate_state(state)
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1

        state_class = classify_state(state)
        if state_class == "done":
            print("Long-running task is done.")
            return 0
        if state_class == "blocked":
            print("Long-running task is blocked.")
            return 3

        if settings.max_runtime_seconds and time.monotonic() - started > settings.max_runtime_seconds:
            print("Max runtime reached.")
            return 4

        prompt = initial_prompt(state["objective"]) if iteration == 1 else continuation_prompt()
        if args.dry_run:
            print(prompt)
            return 0

        run_id = f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-iter-{iteration:03d}"
        before_hash = state_fingerprint(paths)
        snapshot_state(paths, f"{run_id}-before")

        print(f"Starting Codex run {iteration}/{settings.max_iterations}: {run_id}")
        result = run_codex_exec(
            project=paths.project,
            prompt=prompt,
            logs_dir=paths.logs,
            run_id=run_id,
            options=options,
            timeout_seconds=settings.per_run_timeout_seconds or None,
        )
        event_summary = summarize_jsonl(result.stdout_path)
        event_summary_path = paths.logs / f"{run_id}.summary.json"
        write_summary(event_summary_path, event_summary)
        snapshot_state(paths, f"{run_id}-after")

        append_markdown(
            paths.progress,
            "\n".join(
                [
                    f"## Supervisor Run {run_id}",
                    "",
                    f"- returncode: {result.returncode}",
                    f"- timed_out: {result.timed_out}",
                    f"- stdout: `{result.stdout_path}`",
                    f"- stderr: `{result.stderr_path}`",
                    f"- last_message: `{result.last_message_path}`",
                    f"- event_summary: `{event_summary_path}`",
                    "",
                    event_summary.to_markdown(),
                ]
            ),
        )

        if result.returncode != 0:
            if result.timed_out:
                print(f"Codex run timed out. See {result.stderr_path}")
            else:
                print(f"Codex run failed with exit code {result.returncode}. See {result.stderr_path}")
            return result.returncode

        after_state = load_state(paths)
        after_state_class = classify_state(after_state)
        signature = failure_signature(event_summary, returncode=result.returncode, timed_out=result.timed_out)
        if after_state_class == "continue" and signature:
            if signature == repeated_failure_signature:
                repeated_failure_runs += 1
            else:
                repeated_failure_signature = signature
                repeated_failure_runs = 1
            print(
                "Repeated failure signature "
                f"({repeated_failure_runs}/{settings.max_repeated_failure_runs}): {signature}"
            )
            if repeated_failure_runs >= settings.max_repeated_failure_runs:
                print("Stopping because the same failure repeated across runs.")
                return 6
        else:
            repeated_failure_signature = ""
            repeated_failure_runs = 0

        after_hash = state_fingerprint(paths)
        if before_hash == after_hash:
            stagnant_runs += 1
            print(f"State unchanged after run ({stagnant_runs}/{settings.max_stagnant_runs}).")
            if stagnant_runs >= settings.max_stagnant_runs:
                print("Stopping because state did not change across repeated runs.")
                return 5
        else:
            stagnant_runs = 0

    print("Max iterations reached.")
    return 4


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "init":
        return cmd_init(args)
    if args.command == "status":
        return cmd_status(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "report":
        return cmd_report(args)
    if args.command == "run":
        return cmd_run(args)

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
