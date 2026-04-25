from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from longrun_supervisor.events import failure_signature, summarize_jsonl


class EventTests(unittest.TestCase):
    def test_summarize_jsonl_counts_key_events(self) -> None:
        events = [
            {"type": "thread.started", "thread_id": "abc"},
            {
                "type": "item.completed",
                "item": {"type": "agent_message", "text": "hello"},
            },
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "python check.py",
                    "exit_code": 1,
                    "status": "failed",
                    "aggregated_output": "AssertionError",
                },
            },
            {
                "type": "item.completed",
                "item": {"type": "file_change", "status": "completed"},
            },
            "{not json",
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for event in events:
                    if isinstance(event, str):
                        handle.write(event + "\n")
                    else:
                        handle.write(json.dumps(event) + "\n")

            summary = summarize_jsonl(path)

        self.assertEqual(summary.thread_id, "abc")
        self.assertEqual(summary.agent_messages, 1)
        self.assertEqual(summary.command_executions, 1)
        self.assertEqual(len(summary.command_failures), 1)
        self.assertEqual(summary.file_changes, 1)
        self.assertEqual(summary.malformed_lines, 1)
        self.assertTrue(failure_signature(summary).startswith("command|python check.py|1|failed|"))

    def test_timeout_failure_signature(self) -> None:
        self.assertEqual(failure_signature(summarize_jsonl(Path("missing.jsonl")), timed_out=True), "codex-timeout")


if __name__ == "__main__":
    unittest.main()
