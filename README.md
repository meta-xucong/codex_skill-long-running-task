# Codex Long Running Task

Reusable Codex skill plus a Python supervisor for state-driven long-running development tasks.

The skill teaches Codex how to continue through phases, run tests, debug failures, and stop only when the task is done or blocked. The supervisor handles the outer loop by repeatedly invoking Codex with persistent `.codex-longrun/` state.

## Contents

- `skills/long-running-task/`: Codex skill to install under your Codex skills directory.
- `supervisor.py`: local convenience entry point.
- `src/longrun_supervisor/`: Python supervisor package.
- `examples/longrun.toml`: example run configuration.
- `docs/long-running-codex-skill-development.md`: design and implementation notes.
- `tests/`: unit tests.

## Install

Clone the repository, then install the supervisor package:

```powershell
pip install -e .
```

Install the skill by copying it into your Codex skills directory:

```powershell
$dest = Join-Path $env:USERPROFILE ".codex\skills\long-running-task"
Remove-Item -LiteralPath $dest -Recurse -Force -ErrorAction SilentlyContinue
Copy-Item -LiteralPath ".\skills\long-running-task" -Destination $dest -Recurse
```

Restart Codex or open a new Codex conversation so the skill metadata is reloaded.

## Use

From a Codex conversation in the target project, say:

```text
使用 long-running-task 持续开发当前项目，直到完成或遇到 blocker
```

The skill uses the current working directory as the project path by default.

You can also run the supervisor directly:

```powershell
python supervisor.py --project D:\path\to\project init --objective "Build and verify the requested feature"
python supervisor.py --project D:\path\to\project run --max-iterations 10 --sandbox workspace-write --full-auto
```

Environment diagnostics:

```powershell
python supervisor.py --project D:\path\to\project doctor
```

Current state and latest run report:

```powershell
python supervisor.py --project D:\path\to\project report
```

## Safety

This project does not bypass Codex safety boundaries or product/runtime limits. It keeps working across normal phase boundaries, but still stops for done state, blockers, missing credentials, destructive operations, repeated unproductive failures, or external limits.
