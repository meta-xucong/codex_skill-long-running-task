---
name: long-running-task
description: Sustain long-running Codex development tasks across phase boundaries using persistent project state, verification loops, and explicit stop conditions. Use when the user asks Codex to keep working through a roadmap, continue implementation without waiting after each phase, automatically test and debug, resume a large project, or coordinate with an external supervisor that repeatedly invokes Codex until the task is done or blocked.
---

# Long Running Task

## Auto Supervisor Mode

When the user invokes this skill from a normal Codex conversation and asks to continue, keep working, long-run, auto-develop, or avoid stopping between phases, start the external supervisor automatically.

Use the current Codex working directory as the target project path unless the user explicitly provides another path. Do not ask the user to paste a project path when the current working directory is already the target project.

Preferred supervisor command after installing this repository with `pip install -e .`:

```powershell
python -m longrun_supervisor --project . doctor
python -m longrun_supervisor --project . status
python -m longrun_supervisor --project . run --max-iterations 999999 --max-runtime-seconds 0 --per-run-timeout-seconds 1800 --max-stagnant-runs 999999 --max-repeated-failure-runs 10 --sandbox workspace-write --full-auto
```

If `.codex-longrun/state.json` is missing, `done`, `blocked`, or clearly about a different objective, initialize it first:

```powershell
python -m longrun_supervisor --project . init --objective "<objective inferred from the user's request>" --force
```

If `python -m longrun_supervisor` is unavailable but a local checkout path is known, use that checkout's `supervisor.py` instead.

Important recursion guard: if the prompt says `SUPERVISOR_WORKER_MODE`, or the environment contains `LONGRUN_SUPERVISOR_WORKER=1`, do not start `supervisor.py`. In that case, this Codex run is already being managed by the supervisor; follow the Operating Loop below directly.

See `references/execution-spec.md` for the full automatic execution contract.

## Operating Loop

Use this skill to continue a development task until the project state says the objective is done or blocked.

At the start of every run:

1. Read `.codex-longrun/state.json` if it exists.
2. Read `.codex-longrun/roadmap.md`, `.codex-longrun/progress.md`, `.codex-longrun/test-log.md`, and `.codex-longrun/blockers.md` when present.
3. If state files are missing, create them with `scripts/init_longrun_state.py` or by following `references/state-schema.md`.
4. Identify the current phase, pending next actions, known bugs, and done criteria.
5. Continue the most valuable unfinished work without asking for confirmation unless a stop condition applies.

Repeat this loop:

1. Select the next concrete action from the roadmap, state file, failing tests, or project evidence.
2. Implement a small verifiable change.
3. Run the narrowest relevant tests or checks.
4. If tests fail, debug and rerun them before moving on.
5. Update `.codex-longrun/state.json` and append concise notes to `progress.md` and `test-log.md`.
6. Advance to the next phase when the current phase is verified.
7. Stop only when `phase_status` is `done` or `blocked`.

Prefer existing project conventions, test commands, and architecture. Keep changes scoped to the current phase.

## Phase Status Values

Use only these `phase_status` values:

- `discovering`
- `planning`
- `implementing`
- `testing`
- `debugging`
- `verifying`
- `advancing`
- `blocked`
- `done`

Set `blocked` only when a real user decision or unavailable external requirement prevents safe progress.

Set `done` only when all reasonable implementation, verification, cleanup, and documentation tasks tied to the objective are complete.

## State Discipline

Keep `.codex-longrun/state.json` valid JSON. Validate it with:

```bash
python "%USERPROFILE%\.codex\skills\long-running-task\scripts\validate_state.py" --project <project-path>
```

Required fields:

- `objective`
- `current_phase`
- `phase_status`
- `completed_phases`
- `next_actions`
- `tests_run`
- `known_bugs`
- `blockers`
- `done_criteria`
- `last_verified_at`

Use `references/state-schema.md` for the full schema and examples.

## Testing Rules

Discover test commands from the repository before inventing new ones. Prefer, in order:

1. Existing task runner scripts such as `package.json`, `pyproject.toml`, `Makefile`, `justfile`, or CI config.
2. Focused tests for touched modules.
3. Broader suites after shared behavior changes.
4. Static checks or smoke tests when no formal suite exists.

After each test run, append to `.codex-longrun/test-log.md`:

- command
- result
- relevant error summary
- fix attempted, if any
- next verification command

Do not advance phases after a failing relevant test unless the failure is documented as unrelated or blocked.

If a test command repeatedly prints a passing or failing result but exits by timeout, treat that as a test runner/environment problem after two focused attempts. Use a simpler equivalent verification command when possible, such as a direct Python assertion script or a narrower test invocation. If no clean command can be found, update `known_bugs` or `blockers` with the timeout details before stopping.

## Bug Iteration Rules

When a bug or test failure appears:

1. Record it in `known_bugs`.
2. Inspect the failing path and recent changes.
3. Make the smallest plausible fix.
4. Rerun the failing command.
5. Repeat until fixed, unrelated, or blocked.

Avoid infinite loops. If the same failure persists after several distinct fixes, mark `blocked` with the exact missing information or environmental limitation.

Do not spend an entire run cycling through many variants of the same timed-out command. After two materially different attempts, either use a simpler verification path or record a blocker.

## Next-Step Selection

When the roadmap has no explicit next phase, choose from this priority order:

1. Fix failing tests or runtime errors.
2. Complete unfinished acceptance criteria.
3. Add missing tests for recently changed behavior.
4. Clean up obvious implementation debt introduced during the task.
5. Update concise project documentation for changed workflows.
6. Mark `done` when no useful objective-linked work remains.

Do not invent major new features just to keep working.

## Stop Conditions

Stop and mark `phase_status` as `blocked` when progress requires:

- credentials, accounts, API keys, private data, payment, or external approval
- destructive operations such as mass deletion, hard resets, or production migrations
- resolving conflicting requirements
- access to unavailable external services with no reasonable local substitute
- product/design decisions that cannot be inferred safely

Stop and mark `done` when:

- done criteria are satisfied
- relevant tests or checks have passed
- no clear objective-linked next action remains

## Bundled Resources

- `scripts/init_longrun_state.py`: initialize `.codex-longrun/` in a target project.
- `scripts/validate_state.py`: validate `.codex-longrun/state.json`.
- `references/state-schema.md`: state file schema and examples.
- `references/supervisor-protocol.md`: prompt and orchestration contract for external supervisor processes.
- `references/execution-spec.md`: automatic invocation rules for normal Codex conversations.
