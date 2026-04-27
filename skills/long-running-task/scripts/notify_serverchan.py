#!/usr/bin/env python3
"""Send a ServerChan notification for long-running task review."""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


API_TEMPLATE = "https://sctapi.ftqq.com/{sendkey}.send"
SECRET_FILE = Path.home() / ".codex" / "secrets" / "serverchan_sendkey.txt"


def load_sendkey() -> str:
    if os.environ.get("SCT_SENDKEY"):
        return os.environ["SCT_SENDKEY"]
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text(encoding="utf-8").strip()
    return ""


def _read_state(project: Path) -> dict:
    state_path = project / ".codex-longrun" / "state.json"
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _build_message(args: argparse.Namespace, state: dict) -> str:
    project = Path(args.project).resolve()
    objective = state.get("objective") or "long-running task"
    phase = state.get("current_phase") or "unknown"
    tests = state.get("tests_run") or []
    blockers = state.get("blockers") or []

    latest_test = "not recorded"
    if isinstance(tests, list) and tests:
        latest = tests[-1]
        if isinstance(latest, dict):
            latest_test = latest.get("command") or latest.get("result") or str(latest)
        else:
            latest_test = str(latest)

    blocker_text = ""
    if args.status == "blocked" and blockers:
        blocker_text = "\n\nBlocked by:\n" + "\n".join(f"- {item}" for item in blockers[:3])

    summary = args.message.strip() if args.message else "Codex has stopped and is waiting for manual review."

    return textwrap.dedent(
        f"""
        # {args.title}

        Project: `{project}`

        Status: `{args.status}`

        Objective: {objective}

        Current phase: `{phase}`

        Summary: {summary}

        Latest verification: {latest_test}

        Time: {datetime.now().isoformat(timespec="seconds")}
        {blocker_text}

        Please return to the computer and review the result.
        """
    ).strip()


def send(sendkey: str, title: str, short: str, desp: str, timeout: int) -> dict:
    data = urllib.parse.urlencode(
        {
            "title": title,
            "short": short,
            "desp": desp,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        API_TEMPLATE.format(sendkey=sendkey),
        data=data,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return {"code": -1, "message": "Non-JSON response", "raw": body}


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=".", help="Project path for the long-running task.")
    parser.add_argument("--status", default="stopped", choices=["done", "blocked", "stopped"])
    parser.add_argument("--title", default="长任务已停止，等待验收")
    parser.add_argument("--message", default="")
    parser.add_argument("--short", default="Codex 长任务需要人工查看")
    parser.add_argument("--sendkey", default=load_sendkey())
    parser.add_argument("--timeout", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    project = Path(args.project).resolve()
    state = _read_state(project)
    desp = _build_message(args, state)

    if not args.sendkey:
        print(
            json.dumps(
                {
                    "code": -1,
                    "message": "Missing SendKey. Set SCT_SENDKEY, pass --sendkey, or create ~/.codex/secrets/serverchan_sendkey.txt.",
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    if args.dry_run:
        print(json.dumps({"dry_run": True, "title": args.title, "short": args.short, "desp": desp}, ensure_ascii=False))
        return 0

    try:
        result = send(args.sendkey, args.title, args.short, desp, args.timeout)
    except urllib.error.URLError as exc:
        print(json.dumps({"code": -1, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("code") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
