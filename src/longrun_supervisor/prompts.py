from __future__ import annotations

from textwrap import dedent


def initial_prompt(objective: str) -> str:
    return dedent(
        f"""
        Use the long-running-task skill.

        SUPERVISOR_WORKER_MODE: You are already running inside the longrun supervisor.
        Do not start supervisor.py from this Codex run. Execute the long-running-task Operating Loop directly.

        Objective:
        {objective}

        Initialize or read .codex-longrun state in this project.
        Work through the next phase, run relevant tests, debug failures, update state files,
        and continue until this run naturally ends.

        Stop only if the objective is done or a real blocker requires user input.
        Before stopping, update .codex-longrun/state.json, progress.md, and test-log.md.
        """
    ).strip()


def continuation_prompt() -> str:
    return dedent(
        """
        Use the long-running-task skill and continue the existing long-running task.

        SUPERVISOR_WORKER_MODE: You are already running inside the longrun supervisor.
        Do not start supervisor.py from this Codex run. Execute the long-running-task Operating Loop directly.

        First read:
        - .codex-longrun/state.json
        - .codex-longrun/roadmap.md
        - .codex-longrun/progress.md
        - .codex-longrun/test-log.md
        - .codex-longrun/blockers.md

        If the current phase is incomplete, finish it and run relevant tests.
        If tests fail, debug and rerun them.
        If the current phase is verified, choose the next useful phase from the roadmap or project evidence.
        Update state before stopping.
        Stop only when phase_status is done or blocked.
        """
    ).strip()
