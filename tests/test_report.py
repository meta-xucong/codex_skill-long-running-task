from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from longrun_supervisor.report import build_report, latest_file, report_to_text
from longrun_supervisor.state import LongrunPaths, ensure_state


class ReportTests(unittest.TestCase):
    def test_latest_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "a.summary.json"
            second = root / "b.summary.json"
            first.write_text("{}", encoding="utf-8")
            second.write_text("{}", encoding="utf-8")
            os.utime(first, (1, 1))
            os.utime(second, (2, 2))

            self.assertEqual(latest_file(root, "*.summary.json"), second)

    def test_build_report_with_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = LongrunPaths.from_project(tmp)
            ensure_state(paths, "Report demo")
            summary = paths.logs / "run.summary.json"
            summary.write_text(
                json.dumps({"thread_id": "abc", "total_events": 2, "command_executions": 1}),
                encoding="utf-8",
            )

            report = build_report(paths)
            text = report_to_text(report)

        self.assertEqual(report["state"]["objective"], "Report demo")
        self.assertIn("Latest summary:", text)
        self.assertIn("Thread: abc", text)


if __name__ == "__main__":
    unittest.main()
