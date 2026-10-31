"""Eval datasets: WixQA (MIT) and QASPER (CC BY 4.0) as subforest corpora plus normalized question splits.

Nothing is committed. Layout under `$RAGTRAIL_DATA` (default `~/.cache/ragtrail/datasets`):

    <dataset>/raw/...                    downloaded files, untouched
    <dataset>/corpus.db                  subforest tree + chunks + FTS5 index
    <dataset>/questions-<split>.jsonl    one `EvalQuestion` per line
"""

from __future__ import annotations

import os
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

WIXQA_BASE = "https://huggingface.co/datasets/Wix/WixQA/resolve/main"
WIXQA_SPLITS = ("wixqa_expertwritten", "wixqa_simulated", "wixqa_synthetic")
WARM_SPLITS = ("wixqa_simulated", "wixqa_synthetic")
TEST_SPLIT = "wixqa_expertwritten"
QASPER_TEST = "https://qasper-dataset.s3.us-west-2.amazonaws.com/qasper-test-and-evaluator-v0.3.tgz"
QASPER_SPLIT = "qasper_test"
QASPER_QUESTIONS = 400

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


def questions_path(root: Path, split: str, dataset: str = "wixqa") -> Path:
    """Where a split's normalized questions live.

    >>> questions_path(Path("/d"), "wixqa_simulated")
    PosixPath('/d/wixqa/questions-wixqa_simulated.jsonl')
    """
    return root / dataset / f"questions-{split}.jsonl"


def corpus_path(root: Path, dataset: str = "wixqa") -> Path:
    """The subforest corpus DB of a dataset.

    >>> corpus_path(Path("/d"), "qasper")
    PosixPath('/d/qasper/corpus.db')
    """
    return root / dataset / "corpus.db"


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


def titled(title: str, question: str) -> str:
    """QASPER questions are about one paper, so the question names it (as in subforest's titled mode).

    >>> titled("BERT", "Which corpus?")
    'About "BERT": Which corpus?'
    """
    return f'About "{title}": {question}'


def evidence_nodes(store: Any, doc: int, spans: list[tuple[int, int]]) -> list[str]:
    """Deepest section of `doc` holding each evidence span (else the doc), in order, deduplicated.

    >>> from types import SimpleNamespace as N
    >>> tree = {1: [N(id=2, span=(0, 50)), N(id=3, span=(50, 90))], 2: [N(id=4, span=(10, 40))], 3: [], 4: []}
    >>> evidence_nodes(N(children=tree.__getitem__), 1, [(12, 30), (60, 70), (5, 45)])
    ['n4', 'n3', 'n2']
    """
    out: list[str] = []
    for start, end in spans:
        node = doc
        while True:
            inner = [c for c in store.children(node) if c.span and c.span[0] <= start and end <= c.span[1]]
            if not inner:
                break
            node = inner[0].id
        if f"n{node}" not in out:
            out.append(f"n{node}")
    return out


def prepare_qasper(
    root: Path, download: Downloader = http_download, echo: Callable[[str], None] = print
) -> None:  # pragma: no cover - needs subforest and the downloaded data
    """Build the QASPER corpus and 400 titled questions (one per paper, with located evidence).

    Same selection as subforest's QASPER agent runs. Gold = the sections holding the evidence, which is what a
    verified answer would cite.
    """
    from subforest import TreeStore
    from subforest.eval.agent import select_questions
    from subforest.eval.datasets import Dataset, build_qasper
    from subforest.retrievers import FTS5Retriever

    dataset = Dataset("qasper", root)
    if not (dataset.raw / "qasper-test.tgz").exists():
        echo("downloading QASPER test split")
        download(QASPER_TEST, dataset.raw / "qasper-test.tgz")
    result, questions = build_qasper(dataset)
    if not dataset.db.exists():
        echo(f"building {dataset.db}")
        with TreeStore(dataset.db) as store:
            result.write(store)
            FTS5Retriever(store).ensure_index()
    picked = select_questions(questions, evidence_only=True, one_per_doc=True)[:QASPER_QUESTIONS]
    with TreeStore(dataset.db) as store:
        normalized = [
            EvalQuestion(
                id=q.id,
                split=QASPER_SPLIT,
                question=titled(q.context or "", q.question),
                answer=q.answer,
                gold=evidence_nodes(store, q.gold_docs[0], [(s.start, s.end) for s in q.gold_spans]),
            )
            for q in picked
        ]
    save_questions(questions_path(root, QASPER_SPLIT, "qasper"), normalized)
    echo(f"{QASPER_SPLIT}: {len(normalized)} questions")
