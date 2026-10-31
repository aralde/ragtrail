"""Running `claude -p` (the user's subscription) for paraphrasing, agent runs and judging."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

_LIMIT = re.compile(
    r"usage limit|session limit|rate limit|limit reached|limit will reset|resets \d|out of extra usage",
    re.IGNORECASE,
)

Invoke = Callable[[list[str], Path], str]


class UsageLimitReached(Exception):
    """The subscription's usage window is spent; rerun later and the runner resumes."""


def run_claude(cmd: list[str], cwd: Path) -> str:  # pragma: no cover - needs the claude CLI
    """Run one `claude -p` command and return its stdout (a JSON object with `--output-format json`)."""
    done = subprocess.run(
        cmd, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=600, check=False
    )
    return done.stdout or json.dumps({"is_error": True, "result": done.stderr.strip()[-2000:]})


def parse_output(stdout: str) -> dict[str, Any]:
    """Parse `claude -p --output-format json`; raise `UsageLimitReached` when the window is spent.

    >>> parse_output('{"result": "hi", "is_error": false}')["result"]
    'hi'
    >>> parse_output("not json")["is_error"]
    True
    """
    try:
        out: dict[str, Any] = json.loads(stdout)
    except json.JSONDecodeError:
        out = {"is_error": True, "result": stdout[-2000:]}
    if out.get("is_error") and _LIMIT.search(str(out.get("result") or "")):
        raise UsageLimitReached(str(out.get("result")))
    return out


def text_command(prompt: str, *, model: str, system: str, claude: str = "claude") -> list[str]:
    """`claude -p` with no tools at all, for plain text tasks (paraphrasing, judging).

    >>> cmd = text_command("Hi", model="haiku", system="Be brief.")
    >>> cmd[:3], cmd[cmd.index("--tools") + 1]
    (['claude', '-p', 'Hi'], '')
    """
    return [
        claude,
        "-p",
        prompt,
        "--model",
        model,
        "--tools",
        "",
        "--strict-mcp-config",
        "--system-prompt",
        system,
        "--output-format",
        "json",
        "--no-session-persistence",
    ]


def json_block(text: str) -> Any:
    """Parse the first JSON array or object in `text` (models sometimes wrap it in a code fence).

    >>> json_block('Here:\\n```json\\n[{"id": "a"}]\\n```')
    [{'id': 'a'}]
    """
    starts = [i for i in (text.find("["), text.find("{")) if i >= 0]
    if not starts:
        raise ValueError("no JSON in model output")
    value, _ = json.JSONDecoder().raw_decode(text[min(starts) :])
    return value
