# Long-Running State Schema

Store state in `.codex-longrun/state.json` at the target project root.

## Required Fields

```json
{
  "objective": "Build and verify the requested feature.",
  "current_phase": "Discover project structure",
  "phase_status": "discovering",
  "completed_phases": [],
  "next_actions": [
    "Inspect project scripts and tests"
  ],
  "tests_run": [],
  "known_bugs": [],
  "blockers": [],
  "done_criteria": [
    "Implementation is complete",
    "Relevant tests pass"
  ],
  "last_verified_at": ""
}
```

## Allowed `phase_status` Values

- `discovering`
- `planning`
- `implementing`
- `testing`
- `debugging`
- `verifying`
- `advancing`
- `blocked`
- `done`

## Field Guidance

`objective`
: User-facing goal. Keep it stable unless the user changes scope.

`current_phase`
: The active phase Codex should continue first.

`phase_status`
: The current state machine value.

`completed_phases`
: Short names of phases that have passed verification.

`next_actions`
: Concrete next steps. Keep this list ordered.

`tests_run`
: Compact records of verification commands and results. Prefer objects:

```json
{
  "command": "npm test",
  "result": "failed",
  "summary": "LoginForm validation test failed",
  "timestamp": "2026-04-25T06:30:00+08:00"
}
```

`known_bugs`
: Bugs or failures under active debugging.

`blockers`
: Hard blockers requiring user input or unavailable external resources.

`done_criteria`
: Conditions required before `phase_status` may become `done`.

`last_verified_at`
: ISO-like timestamp for the last successful verification pass.

## Completion Rule

Treat the project as complete only when:

- `phase_status` is `done`
- `blockers` is empty
- `next_actions` is empty or contains only non-essential follow-up ideas
- recent relevant tests or checks are recorded in `tests_run`

## Blocked Rule

Use `blocked` only when Codex cannot continue safely. Include a specific blocker entry with:

- what is needed
- why it is needed
- what was already tried
- the exact user decision or resource required
