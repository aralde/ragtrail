"""`ragtrail eval …`: fetch, paraphrase, offline, agent, judge, report. Needs subforest alongside."""

from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ragtrail.eval.data import (
    TEST_SPLIT,
    WARM_SPLITS,
    EvalQuestion,
    corpus_path,
    data_root,
    load_questions,
    questions_path,
    save_questions,
)
from ragtrail.eval.offline import RecallRow

PARAPHRASE_SPLIT = "paraphrase"


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    warm: tuple[str, ...]
    test: str
    dev: tuple[str, str] | None
    matched_first: bool


SCENARIOS = {
    "disjoint": Scenario(
        "disjoint",
        "Warm-up on WixQA-Simulated + WixQA-Synthetic (oracle trails citing their gold articles); test on "
        "WixQA-ExpertWritten. Different question sets: this measures how often real new questions repeat "
        "an earlier path.",
        WARM_SPLITS,
        TEST_SPLIT,
        ("wixqa_synthetic", "wixqa_simulated"),
        True,
    ),
    "repeat": Scenario(
        "repeat",
        "Repeat traffic: warm-up on WixQA-ExpertWritten (oracle trails); test on one model-written "
        "paraphrase of each of those questions. Overlap is by design; this measures the intended use "
        "case, the same question asked again in other words.",
        (TEST_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
    ),
}


def _dir(root: Path) -> Path:
    return root / "wixqa"


def _questions(root: Path, splits: tuple[str, ...] | str) -> list[EvalQuestion]:
    names = (splits,) if isinstance(splits, str) else splits
    return [q for s in names for q in load_questions(questions_path(root, s))]


def _rows(root: Path, scenario: str) -> list[RecallRow]:
    data = json.loads((_dir(root) / f"offline-{scenario}.json").read_text(encoding="utf-8"))
    return [RecallRow(**{**r, "nodes": tuple(r["nodes"])}) for r in data["rows"]]


def _doc_of(corpus: Path) -> Any:  # pragma: no cover - needs subforest
    from subforest import TreeStore

    store = TreeStore(corpus)
    cache: dict[str, str | None] = {}

    def doc_of(node_id: str) -> str | None:
        if node_id not in cache:
            try:
                nid = int(node_id.lstrip("n"))
                chain = [*store.ancestors(nid), store.get_node(nid)]
            except (KeyError, ValueError):
                cache[node_id] = None
            else:
                cache[node_id] = next((f"n{n.id}" for n in reversed(chain) if n.kind == "doc"), None)
        return cache[node_id]

    return doc_of


def cmd_fetch(args: argparse.Namespace) -> int:  # pragma: no cover - network
    from ragtrail.eval.data import prepare_wixqa

    prepare_wixqa(args.data)
    return 0


def cmd_paraphrase(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    from ragtrail.eval.paraphrase import paraphrase_all

    out = questions_path(args.data, PARAPHRASE_SPLIT)
    if out.exists() and not args.force:
        print(f"{out} exists (use --force to regenerate)")
        return 0
    paraphrases = paraphrase_all(_questions(args.data, TEST_SPLIT), model=args.model)
    save_questions(out, paraphrases)
    print(f"wrote {len(paraphrases)} paraphrases to {out}")
    return 0


def cmd_offline(args: argparse.Namespace) -> int:  # pragma: no cover - needs subforest and data
    from subforest import TreeStore

    from ragtrail.eval.offline import OfflineReport, best_matches, exact_duplicates, recall_rows, warm_up
    from ragtrail.match import DEFAULT_CONFIG
    from ragtrail.store import SQLiteStore
    from ragtrail.subforest import SubforestResolver

    sc = SCENARIOS[args.scenario]
    warm, test = _questions(args.data, sc.warm), _questions(args.data, sc.test)
    db = _dir(args.data) / f"trails-{sc.name}.db"
    db.unlink(missing_ok=True)
    with TreeStore(corpus_path(args.data)) as tree, SQLiteStore(db) as store:
        admitted = warm_up(store, SubforestResolver(tree), warm, "eval")
    scratch = db.with_suffix(".scoring.db")
    shutil.copyfile(
        db, scratch
    )  # recall bumps hit counters; score on a copy so the warm store stays as built
    with TreeStore(corpus_path(args.data)) as tree, SQLiteStore(scratch) as store:
        rows = recall_rows(store, SubforestResolver(tree), test, "eval", budget_tokens=args.budget)
    scratch.unlink()
    dev = None
    if sc.dev is not None:
        dev = best_matches(_questions(args.data, sc.dev[0]), _questions(args.data, sc.dev[1]))
    report = OfflineReport(
        scenario=sc.name,
        description=sc.description,
        warm_count=len(warm),
        admitted=admitted,
        test_count=len(test),
        duplicates=exact_duplicates(warm, test),
        rows=rows,
        config=DEFAULT_CONFIG,
        budget_tokens=args.budget,
        dev_matches=dev,
        dev_label=f"{sc.dev[1]} queries against {sc.dev[0]}" if sc.dev else "",
    )
    md = report.markdown()
    out = _dir(args.data)
    (out / f"offline-{sc.name}.json").write_text(
        json.dumps({"rows": [asdict(r) for r in rows]}, ensure_ascii=False), encoding="utf-8"
    )
    (out / f"offline-{sc.name}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def _pilot(args: argparse.Namespace, sc: Scenario) -> list[EvalQuestion]:
    from ragtrail.eval.agent import select_pilot

    by_id = {q.id: q for q in _questions(args.data, sc.test)}
    ids = select_pilot(_rows(args.data, sc.name), args.n, matched_first=sc.matched_first)
    return [by_id[i] for i in ids]


def cmd_agent(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    from ragtrail.eval.agent import AgentConfig, run_agent

    sc = SCENARIOS[args.scenario]
    config = AgentConfig(model=args.model, max_calls=args.max_calls)
    run_agent(
        _pilot(args, sc),
        _dir(args.data) / f"runs-{sc.name}.jsonl",
        scenario=sc.name,
        corpus=corpus_path(args.data).resolve(),
        warm_db=(_dir(args.data) / f"trails-{sc.name}.db").resolve(),
        config=config,
        max_runs=args.max_runs,
    )
    return 0


def cmd_judge(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    from ragtrail.eval.agent import load_runs
    from ragtrail.eval.judge import judge_runs
    from ragtrail.eval.report import judge_key

    sc = SCENARIOS[args.scenario]
    by_id = {q.id: q for q in _questions(args.data, sc.test)}
    path = _dir(args.data) / f"judgments-{sc.name}.json"
    verdicts: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    items = []
    for run in load_runs(_dir(args.data) / f"runs-{sc.name}.jsonl"):
        key = judge_key(sc.name, run["id"], run["arm"])
        if run["status"] != "ok" or key in verdicts:
            continue
        q = by_id[run["id"]]
        items.append({"key": key, "question": q.question, "reference": q.answer, "candidate": run["answer"]})
    verdicts.update(judge_runs(items, model=args.model))
    path.write_text(json.dumps(verdicts, indent=1), encoding="utf-8")
    print(f"{len(verdicts)} verdicts in {path}")
    return 0


def cmd_report(args: argparse.Namespace) -> int:  # pragma: no cover - needs subforest and data
    from ragtrail.eval.agent import load_runs
    from ragtrail.eval.report import agent_markdown, pair_runs

    doc_of = _doc_of(corpus_path(args.data))
    parts = [
        "# ragtrail eval — WixQA, cold vs warm",
        "",
        "Generated by `ragtrail eval report`. Dataset: WixQA (MIT), help-center KB of 6,221 articles "
        "built with subforest. Offline sections use no LLM; agent sections are small pilots.",
        "",
        "How to read the agent pilots:",
        "",
        "- Pilots are **stratified**: every test question whose warm recall was not a miss, filled with "
        "seeded random misses. They show the effect *when the cache hits*; the population effect is roughly "
        "the hit rate from the offline table times the per-hit effect.",
        "- Both arms use the same model, tools, prompt and call cap; only the trail store differs.",
        "- Accuracy is judged by the same small model, blind to the arm. Questions that miss in both arms "
        "run under identical conditions, so their cold→warm change is pure run-to-run noise: read it as "
        "the noise floor.",
        "",
    ]
    for sc in SCENARIOS.values():
        offline = _dir(args.data) / f"offline-{sc.name}.md"
        if not offline.exists():
            continue
        parts.append(offline.read_text(encoding="utf-8").replace(f"## {sc.name}", f"## Scenario: {sc.name}"))
        runs = load_runs(_dir(args.data) / f"runs-{sc.name}.jsonl")
        if runs:
            jpath = _dir(args.data) / f"judgments-{sc.name}.json"
            verdicts = json.loads(jpath.read_text()) if jpath.exists() else {}
            paired = pair_runs(sc.name, runs, _questions(args.data, sc.test), doc_of, verdicts)
            models = ", ".join(sorted({r["model"] for r in runs}))
            parts += [f"### Agent pilot ({sc.name})", "", agent_markdown(paired, models)]
    text = "\n".join(parts)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(text)
    return 0


def add_eval_parser(sub: Any) -> None:
    """Register `ragtrail eval` and its subcommands on the main parser's subparsers."""
    ev = sub.add_parser("eval", help="cold vs warm evaluation on WixQA (needs subforest)")
    ev.add_argument("--data", type=Path, default=data_root(), help="data root (default $RAGTRAIL_DATA)")
    cmds = ev.add_subparsers(dest="eval_command", required=True)
    cmds.add_parser("fetch", help="download WixQA and build the corpus").set_defaults(func=cmd_fetch)
    p = cmds.add_parser("paraphrase", help="write one paraphrase per test question (claude -p)")
    p.add_argument("--model", default="haiku")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_paraphrase)
    o = cmds.add_parser("offline", help="warm up and score recall without an LLM")
    o.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    o.add_argument("--budget", type=int, default=2000, help="recall token budget")
    o.set_defaults(func=cmd_offline)
    a = cmds.add_parser("agent", help="run the cold/warm agent pilot (claude -p)")
    a.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    a.add_argument("--n", type=int, default=20, help="pilot questions")
    a.add_argument("--max-runs", type=int, help="stop after this many runs (resume later)")
    a.add_argument("--max-calls", type=int, default=10)
    a.add_argument("--model", default="haiku")
    a.set_defaults(func=cmd_agent)
    j = cmds.add_parser("judge", help="grade pilot answers against references (claude -p)")
    j.add_argument("--scenario", choices=sorted(SCENARIOS), required=True)
    j.add_argument("--model", default="haiku")
    j.set_defaults(func=cmd_judge)
    r = cmds.add_parser("report", help="write the Markdown report")
    r.add_argument("--out", type=Path, default=Path("reports/wixqa-eval.md"))
    r.set_defaults(func=cmd_report)
