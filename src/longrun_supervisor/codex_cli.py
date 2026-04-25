from __future__ import annotations

import subprocess
import os
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodexRunResult:
    returncode: int
    stdout_path: Path
    stderr_path: Path
    last_message_path: Path
    command: list[str]
    timed_out: bool = False

    def last_message(self) -> str:
        if not self.last_message_path.exists():
            return ""
        return self.last_message_path.read_text(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class CodexCliOptions:
    codex_bin: str = "codex"
    model: str | None = None
    sandbox: str | None = None
    full_auto: bool = False
    dangerously_bypass_approvals_and_sandbox: bool = False


def build_codex_exec_command(
    options: CodexCliOptions,
    project: Path,
    last_message_path: Path,
) -> list[str]:
    codex_bin = resolve_codex_bin(options.codex_bin)
    command = [
        codex_bin,
        "exec",
        "--json",
        "--output-last-message",
        str(last_message_path),
        "--skip-git-repo-check",
        "-C",
        str(project),
    ]

    if options.model:
        command.extend(["--model", options.model])
    if options.sandbox:
        command.extend(["--sandbox", options.sandbox])
    if options.full_auto:
        command.append("--full-auto")
    if options.dangerously_bypass_approvals_and_sandbox:
        command.append("--dangerously-bypass-approvals-and-sandbox")

    command.append("-")
    return command


def resolve_codex_bin(codex_bin: str) -> str:
    """Resolve Codex executable, avoiding extensionless Windows shims."""
    path = Path(codex_bin)
    if path.is_absolute() or path.parent != Path("."):
        return codex_bin

    if os.name == "nt" and path.suffix == "":
        for candidate in (f"{codex_bin}.cmd", f"{codex_bin}.exe", f"{codex_bin}.bat"):
            resolved = shutil.which(candidate)
            if resolved:
                return resolved

    return shutil.which(codex_bin) or codex_bin


def run_codex_exec(
    *,
    project: Path,
    prompt: str,
    logs_dir: Path,
    run_id: str,
    options: CodexCliOptions,
    timeout_seconds: int | None = None,
) -> CodexRunResult:
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / f"{run_id}.jsonl"
    stderr_path = logs_dir / f"{run_id}.stderr.txt"
    last_message_path = logs_dir / f"{run_id}.last-message.md"
    command = build_codex_exec_command(options, project, last_message_path)

    env = os.environ.copy()
    env["LONGRUN_SUPERVISOR_WORKER"] = "1"

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_file:
        try:
            process = subprocess.run(
                command,
                cwd=project,
                input=prompt,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=stdout_file,
                stderr=stderr_file,
                timeout=timeout_seconds,
                env=env,
            )
            return CodexRunResult(
                returncode=process.returncode,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                last_message_path=last_message_path,
                command=command,
            )
        except subprocess.TimeoutExpired:
            stderr_file.write(
                f"\nSupervisor timeout expired after {timeout_seconds} seconds.\n"
            )

    return CodexRunResult(
        returncode=124,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        last_message_path=last_message_path,
        command=command,
        timed_out=True,
    )
