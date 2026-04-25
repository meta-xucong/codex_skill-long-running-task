from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from longrun_supervisor.codex_cli import build_codex_exec_command, resolve_codex_bin, CodexCliOptions
from longrun_supervisor.doctor import DoctorCheck, checks_to_text, worst_status
from longrun_supervisor.state import LongrunPaths, ensure_state, load_state, validate_state


class StateTests(unittest.TestCase):
    def test_init_state_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths = LongrunPaths.from_project(Path(tmp))
            created = ensure_state(paths, "Build the thing")

            self.assertTrue(created)
            self.assertTrue(paths.state.exists())
            self.assertEqual(validate_state(load_state(paths)), [])

    def test_invalid_status_is_reported(self) -> None:
        state = {
            "objective": "x",
            "current_phase": "x",
            "phase_status": "mystery",
            "completed_phases": [],
            "next_actions": [],
            "tests_run": [],
            "known_bugs": [],
            "blockers": [],
            "done_criteria": [],
            "last_verified_at": "",
        }

        self.assertIn("Invalid phase_status: mystery", validate_state(state))


class CodexCliTests(unittest.TestCase):
    def test_resolve_codex_bin_returns_a_value(self) -> None:
        self.assertTrue(resolve_codex_bin("codex"))

    def test_build_codex_exec_command_uses_stdin_prompt(self) -> None:
        command = build_codex_exec_command(CodexCliOptions(), Path("."), Path("last.md"))
        self.assertEqual(command[-1], "-")
        self.assertIn("exec", command)


class DoctorTests(unittest.TestCase):
    def test_worst_status(self) -> None:
        self.assertEqual(worst_status([DoctorCheck("x", "ok", "fine")]), 0)
        self.assertEqual(worst_status([DoctorCheck("x", "warn", "hmm")]), 2)
        self.assertEqual(worst_status([DoctorCheck("x", "error", "bad")]), 1)

    def test_checks_to_text(self) -> None:
        text = checks_to_text([DoctorCheck("python", "ok", "3.x")])
        self.assertIn("OK", text)
        self.assertIn("python", text)


if __name__ == "__main__":
    unittest.main()
