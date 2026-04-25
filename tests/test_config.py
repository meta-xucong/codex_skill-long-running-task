from __future__ import annotations

import argparse
import json
import tempfile
import unittest
from pathlib import Path

from longrun_supervisor.config import RunSettings, apply_cli_overrides, load_run_settings


class ConfigTests(unittest.TestCase):
    def test_load_json_config_with_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "longrun.json"
            path.write_text(
                json.dumps(
                    {
                        "run": {
                            "project": "demo",
                            "objective": "Ship it",
                            "max_iterations": 9,
                        },
                        "codex": {
                            "model": "gpt-test",
                            "sandbox": "workspace-write",
                            "full_auto": True,
                        },
                    }
                ),
                encoding="utf-8-sig",
            )

            settings = load_run_settings(path)

        self.assertEqual(settings.project, "demo")
        self.assertEqual(settings.objective, "Ship it")
        self.assertEqual(settings.max_iterations, 9)
        self.assertEqual(settings.max_repeated_failure_runs, 3)
        self.assertEqual(settings.model, "gpt-test")
        self.assertEqual(settings.sandbox, "workspace-write")
        self.assertTrue(settings.full_auto)

    def test_load_toml_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "longrun.toml"
            path.write_text(
                """
[run]
project = "demo"
max_iterations = 3
max_repeated_failure_runs = 4

[codex]
full_auto = true
""".strip(),
                encoding="utf-8",
            )

            settings = load_run_settings(path)

        self.assertEqual(settings.project, "demo")
        self.assertEqual(settings.max_iterations, 3)
        self.assertEqual(settings.max_repeated_failure_runs, 4)
        self.assertTrue(settings.full_auto)

    def test_cli_overrides_config(self) -> None:
        args = argparse.Namespace(project="override", max_iterations=7, model=None)
        settings = apply_cli_overrides(
            RunSettings(project="from-config", max_iterations=2, model="gpt-test"),
            args,
        )

        self.assertEqual(settings.project, "override")
        self.assertEqual(settings.max_iterations, 7)
        self.assertEqual(settings.model, "gpt-test")


if __name__ == "__main__":
    unittest.main()
