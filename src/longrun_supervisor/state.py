from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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

REQUIRED_FIELDS: dict[str, type] = {
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


@dataclass(frozen=True)
class LongrunPaths:
    project: Path
    root: Path
    state: Path
    roadmap: Path
    progress: Path
    test_log: Path
    decisions: Path
    blockers: Path
    logs: Path
    snapshots: Path

    @classmethod
    def from_project(cls, project: str | Path) -> "LongrunPaths":
        project_path = Path(project).expanduser().resolve()
        root = project_path / ".codex-longrun"
        return cls(
            project=project_path,
            root=root,
            state=root / "state.json",
            roadmap=root / "roadmap.md",
            progress=root / "progress.md",
            test_log=root / "test-log.md",
            decisions=root / "decisions.md",
            blockers=root / "blockers.md",
            logs=root / "logs",
            snapshots=root / "snapshots",
        )


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def default_state(objective: str) -> dict[str, Any]:
    timestamp = now_iso()
    return {
        "objective": objective,
        "current_phase": "Discover project structure",
        "phase_status": "discovering",
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
        "created_at": timestamp,
        "updated_at": timestamp,
    }


def ensure_state(paths: LongrunPaths, objective: str, force: bool = False) -> bool:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.logs.mkdir(exist_ok=True)
    paths.snapshots.mkdir(exist_ok=True)

    created = False
    if force or not paths.state.exists():
        save_state(paths, default_state(objective))
        created = True

    write_if_missing(paths.roadmap, f"# Roadmap\n\nObjective: {objective}\n\n")
    write_if_missing(paths.progress, "# Progress\n\n")
    write_if_missing(paths.test_log, "# Test Log\n\n")
    write_if_missing(paths.decisions, "# Decisions\n\n")
    write_if_missing(paths.blockers, "# Blockers\n\n")
    return created


def write_if_missing(path: Path, content: str) -> None:
    if not path.exists():
        path.write_text(content, encoding="utf-8")


def load_state(paths: LongrunPaths) -> dict[str, Any]:
    return json.loads(paths.state.read_text(encoding="utf-8"))


def save_state(paths: LongrunPaths, state: dict[str, Any]) -> None:
    state = dict(state)
    state["updated_at"] = now_iso()
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.state.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_state(state: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in state:
            errors.append(f"Missing required field: {field}")
            continue
        if not isinstance(state[field], expected_type):
            errors.append(
                f"Field {field!r} must be {expected_type.__name__}, got {type(state[field]).__name__}"
            )

    status = state.get("phase_status")
    if isinstance(status, str) and status not in ALLOWED_STATUSES:
        errors.append(f"Invalid phase_status: {status}")

    if state.get("phase_status") == "done" and state.get("blockers"):
        errors.append("State cannot be done while blockers is non-empty")

    return errors


def state_fingerprint(paths: LongrunPaths) -> str:
    if not paths.state.exists():
        return ""
    content = paths.state.read_bytes()
    return hashlib.sha256(content).hexdigest()


def snapshot_state(paths: LongrunPaths, label: str) -> Path | None:
    if not paths.state.exists():
        return None
    paths.snapshots.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in label)
    snapshot = paths.snapshots / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_label}.json"
    shutil.copy2(paths.state, snapshot)
    return snapshot


def append_markdown(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(text.rstrip() + "\n\n")


def classify_state(state: dict[str, Any]) -> str:
    status = state.get("phase_status")
    if status == "done":
        return "done"
    if status == "blocked":
        return "blocked"
    return "continue"


def summarize_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective": state.get("objective", ""),
        "current_phase": state.get("current_phase", ""),
        "phase_status": state.get("phase_status", ""),
        "next_actions": state.get("next_actions", []),
        "known_bugs": state.get("known_bugs", []),
        "blockers": state.get("blockers", []),
        "last_verified_at": state.get("last_verified_at", ""),
    }
