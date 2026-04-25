from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .state import LongrunPaths, load_state, summarize_state


def build_report(paths: LongrunPaths) -> dict[str, Any]:
    report: dict[str, Any] = {
        "project": str(paths.project),
        "state": None,
        "latest_summary_path": "",
        "latest_summary": None,
        "latest_last_message_path": "",
    }
    if paths.state.exists():
        report["state"] = summarize_state(load_state(paths))

    latest_summary = latest_file(paths.logs, "*.summary.json")
    if latest_summary:
        report["latest_summary_path"] = str(latest_summary)
        try:
            report["latest_summary"] = json.loads(latest_summary.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report["latest_summary"] = {"error": str(exc)}

        last_message = latest_summary.with_name(latest_summary.name.replace(".summary.json", ".last-message.md"))
        if last_message.exists():
            report["latest_last_message_path"] = str(last_message)

    return report


def latest_file(directory: Path, pattern: str) -> Path | None:
    if not directory.exists():
        return None
    files = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    return files[0] if files else None


def report_to_text(report: dict[str, Any]) -> str:
    lines = [f"Project: {report['project']}"]
    state = report.get("state")
    if state:
        lines.extend(
            [
                f"Status: {state.get('phase_status', 'unknown')}",
                f"Phase: {state.get('current_phase', '')}",
                f"Next actions: {len(state.get('next_actions', []))}",
                f"Known bugs: {len(state.get('known_bugs', []))}",
                f"Blockers: {len(state.get('blockers', []))}",
                f"Last verified: {state.get('last_verified_at', '') or 'never'}",
            ]
        )
    else:
        lines.append("Status: no state file")

    summary = report.get("latest_summary")
    if summary:
        lines.extend(
            [
                "",
                f"Latest summary: {report.get('latest_summary_path', '')}",
                f"Thread: {summary.get('thread_id', 'unknown')}",
                f"Events: {summary.get('total_events', 0)}",
                f"Commands: {summary.get('command_executions', 0)}",
                f"Command failures: {len(summary.get('command_failures', []))}",
                f"File changes: {summary.get('file_changes', 0)}",
                f"Last message: {report.get('latest_last_message_path', '') or 'none'}",
            ]
        )
    else:
        lines.extend(["", "Latest summary: none"])

    return "\n".join(lines)
