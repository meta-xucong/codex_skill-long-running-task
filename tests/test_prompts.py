from __future__ import annotations

import unittest

from longrun_supervisor.prompts import continuation_prompt, initial_prompt


class PromptTests(unittest.TestCase):
    def test_initial_prompt_contains_worker_mode_guard(self) -> None:
        prompt = initial_prompt("Do the thing")
        self.assertIn("SUPERVISOR_WORKER_MODE", prompt)
        self.assertIn("Do not start supervisor.py", prompt)

    def test_continuation_prompt_contains_worker_mode_guard(self) -> None:
        prompt = continuation_prompt()
        self.assertIn("SUPERVISOR_WORKER_MODE", prompt)
        self.assertIn("Do not start supervisor.py", prompt)


if __name__ == "__main__":
    unittest.main()
