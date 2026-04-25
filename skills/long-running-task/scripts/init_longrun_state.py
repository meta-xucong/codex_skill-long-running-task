#!/usr/bin/env python3
"""Initialize .codex-longrun state for a target project."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_STATUS = "discovering"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def build_state(objective: str) -> dict:
    return {
        "objective": objective,
        "current_phase": "Discover project structure",
        "phase_status": DEFAULT_STATUS,
        "completed_phases": [],
        "next_actions": [
            "Inspect project structure and existing scripts",
            "Identify relevant tests or checks",
            "Plan the first implementation phase",
        ],
        "tests_run": [],
        "known_bugs": [],
        "blockers": [],
        "done_criteria": [
            "Requested implementation work is complete",
            "Relevant tests or checks pass",
            "Progress and verification are recorded",
        ],
        "last_verified_at": "",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def write_if_missing(path: Path, content: str) -> bool:
    if path.exists():
        return False
    path.write_text(content, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize .codex-longrun in a project.")
    parser.add_argument("--project", default=".", help="Target project directory.")
    parser.add_argument("--objective", required=True, help="Long-running task objective.")
    parser.add_argument("--force", action="store_true", help="Overwrite existing state.json.")
    args = parser.parse_args()

    project = Path(args.project).expanduser().resolve()
    longrun = project / ".codex-longrun"
    longrun.mkdir(parents=True, exist_ok=True)

    state_path = longrun / "state.json"
    if state_path.exists() and not args.force:
        print(f"State already exists: {state_path}")
    else:
        state_path.write_text(
            json.dumps(build_state(args.objective), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"Wrote {state_path}")

    write_if_missing(longrun / "roadmap.md", f"# Roadmap\n\nObjective: {args.objective}\n\n")
    write_if_missing(longrun / "progress.md", "# Progress\n\n")
    write_if_missing(longrun / "test-log.md", "# Test Log\n\n")
    write_if_missing(longrun / "decisions.md", "# Decisions\n\n")
    write_if_missing(longrun / "blockers.md", "# Blockers\n\n")
    (longrun / "logs").mkdir(exist_ok=True)
    (longrun / "snapshots").mkdir(exist_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
