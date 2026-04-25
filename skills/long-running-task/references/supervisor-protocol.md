# Supervisor Protocol

External supervisors should treat Codex as a worker that can stop naturally after a phase. The supervisor is responsible for restarting or resuming Codex only when the persistent state says more work remains.

## Initial Prompt

```text
Use the long-running-task skill.

Objective:
<objective>

Initialize or read .codex-longrun state in this project.
Work through the next phase, run relevant tests, debug failures, update state files, and continue until this run naturally ends.
Stop only if the objective is done or a real blocker requires user input.
```

## Continuation Prompt

```text
Use the long-running-task skill and continue the existing long-running task.

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
```

## Supervisor Decision Logic

Continue when:

- `phase_status` is not `done` or `blocked`
- `next_actions` is non-empty
- there are known bugs that are not blocked
- tests failed and the failure is still actionable

Stop when:

- `phase_status` is `done`
- `phase_status` is `blocked`
- max iterations, runtime, or stagnant-run limits are reached

## Recommended Codex CLI Flags

Use `codex exec` first:

```bash
codex exec --json --output-last-message <file> --skip-git-repo-check -C <project> <prompt>
```

Add these only when appropriate:

- `--model <model>`
- `--sandbox workspace-write`
- `--full-auto`
- `--dangerously-bypass-approvals-and-sandbox` only inside an external sandbox

Prefer a state-driven fresh `codex exec` loop before UI automation.
