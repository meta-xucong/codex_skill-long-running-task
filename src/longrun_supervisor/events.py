from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class CommandEvent:
    command: str
    exit_code: int | None
    status: str
    output_tail: str = ""


@dataclass
class EventSummary:
    total_events: int = 0
    malformed_lines: int = 0
    thread_id: str = ""
    agent_messages: int = 0
    command_executions: int = 0
    command_failures: list[CommandEvent] = field(default_factory=list)
    file_changes: int = 0
    file_change_failures: int = 0
    last_event_type: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_markdown(self) -> str:
        lines = [
            "### Event Summary",
            "",
            f"- total_events: {self.total_events}",
            f"- malformed_lines: {self.malformed_lines}",
            f"- thread_id: {self.thread_id or 'unknown'}",
            f"- agent_messages: {self.agent_messages}",
            f"- command_executions: {self.command_executions}",
            f"- command_failures: {len(self.command_failures)}",
            f"- file_changes: {self.file_changes}",
            f"- file_change_failures: {self.file_change_failures}",
            f"- last_event_type: {self.last_event_type or 'unknown'}",
        ]
        for failure in self.command_failures[:5]:
            lines.extend(
                [
                    "",
                    f"- failed_command: `{failure.command}`",
                    f"  exit_code: {failure.exit_code}",
                    f"  status: {failure.status}",
                    f"  output_tail: {failure.output_tail or 'n/a'}",
                ]
            )
        return "\n".join(lines)


def summarize_jsonl(path: Path) -> EventSummary:
    summary = EventSummary()
    if not path.exists():
        return summary

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                summary.malformed_lines += 1
                continue
            update_summary(summary, event)

    return summary


def update_summary(summary: EventSummary, event: dict[str, Any]) -> None:
    summary.total_events += 1
    event_type = str(event.get("type", ""))
    summary.last_event_type = event_type

    if event_type == "thread.started":
        summary.thread_id = str(event.get("thread_id", ""))
        return

    item = event.get("item")
    if not isinstance(item, dict):
        return

    item_type = item.get("type")
    status = str(item.get("status", ""))
    if item_type == "agent_message" and event_type == "item.completed":
        summary.agent_messages += 1
    elif item_type == "command_execution" and event_type == "item.completed":
        summary.command_executions += 1
        exit_code = item.get("exit_code")
        if status == "failed" or (isinstance(exit_code, int) and exit_code != 0):
            summary.command_failures.append(
                CommandEvent(
                    command=str(item.get("command", "")),
                    exit_code=exit_code if isinstance(exit_code, int) else None,
                    status=status,
                    output_tail=tail(str(item.get("aggregated_output", ""))),
                )
            )
    elif item_type == "file_change" and event_type == "item.completed":
        summary.file_changes += 1
        if status == "failed":
            summary.file_change_failures += 1


def tail(text: str, limit: int = 500) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[-limit:]


def write_summary(path: Path, summary: EventSummary) -> None:
    path.write_text(json.dumps(summary.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def failure_signature(summary: EventSummary, *, returncode: int = 0, timed_out: bool = False) -> str:
    if timed_out:
        return "codex-timeout"
    if summary.command_failures:
        failure = summary.command_failures[0]
        return "|".join(
            [
                "command",
                failure.command,
                str(failure.exit_code),
                failure.status,
                tail(failure.output_tail, limit=160),
            ]
        )
    if summary.file_change_failures:
        return "file-change-failure"
    if returncode:
        return f"codex-returncode-{returncode}"
    return ""
