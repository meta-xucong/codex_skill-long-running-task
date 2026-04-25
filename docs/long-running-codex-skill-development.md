# Long-Running Codex Skill Development Document

## 1. Goal

Build a reusable Codex skill and supporting local automation that lets Codex continue long-running development work across natural stopping points.

The system should:

- Follow a user-provided roadmap when one exists.
- Break large goals into phases when no roadmap exists.
- Implement one phase at a time.
- Run relevant tests after each phase.
- Debug and iterate automatically when tests fail.
- Move to the next phase after verification passes.
- When no explicit next phase exists, infer the most useful next step from the goal and current project state.
- Stop only when all reasonable development and verification work is complete, or when continuing requires a real user decision.

This should not be framed as a way to bypass Codex safety or product limits. The reliable architecture is a recoverable workflow:

- The skill defines the work protocol.
- A local supervisor process restarts or resumes work when Codex naturally stops.
- Persistent state files carry progress across turns and sessions.

## 2. Core Architecture

### 2.1 Skill Layer

The skill tells Codex how to behave during long-running work.

Responsibilities:

- Read the roadmap, state file, and recent logs at the start of every continuation.
- Maintain a phase-based execution loop.
- Prefer small, verifiable changes over large rewrites.
- Run tests before advancing.
- Record failures, fixes, and verification results.
- Decide whether the next action is implementation, debugging, test expansion, cleanup, or finalization.
- Stop only for explicit completion or a hard blocker.

Suggested skill name:

- `long-running-task`
- Alternative names: `continuous-dev`, `persistent-codex`, `codex-autopilot`

Recommended location:

- `C:\Users\兰落落的本本\.codex\skills\long-running-task`

Required skill files:

- `SKILL.md`
- `agents/openai.yaml`

Optional bundled resources:

- `scripts/init_longrun_state.py`
- `scripts/validate_state.py`
- `references/state-schema.md`
- `references/supervisor-protocol.md`

### 2.2 Persistent Project State

Each target project should get a local state directory, for example:

```text
.codex-longrun/
  state.json
  roadmap.md
  progress.md
  test-log.md
  decisions.md
  blockers.md
```

The state directory is the main continuity mechanism. It should be safe to read at the start of every new Codex turn.

Minimum `state.json` fields:

```json
{
  "objective": "",
  "current_phase": "",
  "phase_status": "discovering",
  "completed_phases": [],
  "next_actions": [],
  "tests_run": [],
  "known_bugs": [],
  "blockers": [],
  "done_criteria": [],
  "last_verified_at": ""
}
```

Recommended phase states:

- `discovering`
- `planning`
- `implementing`
- `testing`
- `debugging`
- `verifying`
- `advancing`
- `blocked`
- `done`

### 2.3 Supervisor Process

The supervisor is an external Python program that repeatedly invokes or resumes Codex.

Responsibilities:

- Start a Codex run with the long-running prompt.
- Detect when a Codex run exits or reaches a final answer.
- Inspect `.codex-longrun/state.json`.
- Decide whether to continue, stop, or report a blocker.
- Send a continuation prompt that asks Codex to read state and resume the loop.
- Record run metadata and exit reasons.

Preferred integration order:

1. Codex CLI non-interactive mode: `codex exec`
2. Codex CLI resume mode: `codex exec resume` or `codex resume --last`
3. Codex MCP server integration if a stronger orchestration path is needed.
4. UI automation only as a fallback.

The supervisor should avoid blindly sending "continue". It should send structured instructions:

```text
Continue the long-running task.
First read .codex-longrun/state.json, roadmap.md, progress.md, and test-log.md.
If the current phase is incomplete, finish and test it.
If tests fail, debug and rerun them.
If the phase is complete, select the next useful phase.
Stop only if done_criteria are satisfied or blockers require user input.
```

### 2.4 Safety and Stop Conditions

The system must allow Codex to stop when continued execution would be unsafe or speculative.

Hard stop conditions:

