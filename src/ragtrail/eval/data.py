"""Eval datasets: download WixQA (MIT), build the subforest corpus and normalized question splits.

Nothing is committed. Layout under `$RAGTRAIL_DATA` (default `~/.cache/ragtrail/datasets`):

    wixqa/raw/*.jsonl                  downloaded files, untouched
    wixqa/corpus.db                    subforest tree + chunks + FTS5 index
    wixqa/questions-<split>.jsonl      one `EvalQuestion` per line
"""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

WIXQA_BASE = "https://huggingface.co/datasets/Wix/WixQA/resolve/main"
WIXQA_SPLITS = ("wixqa_expertwritten", "wixqa_simulated", "wixqa_synthetic")
WARM_SPLITS = ("wixqa_simulated", "wixqa_synthetic")
TEST_SPLIT = "wixqa_expertwritten"

Downloader = Callable[[str, Path], None]


class EvalQuestion(BaseModel):
    """A question with its reference answer and gold documents as subforest short ids (`n123`).

    >>> EvalQuestion(id="q1", split="s", question="How?", answer="So.", gold=["n7"]).gold
    ['n7']
    """

    id: str
    split: str
    question: str
    answer: str
    gold: list[str] = Field(default_factory=list)
    source_id: str | None = None


def data_root() -> Path:
    """`$RAGTRAIL_DATA` or `~/.cache/ragtrail/datasets`.

    >>> isinstance(data_root(), Path)
    True
    """
    env = os.environ.get("RAGTRAIL_DATA")
    return Path(env).expanduser() if env else Path.home() / ".cache" / "ragtrail" / "datasets"


def http_download(url: str, dest: Path) -> None:  # pragma: no cover - network
    """Download `url` to `dest` atomically."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as out:
        while block := response.read(1 << 20):
            out.write(block)
    tmp.replace(dest)


def save_questions(path: Path, questions: list[EvalQuestion]) -> None:
    """Write questions as JSON lines."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(q.model_dump_json() + "\n" for q in questions), encoding="utf-8")


def load_questions(path: Path) -> list[EvalQuestion]:
    """Read questions written by `save_questions`."""
    with path.open(encoding="utf-8") as f:
        return [EvalQuestion.model_validate_json(line) for line in f if line.strip()]


def questions_path(root: Path, split: str) -> Path:
    """Where a split's normalized questions live.

    >>> questions_path(Path("/d"), "wixqa_simulated")
    PosixPath('/d/wixqa/questions-wixqa_simulated.jsonl')
    """
    return root / "wixqa" / f"questions-{split}.jsonl"


def corpus_path(root: Path) -> Path:
    """The subforest corpus DB of the WixQA knowledge base.

    >>> corpus_path(Path("/d"))
    PosixPath('/d/wixqa/corpus.db')
    """
    return root / "wixqa" / "corpus.db"


def prepare_wixqa(
    root: Path, download: Downloader = http_download, echo: Callable[[str], None] = print
) -> None:  # pragma: no cover - needs subforest and the downloaded data
    """Download the KB and the three question splits, then build `corpus.db` and the question files."""
    from subforest import TreeStore
    from subforest.eval.datasets import Dataset, build_wixqa
    from subforest.retrievers import FTS5Retriever

    dataset = Dataset("wixqa", root)
    for rel in ("wix_kb_corpus/wix_kb_corpus.jsonl", *(f"{s}/test.jsonl" for s in WIXQA_SPLITS)):
        name = rel.split("/")[0] + ".jsonl"
        if not (dataset.raw / name).exists():
            echo(f"downloading {rel}")
            download(f"{WIXQA_BASE}/{rel}", dataset.raw / name)
    for split in WIXQA_SPLITS:
        result, questions = build_wixqa(dataset, split)
        if not dataset.db.exists():
            echo(f"building {dataset.db}")
            with TreeStore(dataset.db) as store:
                result.write(store)
                FTS5Retriever(store).ensure_index()
        normalized = [
            EvalQuestion(
                id=q.id,
                split=split,
                question=q.question,
                answer=q.answer,
                gold=[f"n{d}" for d in q.gold_docs],
            )
            for q in questions
        ]
        save_questions(questions_path(root, split), normalized)
        echo(f"{split}: {len(normalized)} questions")
