"""Reference-free admission check: is an answer supported by the nodes it cites?

This is the gate a deployment could run before `record`: it sees the question, the answer and the current text
of the cited nodes, never a reference answer.
"""

from __future__ import annotations

import json
import random
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ragtrail.eval.claude import Invoke, json_block, parse_output, run_claude, text_command

SYSTEM = "You check whether answers are supported by the sources they cite. Reply with JSON only."

PROMPT = """\
For each item, read the question, the answer, and the sources the answer cites.

- "supported": the answer addresses the question, and its key claims or steps are stated in the sources.
- "unsupported": the answer misses the question, relies on facts the sources do not contain, contradicts
  them, or the sources are about something else.

Judge only against the sources given. Do not use outside knowledge.

Reply with a JSON array, one object per item:
{{"key": ..., "verdict": "supported" | "unsupported"}}

{items}"""

VERDICTS = ("supported", "unsupported")


def verify_prompt(items: Sequence[dict[str, Any]]) -> str:
    """The prompt for one batch of `{key, question, answer, sources}` items.

    >>> "sources" in verify_prompt([{"key": "k", "question": "q", "answer": "a", "sources": ["s"]}])
    True
    """
    return PROMPT.format(items=json.dumps(list(items), ensure_ascii=False, indent=1))


def parse_support(output: str, keys: Sequence[str]) -> dict[str, str]:
    """Map key → verdict for the keys asked about; anything else is ignored.

    >>> parse_support('[{"key": "a", "verdict": "supported"}, {"key": "b", "verdict": "maybe"}]', ["a", "b"])
    {'a': 'supported'}
    """
    wanted = set(keys)
    out = {}
    for item in json_block(output):
        key, verdict = str(item.get("key")), str(item.get("verdict"))
        if key in wanted and verdict in VERDICTS:
            out[key] = verdict
    return out


def verify_runs(
    items: Sequence[dict[str, Any]],
    *,
    model: str = "haiku",
    batch_size: int = 5,
    seed: int = 0,
    invoke: Invoke = run_claude,
    echo: Callable[[str], None] = print,
) -> dict[str, str]:
    """Check items in seeded shuffled batches; returns key → "supported" | "unsupported".

    >>> fake = lambda cmd, cwd: json.dumps({"result": '[{"key": "a", "verdict": "unsupported"}]'})
    >>> item = {"key": "a", "question": "q", "answer": "x", "sources": []}
    >>> verify_runs([item], invoke=fake, echo=lambda s: None)
    {'a': 'unsupported'}
    """
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    verdicts: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="ragtrail-verify-") as tmp:
        for start in range(0, len(shuffled), batch_size):
            batch = shuffled[start : start + batch_size]
            out = parse_output(
                invoke(text_command(verify_prompt(batch), model=model, system=SYSTEM), Path(tmp))
            )
            got = parse_support(str(out.get("result") or ""), [i["key"] for i in batch])
            verdicts.update(got)
            echo(f"verified {len(got)}/{len(batch)} (batch {start // batch_size + 1})")
    return verdicts


def agreement(gate: dict[str, str], judged: dict[str, str]) -> dict[tuple[str, str], int]:
    """Count (gate verdict, judge verdict) pairs over ids both have.

    >>> agreement({"a": "supported", "b": "unsupported"}, {"a": "correct", "b": "correct", "c": "partial"})
    {('supported', 'correct'): 1, ('unsupported', 'correct'): 1}
    """
    counts: dict[tuple[str, str], int] = {}
    for key in sorted(gate.keys() & judged.keys()):
        pair = (gate[key], judged[key])
        counts[pair] = counts.get(pair, 0) + 1
    return counts