- Missing credentials, accounts, API keys, or private data.
- A destructive operation is required, such as mass deletion, `git reset --hard`, or production database migration.
- Requirements conflict and no reasonable assumption is safe.
- Tests require unavailable external services and no mock or local substitute is reasonable.
- The task is complete according to `done_criteria`.
- The supervisor reaches configured limits, such as max runs, max time, or max cost.

Soft stop conditions:

- Codex has no useful next step with a clear connection to the objective.
- Further work would be speculative feature creep.
- The project needs product/design approval rather than engineering execution.

## 3. Required Basic Components

### 3.1 Skill Package

Purpose:

- Make the long-running workflow discoverable and reusable inside Codex.

Needed:

- Skill metadata with a clear trigger description.
- Concise execution loop instructions.
- State file protocol.
- Stop condition rules.
- Test and debugging rules.

### 3.2 State Manager

Purpose:

- Create and validate `.codex-longrun/` files.

Needed:

- Initialize state from a user objective.
- Validate required keys and allowed phase states.
- Append progress and test summaries.
- Keep the schema simple enough that Codex can edit it safely.

### 3.3 Codex Runner Adapter

Purpose:

- Abstract how the supervisor talks to Codex.

Needed:

- `codex exec` adapter for non-interactive runs.
- `codex exec resume` or `codex resume --last` adapter for continuation.
- JSONL parsing support when `codex exec --json` is used.
- Fallback plain-text output parsing.

### 3.4 Idle and Completion Detector

Purpose:

- Decide whether a Codex stop means "done", "blocked", or "continue".

Needed:

- Read final assistant output.
- Read `.codex-longrun/state.json`.
- Treat `phase_status = done` as final only when done criteria are satisfied.
- Treat `phase_status = blocked` as a user-facing stop.
- Continue when there are pending phases, failing tests under active debugging, or useful next actions.

### 3.5 Test Runner Strategy

Purpose:

- Give Codex a repeatable way to verify each phase.

Needed:

- Detect project type where possible.
- Prefer existing project commands from package files, README, CI config, or previous logs.
- Record commands and results in `test-log.md`.
- Require re-running relevant tests after a fix.

### 3.6 Bug Iteration Loop

Purpose:

- Keep Codex working through failures without waiting for user input.

Needed:

- Capture failing command, error summary, suspected cause, attempted fix, and retest result.
- Limit repeated attempts on the same failure to avoid infinite loops.
- Escalate to `blocked` only after meaningful attempts or when missing information is required.

### 3.7 Prompt Templates

Purpose:

- Keep continuation behavior consistent.

Needed:

- Initial run prompt.
- Continuation prompt.
- Blocker-report prompt.
- Finalization prompt.

### 3.8 Logging

Purpose:

- Make long-running behavior auditable and recoverable.

Needed:

- Supervisor run log.
- Codex output log.
- State snapshots before and after each run.
- Test command history.

### 3.9 Configuration

Purpose:

- Avoid hardcoding behavior.

Needed:

- Target project path.
- Max iterations.
- Max runtime.
- Codex model/profile.
- Sandbox and approval policy.
- Whether to allow risky operations.
- Test command overrides.

### 3.10 Optional UI Automation Fallback

Purpose:

- Continue work in environments where CLI continuation is not enough.

Needed only if CLI/MCP cannot meet the goal:

- Window discovery.
- Focus management.
- Text injection.
- Idle detection by screenshot or accessibility tree.
- Strong safeguards against typing into the wrong window.

This should be treated as the least reliable path.

## 4. Local Environment Assessment

Checked workspace:

- Current workspace: `D:\AI\total_task_skill`
- Workspace is currently empty except for the new `docs/` directory.
- The workspace is not currently a Git repository.

Installed and available:

- Python: `Python 3.13.5`
- pip: `25.1.1`
- Git: `2.53.0.windows.1`
- Node.js: `v24.13.1`
- npm: `11.8.0`
- uv: `0.10.4`
- GitHub CLI: `2.87.2`
- Codex CLI: `codex-cli 0.118.0`
- Codex CLI supports `exec`, `exec resume`, `resume --last`, `mcp-server`, `--json`, and `--output-last-message`.

Codex directories:

