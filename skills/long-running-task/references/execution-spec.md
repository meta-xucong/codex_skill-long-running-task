# Long-Running Task Execution Spec

This file defines what Codex should do when the user invokes `long-running-task` in a normal Codex conversation.

## Invocation Contract

Trigger this mode when the user says things like:

- "use long-running-task"
- "continue task"
- "keep developing"
- "do not stop between phases"
- "run until done"
- "continue optimizing"

The user should not need to paste a long command. The skill should infer the project path and objective.

## Project Path Rule

Use the current Codex working directory as the target project path.

Only use another project path when the user explicitly provides one.

Use `--project .` in commands when running from the target project directory. This lets Codex naturally match the current task path.

## Windows Encoding Guardrail

On Windows PowerShell, UTF-8 Chinese text may appear garbled in console output even when the underlying file is correct.

If `SKILL.md`, `notify_serverchan.py`, or related files look garbled:

1. Re-check with a UTF-8 aware reader such as VS Code, `Get-Content -Encoding utf8`, or Python `Path(...).read_text(encoding="utf-8")`.
2. Treat raw-console mojibake as a display issue unless the direct UTF-8 read is also wrong.
3. Do not patch or rewrite the file solely based on the console rendering.

## Objective Rule

Choose the objective in this order:

1. The explicit objective in the user's latest message.
2. The current `.codex-longrun/state.json` objective, if it exists and is not done or blocked.
3. A concise inferred objective from the user's latest request and visible project context.

Do not ask for an objective unless no safe inference is possible.

## Normal Conversation Startup

From a normal Codex conversation, prefer the bundled launcher when the user wants the task to run until completion or the run may outlive the current tool-call timeout:

```powershell
python "%USERPROFILE%\.codex\skills\long-running-task\scripts\run_until_complete.py" --project . --objective "<objective>" --detach
```

Use foreground mode only when the expected run is short enough to wait for:

```powershell
python "%USERPROFILE%\.codex\skills\long-running-task\scripts\run_until_complete.py" --project . --objective "<objective>"
```

After a detached launch, tell the user the PID, log path, and how to monitor:

```powershell
python -m longrun_supervisor --project . status
python -m longrun_supervisor --project . report
```

If the launcher is unavailable, execute this manual flow:

```powershell
python -m longrun_supervisor --project . doctor
python -m longrun_supervisor --project . status
```

If state is missing, `done`, `blocked`, or about a different objective:

```powershell
python -m longrun_supervisor --project . init --objective "<objective>" --force
```

Then run:

```powershell
python -m longrun_supervisor --project . run --max-iterations 999999 --max-runtime-seconds 0 --per-run-timeout-seconds 1800 --max-stagnant-runs 999999 --sandbox workspace-write --full-auto
```

## Supervisor Worker Mode

Do not start `supervisor.py` when already inside a supervisor-managed Codex run.

Treat either of these as a worker-mode marker:

- the prompt contains `SUPERVISOR_WORKER_MODE`
- the environment contains `LONGRUN_SUPERVISOR_WORKER=1`

In worker mode, follow `SKILL.md` directly:

1. Read `.codex-longrun/state.json`.
2. Continue the current phase.
3. Run tests.
4. Debug failures.
5. Update state and logs.
6. Stop only when state is `done` or `blocked`.

## Stop Boundaries

The supervisor should keep going across normal phase boundaries, but it must still stop for:

- `phase_status = done`
- `phase_status = blocked`
- required credentials, payment, private data, or external account access
- destructive operations requiring user confirmation
- repeated unproductive failures that hit supervisor guardrails
- Codex product or runtime limits outside the skill's control

Before a normal conversation or supervisor-managed worker stops and hands control back to the user for review, send the ServerChan review reminder described in `SKILL.md` under "Manual Review Notification".

Do not promise literal infinite execution. Promise state-driven continuation until done or blocked.
