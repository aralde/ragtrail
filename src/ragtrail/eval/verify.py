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

_PROMPT_V1 = """\
For each item, read the question, the answer, and the sources the answer cites.

- "supported": the answer addresses the question, and its key claims or steps are stated in the sources.
- "unsupported": the answer misses the question, relies on facts the sources do not contain, contradicts
  them, or the sources are about something else.

Judge only against the sources given. Do not use outside knowledge.

Reply with a JSON array, one object per item:
{{"key": ..., "verdict": "supported" | "unsupported"}}

{items}"""

_PROMPT_V2 = """\
For each item, read the question, the answer, and the sources the answer cites.

- "supported": the answer addresses the question, and its key claims or steps are stated in the sources.
- "unsupported": the answer misses the question, relies on facts the sources do not contain, contradicts
  them, or the sources are about something else.
- Also "unsupported": the answer says or implies that the sources do not answer the question (for example
  "the docs don't cover this" or "I couldn't find"), even if what it does say is in the sources.

Judge only against the sources given. Do not use outside knowledge.

Reply with a JSON array, one object per item:
{{"key": ..., "verdict": "supported" | "unsupported"}}

{items}"""

PROMPTS = {"v1": _PROMPT_V1, "v2": _PROMPT_V2}
PROMPT = _PROMPT_V1  # the default; `v2` also rejects answers that say the sources do not cover the question

VERDICTS = ("supported", "unsupported")

# `claude -p` takes the prompt as one argv entry, which Linux caps at 128 KiB.
MAX_PROMPT_BYTES = 100_000


def _fit(item: dict[str, Any], limit: int, prompt_version: str = "v1") -> dict[str, Any]:
    """Trim the item's sources evenly so its prompt fits `limit` bytes (a fitting item is returned as is).

    >>> big = {"key": "k", "question": "q", "answer": "a", "sources": ["x" * 5000, "y" * 5000]}
    >>> len(verify_prompt([_fit(big, 3000)]).encode()) <= 3000
    True
    >>> _fit({"key": "k", "sources": ["s"]}, 3000)["sources"]
    ['s']
    """
    size = len(verify_prompt([item], prompt_version).encode())
    if size <= limit:
        return item
    excess = size - limit
    sources = list(item["sources"])
    total = sum(len(s) for s in sources)
    keep = max(0, total - excess - 64 * len(sources))
    trimmed = [s[: max(0, len(s) * keep // total)] + " …[trimmed]" for s in sources]
    return {**item, "sources": trimmed}


def batches(
    items: Sequence[dict[str, Any]],
    batch_size: int,
    limit: int = MAX_PROMPT_BYTES,
    prompt_version: str = "v1",
) -> list[list[dict[str, Any]]]:
    """Group items in order: at most `batch_size` and `limit` prompt bytes per batch; trim an oversized item.

    >>> small = {"key": "a", "question": "q", "answer": "a", "sources": ["s"]}
    >>> [len(b) for b in batches([small] * 7, 5)]
    [5, 2]
    >>> big = {**small, "sources": ["x" * 9000]}
    >>> [len(b) for b in batches([big] * 3, 5, limit=12000)]
    [1, 1, 1]
    """
    out: list[list[dict[str, Any]]] = []
    for item in items:
        item = _fit(item, limit, prompt_version)
        if (
            out
            and len(out[-1]) < batch_size
            and len(verify_prompt([*out[-1], item], prompt_version).encode()) <= limit
        ):
            out[-1].append(item)
        else:
            out.append([item])
    return out


def verify_prompt(items: Sequence[dict[str, Any]], prompt_version: str = "v1") -> str:
    """The prompt for one batch of `{key, question, answer, sources}` items; `v2` also rejects non-answers.

    >>> item = {"key": "k", "question": "q", "answer": "a", "sources": ["s"]}
    >>> "sources" in verify_prompt([item])
    True
    >>> marker = "do not answer the question"
    >>> marker in verify_prompt([item], "v2"), marker in verify_prompt([item])
    (True, False)
    """
    return PROMPTS[prompt_version].format(items=json.dumps(list(items), ensure_ascii=False, indent=1))


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
    prompt_version: str = "v1",
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
        for number, batch in enumerate(batches(shuffled, batch_size, prompt_version=prompt_version), start=1):
            out = parse_output(
                invoke(
                    text_command(verify_prompt(batch, prompt_version), model=model, system=SYSTEM), Path(tmp)
                )
            )
            got = parse_support(str(out.get("result") or ""), [i["key"] for i in batch])
            verdicts.update(got)
            echo(f"verified {len(got)}/{len(batch)} (batch {number})")
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
