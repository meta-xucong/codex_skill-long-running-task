#!/usr/bin/env python3
"""Validate .codex-longrun/state.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_FIELDS = {
    "objective": str,
    "current_phase": str,
    "phase_status": str,
    "completed_phases": list,
    "next_actions": list,
    "tests_run": list,
    "known_bugs": list,
    "blockers": list,
    "done_criteria": list,
    "last_verified_at": str,
}

ALLOWED_STATUSES = {
    "discovering",
    "planning",
    "implementing",
    "testing",
    "debugging",
    "verifying",
    "advancing",
    "blocked",
    "done",
}


def validate_state(data: dict) -> list[str]:
    errors: list[str] = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in data:
            errors.append(f"Missing required field: {field}")
            continue
        if not isinstance(data[field], expected_type):
            errors.append(
                f"Field {field!r} must be {expected_type.__name__}, got {type(data[field]).__name__}"
            )

    status = data.get("phase_status")
    if isinstance(status, str) and status not in ALLOWED_STATUSES:
        errors.append(f"Invalid phase_status: {status}")

    if data.get("phase_status") == "done" and data.get("blockers"):
        errors.append("State cannot be done while blockers is non-empty")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate .codex-longrun/state.json.")
    parser.add_argument("--project", default=".", help="Target project directory.")
    parser.add_argument("--state", help="Explicit state.json path.")
    args = parser.parse_args()

    state_path = Path(args.state).expanduser().resolve() if args.state else (
        Path(args.project).expanduser().resolve() / ".codex-longrun" / "state.json"
    )

    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(f"State file not found: {state_path}")
        return 2
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {state_path}: {exc}")
        return 2

    errors = validate_state(data)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"OK: {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