- `CODEX_HOME` is not set.
- Default Codex directory exists: `C:\Users\兰落落的本本\.codex`
- Skills directory exists: `C:\Users\兰落落的本本\.codex\skills`
- Existing user skill: `polymarket-clob-v2-migration`
- System skills are present under `.system`

Python packages checked:

- `psutil`: available
- `yaml`: available
- `watchdog`: missing
- `pyautogui`: missing
- `pexpect`: missing

Tooling issue:

- `rg` is found at `C:\Program Files\WindowsApps\OpenAI.Codex_26.422.1952.0_x64__2p2nqsd0c76g0\app\resources\rg.exe`, but running it returns `Access is denied`.

## 5. Missing or Recommended Components

Required before implementation:

- Create the actual skill directory under `C:\Users\兰落落的本本\.codex\skills`.
- Create the supervisor script.
- Define the `.codex-longrun/state.json` schema.
- Add prompt templates.
- Add a minimal validation script for state files.
- Initialize this workspace as a Git repository if versioned development is desired.

Recommended but not strictly required:

- Fix or install a working `rg` binary for fast source search.
- Install `watchdog` if the supervisor should react to file changes.
- Add `pytest` if the supervisor scripts will have automated tests.
- Add a `pyproject.toml` for packaging the supervisor cleanly.

Only needed for UI automation fallback:

- Install `pyautogui` or another Windows UI automation library.
- Add safeguards for active-window checks.
- Add manual confirmation before enabling UI injection.

Probably not needed on Windows:

- `pexpect`, unless the design later targets Unix-like terminal automation.

## 6. Recommended MVP

The first version should avoid UI automation.

MVP components:

1. `long-running-task` Codex skill.
2. `.codex-longrun/` state protocol.
3. Python supervisor using `codex exec --json --output-last-message`.
4. Continuation loop based on `state.json`.
5. Max-iteration and max-runtime limits.
6. Basic logs and state snapshots.

MVP execution flow:

```text
User objective
  -> initialize .codex-longrun/state.json
  -> run codex exec with long-running skill prompt
  -> Codex updates code, runs tests, updates state
  -> supervisor reads final output and state
  -> continue if pending work remains
  -> stop if done or blocked
```

## 7. Implementation Plan

Phase 1: Create the skill

- Use the skill-creator workflow to initialize `long-running-task`.
- Write `SKILL.md` with the execution loop, state rules, test rules, and stop conditions.
- Generate `agents/openai.yaml`.
- Validate the skill.

Phase 2: Create state protocol

- Add `references/state-schema.md`.
- Add `scripts/init_longrun_state.py`.
- Add `scripts/validate_state.py`.
- Test scripts locally.

Phase 3: Create supervisor MVP

- Add a Python package or script in this workspace.
- Implement a Codex CLI adapter.
- Implement continuation decision logic.
- Implement logs and state snapshots.

Phase 4: Test on a small local project

- Use a toy repository with known failing tests.
- Verify Codex can implement, test, debug, update state, and continue.
- Verify it stops on `done` and `blocked`.

Phase 5: Harden

- Add config file support.
- Add retry limits per failure.
- Add better JSONL event parsing.
- Add optional file-watcher mode.
- Add optional UI automation fallback only if needed.

## 8. Open Design Questions

- Should the supervisor manage one Codex session with `resume`, or run fresh `codex exec` calls that rely entirely on state files?
- Should the skill be general-purpose, or tuned specifically for software development tasks?
- Should the default sandbox be `workspace-write`, `danger-full-access`, or user-configured?
- What default max iteration count and max runtime are acceptable?
- Should final "AI suggested next step" behavior be allowed to add new features, or limited to tests, cleanup, documentation, and obvious gaps?

## 9. Current Recommendation

Proceed with a CLI-first MVP.

The local environment already has the most important pieces: Python, Codex CLI, Git, Node/npm, uv, and access to the Codex skills directory. The main missing pieces are project files, the actual skill, the supervisor, and a working `rg` command.

Do not start with UI automation. It is more fragile and requires extra safety work. Build the state-driven CLI loop first, then add UI automation only if the CLI path cannot sustain the desired workflow.

