# codex_skill: Long Running Task

Reusable `codex_skill` plus a Python supervisor for state-driven long-running development tasks.

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

### Windows UTF-8 Note

On some Windows PowerShell consoles, UTF-8 Chinese text can appear garbled even when the repository files are correct.

Before treating garbled Chinese output as a repository bug:

- verify the file in VS Code or another UTF-8 aware editor
- prefer `Get-Content -Encoding utf8` when inspecting files in PowerShell
- use Python for a direct UTF-8 read when needed, for example `python -c "from pathlib import Path; print(Path(r'path/to/file').read_text(encoding='utf-8'))"`
- do not rewrite or save a file only because raw console output looks garbled

This is usually a terminal rendering issue, not a file corruption issue.

## Use

From a Codex conversation in the target project, say:

```text
Use long-running-task to keep developing the current project until it is done or blocked.
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
