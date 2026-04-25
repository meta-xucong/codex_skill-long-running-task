from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunSettings:
    project: str = "."
    objective: str | None = None
    max_iterations: int = 5
    max_runtime_seconds: int = 0
    per_run_timeout_seconds: int = 0
    max_stagnant_runs: int = 2
    max_repeated_failure_runs: int = 3
    codex_bin: str = "codex"
    model: str | None = None
    sandbox: str | None = None
    full_auto: bool = False
    dangerously_bypass_approvals_and_sandbox: bool = False


RUN_KEYS = set(RunSettings.__dataclass_fields__)


def load_run_settings(path: str | Path | None) -> RunSettings:
    if not path:
        return RunSettings()

    config_path = Path(path).expanduser().resolve()
    raw = load_config_data(config_path)
    values: dict[str, Any] = {}

    # Accept either flat keys or grouped [run] / [codex] sections.
    merge_known(values, raw)
    if isinstance(raw.get("run"), dict):
        merge_known(values, raw["run"])
    if isinstance(raw.get("codex"), dict):
        merge_known(values, raw["codex"])

    unknown = sorted(key for key in values if key not in RUN_KEYS)
    if unknown:
        raise ValueError(f"Unknown run config keys in {config_path}: {', '.join(unknown)}")

    settings = RunSettings()
    return replace(settings, **coerce_values(values))


def load_config_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".json":
        return json.loads(path.read_text(encoding="utf-8-sig"))
    if suffix in {".toml", ".tml"}:
        return tomllib.loads(path.read_text(encoding="utf-8-sig"))

    raise ValueError(f"Unsupported config file extension: {path.suffix}")


def merge_known(target: dict[str, Any], source: dict[str, Any]) -> None:
    for key, value in source.items():
        if key in {"run", "codex"}:
            continue
        target[key] = value


def coerce_values(values: dict[str, Any]) -> dict[str, Any]:
    coerced: dict[str, Any] = {}
    int_keys = {
        "max_iterations",
        "max_runtime_seconds",
        "per_run_timeout_seconds",
        "max_stagnant_runs",
        "max_repeated_failure_runs",
    }
    bool_keys = {"full_auto", "dangerously_bypass_approvals_and_sandbox"}

    for key, value in values.items():
        if key in int_keys:
            coerced[key] = int(value)
        elif key in bool_keys:
            coerced[key] = coerce_bool(value)
        elif value is None:
            coerced[key] = None
        else:
            coerced[key] = str(value)

    return coerced


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    raise ValueError(f"Cannot coerce boolean value: {value!r}")


def apply_cli_overrides(settings: RunSettings, args: Any) -> RunSettings:
    values = settings.__dict__.copy()
    for key in RUN_KEYS:
        if hasattr(args, key):
            value = getattr(args, key)
            if value is not None:
                values[key] = value
    if getattr(args, "project", None) is not None:
        values["project"] = args.project
    return RunSettings(**values)
