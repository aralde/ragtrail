"""LLM judge: grades each answer against the reference, blind to the arm, in shuffled batches."""

from __future__ import annotations

import json
import random
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from ragtrail.eval.claude import Invoke, json_block, parse_output, run_claude, text_command

SYSTEM = "You grade answers to customer support questions against a reference answer. Reply with JSON only."

PROMPT = """\
For each item, compare the candidate answer with the reference answer for the question.

- "correct": the candidate gives the reference's key facts or steps, and nothing that contradicts it.
- "partial": some key facts or steps are right, but important ones are missing or vague.
- "incorrect": wrong, contradicts the reference, does not answer, or says the docs do not cover it when
  the reference does.

Extra correct detail is fine. Judge substance, not wording or length.

Reply with a JSON array, one object per item:
{{"key": ..., "verdict": "correct" | "partial" | "incorrect"}}

{items}"""

SCORES = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


def judge_prompt(items: Sequence[dict[str, str]]) -> str:
    """The prompt for one batch of `{key, question, reference, candidate}` items.

    >>> "candidate" in judge_prompt([{"key": "k", "question": "q", "reference": "r", "candidate": "c"}])
    True
    """
    return PROMPT.format(items=json.dumps(list(items), ensure_ascii=False, indent=1))


def parse_verdicts(output: str, keys: Sequence[str]) -> dict[str, str]:
    """Map key → verdict for the keys we asked about; unknown keys and verdicts are ignored.

    >>> parse_verdicts('[{"key": "a", "verdict": "partial"}, {"key": "z", "verdict": "correct"}]', ["a"])
    {'a': 'partial'}
    """
    wanted = set(keys)
    out = {}
    for item in json_block(output):
        key, verdict = str(item.get("key")), str(item.get("verdict"))
        if key in wanted and verdict in SCORES:
            out[key] = verdict
    return out


def judge_runs(
    items: Sequence[dict[str, str]],
    *,
    model: str = "haiku",
    batch_size: int = 10,
    seed: int = 0,
    invoke: Invoke = run_claude,
    echo: Callable[[str], None] = print,
) -> dict[str, str]:
    """Grade items (each with an opaque `key`) in seeded shuffled batches; returns key → verdict."""
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    verdicts: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="ragtrail-judge-") as tmp:
        for start in range(0, len(shuffled), batch_size):
            batch = shuffled[start : start + batch_size]
            out: dict[str, Any] = parse_output(
                invoke(text_command(judge_prompt(batch), model=model, system=SYSTEM), Path(tmp))
            )
            got = parse_verdicts(str(out.get("result") or ""), [i["key"] for i in batch])
            verdicts.update(got)
            echo(f"judged {len(got)}/{len(batch)} (batch {start // batch_size + 1})")
    return verdicts