## 10. MVP Implementation Status

Implemented:

- Codex skill: `C:\Users\兰落落的本本\.codex\skills\long-running-task`
- Skill helper scripts:
  - `scripts/init_longrun_state.py`
  - `scripts/validate_state.py`
- Skill references:
  - `references/state-schema.md`
  - `references/supervisor-protocol.md`
  - `references/execution-spec.md`
- Local supervisor package:
  - `src/longrun_supervisor/config.py`
  - `src/longrun_supervisor/state.py`
  - `src/longrun_supervisor/events.py`
  - `src/longrun_supervisor/doctor.py`
  - `src/longrun_supervisor/report.py`
  - `src/longrun_supervisor/prompts.py`
  - `src/longrun_supervisor/codex_cli.py`
  - `src/longrun_supervisor/cli.py`
- Example config:
  - `examples/longrun.toml`
- Unit tests:
  - `tests/test_state.py`
  - `tests/test_config.py`
  - `tests/test_events.py`
  - `tests/test_report.py`

Verified:

- Skill validates with `quick_validate.py`.
- Skill state helper validates `.codex-longrun/state.json`.
- Supervisor package compiles.
- Supervisor state tests pass.
- Supervisor dry-run emits the expected initial prompt without launching Codex.
- Real `codex exec` integration passes on `.tmp/codex-supervisor-check-smoke`: the nested Codex fixed a failing `math_tools.add`, verified with `cmd /c python check.py`, updated `.codex-longrun/state.json` to `done`, and the supervisor stopped.
- JSON and TOML config loading works, including UTF-8 BOM TOML files produced by Windows PowerShell.
- JSONL event parsing summarizes thread id, agent messages, command executions, command failures, file changes, and malformed lines.
- Repeated failure signatures are tracked across runs to stop unproductive loops.
- `doctor` checks Python, Codex CLI, skill installation, project state, and ripgrep availability.
- `report` prints current long-run state and the latest run summary.
- Skill invocation now has an automatic supervisor execution spec: normal Codex conversations use the current working directory as the project path and start `supervisor.py` without requiring the user to paste the long command.
- Supervisor-managed Codex runs include `SUPERVISOR_WORKER_MODE` and `LONGRUN_SUPERVISOR_WORKER=1` to prevent recursive supervisor launches.

Not implemented yet:

- File watcher mode.
- UI automation fallback.

Known integration issue:

- A pytest-based disposable fixture exposed a nested Codex shell timeout on Windows: `pytest` printed test results but did not exit cleanly inside the nested sandbox. The supervisor now reports Codex run timeouts cleanly instead of raising a Python traceback, and the skill now instructs Codex to avoid cycling indefinitely on repeated timed-out test commands.

## 11. Supervisor Usage

Initialize a target project:

```powershell
python supervisor.py --project D:\path\to\project init --objective "Build and verify the requested feature"
```

Run with command-line options:

```powershell
python supervisor.py --project D:\path\to\project run --max-iterations 5 --sandbox workspace-write --full-auto
```

Run with config:

```powershell
python supervisor.py run --config examples\longrun.toml
```

Config supports JSON or TOML. Use `[run]` for supervisor limits and `[codex]` for Codex CLI settings.

Diagnose the local environment:

```powershell
python supervisor.py --project D:\path\to\project doctor
```

Print the current state and latest Codex run summary:

```powershell
python supervisor.py --project D:\path\to\project report
```

Use `doctor --strict` when warnings should produce a non-zero exit code.

## 12. Short Natural Language Invocation

After this skill is installed, the intended user prompt can be short:

```text
使用 long-running-task 继续长期任务
```

or:

```text
使用 long-running-task 持续开发当前项目，直到完成或遇到 blocker
```

The skill should then:

1. Treat the current Codex working directory as the project path.
2. Run `python D:\AI\total_task_skill\supervisor.py --project . doctor`.
3. Inspect status.
4. Initialize state when missing, done, blocked, or mismatched.
5. Start `supervisor.py run` with long-running defaults.

Inside supervisor-managed worker runs, Codex must not start another supervisor. It should execute the skill's Operating Loop directly.
