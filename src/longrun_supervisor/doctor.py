from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .codex_cli import resolve_codex_bin
from .state import LongrunPaths, load_state, validate_state


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str


def run_doctor(project: str | Path = ".", codex_bin: str = "codex") -> list[DoctorCheck]:
    paths = LongrunPaths.from_project(project)
    checks = [
        check_python(),
        check_codex(codex_bin),
        check_skill(),
        check_project_state(paths),
        check_rg(),
    ]
    return checks


def check_python() -> DoctorCheck:
    return DoctorCheck(
        name="python",
        status="ok",
        detail=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    )


def check_codex(codex_bin: str) -> DoctorCheck:
    resolved = resolve_codex_bin(codex_bin)
    if not resolved:
        return DoctorCheck("codex", "error", "Codex executable was not found")
    try:
        result = subprocess.run(
            [resolved, "--version"],
            text=True,
            capture_output=True,
            timeout=20,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck("codex", "error", f"{resolved}: {exc}")

    output = (result.stdout or result.stderr).strip()
    status = "ok" if result.returncode == 0 else "error"
    return DoctorCheck("codex", status, f"{resolved}: {output}")


def check_skill() -> DoctorCheck:
    path = Path.home() / ".codex" / "skills" / "long-running-task" / "SKILL.md"
    if path.exists():
        return DoctorCheck("long-running-task-skill", "ok", str(path))
    return DoctorCheck("long-running-task-skill", "error", f"Missing {path}")


def check_project_state(paths: LongrunPaths) -> DoctorCheck:
    if not paths.state.exists():
        return DoctorCheck("project-state", "warn", f"Missing {paths.state}")
    try:
        errors = validate_state(load_state(paths))
    except (OSError, json.JSONDecodeError) as exc:
        return DoctorCheck("project-state", "error", str(exc))
    if errors:
        return DoctorCheck("project-state", "error", "; ".join(errors))
    return DoctorCheck("project-state", "ok", str(paths.state))


def check_rg() -> DoctorCheck:
    resolved = shutil.which("rg")
    if not resolved:
        return DoctorCheck("ripgrep", "warn", "rg was not found")
    try:
        result = subprocess.run(
            [resolved, "--version"],
            text=True,
            capture_output=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return DoctorCheck("ripgrep", "warn", f"{resolved}: {exc}")
    output = (result.stdout or result.stderr).splitlines()
    detail = output[0] if output else resolved
    status = "ok" if result.returncode == 0 else "warn"
    return DoctorCheck("ripgrep", status, detail)


def checks_to_json(checks: list[DoctorCheck]) -> str:
    return json.dumps([asdict(check) for check in checks], indent=2, ensure_ascii=False)


def checks_to_text(checks: list[DoctorCheck]) -> str:
    width = max(len(check.name) for check in checks) if checks else 0
    return "\n".join(
        f"{check.status.upper():5} {check.name.ljust(width)}  {check.detail}" for check in checks
    )


def worst_status(checks: list[DoctorCheck]) -> int:
    if any(check.status == "error" for check in checks):
        return 1
    if any(check.status == "warn" for check in checks):
        return 2
    return 0
