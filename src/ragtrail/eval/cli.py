"""`ragtrail eval …`: fetch, paraphrase, offline, agent, judge, report. Needs subforest alongside."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ragtrail.embed import DEFAULT_MODEL
from ragtrail.eval.data import (
    QASPER_SPLIT,
    TEST_SPLIT,
    WARM_SPLITS,
    EvalQuestion,
    corpus_path,
    data_root,
    load_questions,
    questions_path,
    save_questions,
    titled,
)
from ragtrail.eval.offline import RecallRow

PARAPHRASE_SPLIT = "paraphrase"


_TITLED = re.compile(r'^About "(?P<title>.+?)": (?P<question>.*)$', re.DOTALL)


@dataclass(frozen=True)
class Scenario:
    dataset: str
    name: str
    description: str
    warm: tuple[str, ...]
    test: str
    dev: tuple[str, str] | None
    matched_first: bool
    trails: str = "oracle"
    cold_from: str | None = None


SCENARIOS = {
    ("wixqa", "disjoint"): Scenario(
        "wixqa",
        "disjoint",
        "Warm-up on WixQA-Simulated + WixQA-Synthetic (oracle trails citing their gold articles); test on "
        "WixQA-ExpertWritten. Different question sets: this measures how often real new questions repeat "
        "an earlier path.",
        WARM_SPLITS,
        TEST_SPLIT,
        ("wixqa_synthetic", "wixqa_simulated"),
        True,
    ),
    ("wixqa", "repeat"): Scenario(
        "wixqa",
        "repeat",
        "Repeat traffic: warm-up on WixQA-ExpertWritten (oracle trails); test on one model-written "
        "paraphrase of each of those questions. Overlap is by design; this measures the intended use "
        "case, the same question asked again in other words.",
        (TEST_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
    ),
    ("wixqa", "repeat-self"): Scenario(
        "wixqa",
        "repeat-self",
        "Repeat traffic without oracle: the agent first answers WixQA-ExpertWritten with an empty cache "
        "and calls `record` with the nodes it chose to cite (phase A); those self-recorded trails warm the "
        "cache; test on the same paraphrases as `repeat`. The cold arm is reused from `repeat` (identical "
        "condition).",
        (TEST_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
        trails="self",
        cold_from="repeat",
    ),
    ("qasper", "repeat"): Scenario(
        "qasper",
        "repeat",
        "Repeat traffic on long papers: warm-up on 400 QASPER test questions (one per paper, titled, oracle "
        "trails citing the sections that hold the evidence); test on one model-written paraphrase of each, "
        "with the same paper title.",
        (QASPER_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
    ),
}

CORPUS_NAMES = {"wixqa": "the Wix help center", "qasper": "a collection of NLP research papers"}
TEST_SPLITS = {"wixqa": TEST_SPLIT, "qasper": QASPER_SPLIT}
DATASET_TITLES = {
    "wixqa": "WixQA (MIT), help-center KB of 6,221 articles",
    "qasper": "QASPER test split (CC BY 4.0), 416 NLP papers; 400 titled questions with located evidence",
}


def _scenario(args: argparse.Namespace) -> Scenario:
    try:
        return SCENARIOS[(args.dataset, args.scenario)]
    except KeyError:
        raise SystemExit(f"error: no scenario {args.scenario!r} for dataset {args.dataset!r}") from None


def _run(args: argparse.Namespace, sc: Scenario) -> str:
    return sc.name + ("-embed" if getattr(args, "embed", None) else "")


def _dir(args: argparse.Namespace) -> Path:
    return Path(args.data) / str(args.dataset)


def _questions(args: argparse.Namespace, splits: tuple[str, ...] | str) -> list[EvalQuestion]:
    names = (splits,) if isinstance(splits, str) else splits
    return [q for s in names for q in load_questions(questions_path(args.data, s, args.dataset))]


def _rows(args: argparse.Namespace, run: str) -> list[RecallRow]:
    data = json.loads((_dir(args) / f"offline-{run}.json").read_text(encoding="utf-8"))
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
    from ragtrail.eval.data import prepare_qasper, prepare_wixqa

    (prepare_qasper if args.dataset == "qasper" else prepare_wixqa)(args.data)
    return 0


def cmd_paraphrase(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    from ragtrail.eval.paraphrase import paraphrase_all

    out = questions_path(args.data, PARAPHRASE_SPLIT, args.dataset)
    if out.exists() and not args.force:
        print(f"{out} exists (use --force to regenerate)")
        return 0
    originals = _questions(args, TEST_SPLITS[args.dataset])
    titles: dict[str, str] = {}
    bare = []
    for q in originals:  # paraphrase the question, keep the paper title verbatim
        m = _TITLED.match(q.question)
        if m:
            titles[q.id] = m["title"]
            q = q.model_copy(update={"question": m["question"]})
        bare.append(q)
    paraphrases = [
        p.model_copy(update={"question": titled(titles[p.source_id], p.question)})
        if p.source_id in titles
        else p
        for p in paraphrase_all(bare, model=args.model)
    ]
    save_questions(out, paraphrases)
    print(f"wrote {len(paraphrases)} paraphrases to {out}")
    return 0


def cmd_offline(args: argparse.Namespace) -> int:  # pragma: no cover - needs subforest and data
    from subforest import TreeStore

    from ragtrail.eval.offline import OfflineReport, best_matches, exact_duplicates, recall_rows, warm_up
    from ragtrail.match import DEFAULT_CONFIG
    from ragtrail.store import SQLiteStore
    from ragtrail.subforest import SubforestResolver

    sc = _scenario(args)
    embedder = None
    if args.embed:
        from ragtrail.embed import FastEmbedder

        embedder = FastEmbedder(args.embed)
    warm, test = _questions(args, sc.warm), _questions(args, sc.test)
    db = _dir(args) / f"trails-{_run(args, sc)}.db"
    db.unlink(missing_ok=True)
    with TreeStore(corpus_path(args.data, args.dataset)) as tree, SQLiteStore(db) as store:
        if sc.trails == "self":
            from ragtrail.eval.agent import load_runs
            from ragtrail.eval.offline import warm_from_records

            phase_a = load_runs(_dir(args) / f"runs-{_run(args, sc)}-phaseA.jsonl")
            records = [r for run in phase_a if run["status"] == "ok" for r in run.get("records", [])]
            admitted = warm_from_records(store, SubforestResolver(tree), records, "eval", embedder=embedder)
        else:
            admitted = warm_up(store, SubforestResolver(tree), warm, "eval", embedder=embedder)
    scratch = db.with_suffix(".scoring.db")
    shutil.copyfile(
        db, scratch
    )  # recall bumps hit counters; score on a copy so the warm store stays as built
    with TreeStore(corpus_path(args.data, args.dataset)) as tree, SQLiteStore(scratch) as store:
        rows = recall_rows(
            store, SubforestResolver(tree), test, "eval", budget_tokens=args.budget, embedder=embedder
        )
    scratch.unlink()
    dev = None
    if sc.dev is not None:
        dev = best_matches(_questions(args, sc.dev[0]), _questions(args, sc.dev[1]))
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
        embed_model=args.embed,
    )
    md = report.markdown()
    out = _dir(args)
    (out / f"offline-{_run(args, sc)}.json").write_text(
        json.dumps({"rows": [asdict(r) for r in rows]}, ensure_ascii=False), encoding="utf-8"
    )
    (out / f"offline-{_run(args, sc)}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def _pilot(args: argparse.Namespace, sc: Scenario) -> list[EvalQuestion]:
    from ragtrail.eval.agent import select_pilot

    by_id = {q.id: q for q in _questions(args, sc.test)}
    ids = select_pilot(_rows(args, _run(args, sc)), args.n, matched_first=sc.matched_first)
    return [by_id[i] for i in ids]


def cmd_agent(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    from ragtrail.eval.agent import AgentConfig, run_agent

    sc = _scenario(args)
    config = AgentConfig(
        model=args.model, max_calls=args.max_calls, embed=args.embed, corpus_name=CORPUS_NAMES[args.dataset]
    )
    run_agent(
        _pilot(args, sc),
        _dir(args) / f"runs-{_run(args, sc)}.jsonl",
        scenario=_run(args, sc),
        corpus=corpus_path(args.data, args.dataset).resolve(),
        warm_db=(_dir(args) / f"trails-{_run(args, sc)}.db").resolve(),
        config=config,
        max_runs=args.max_runs,
        arms=("warm",) if sc.cold_from else ("cold", "warm"),
    )
    return 0


def cmd_selfrecord(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    """Phase A of a self-trail scenario: answer the warm questions with an empty cache and let the agent
    record its own trails."""
    from ragtrail.eval.agent import AgentConfig, run_agent

    sc = _scenario(args)
    if sc.trails != "self":
        raise SystemExit(f"error: scenario {sc.name!r} uses oracle trails; nothing to self-record")
    config = AgentConfig(
        model=args.model,
        max_calls=args.max_calls,
        embed=args.embed,
        corpus_name=CORPUS_NAMES[args.dataset],
        allow_record=True,
    )
    run_agent(
        _questions(args, sc.warm),
        _dir(args) / f"runs-{_run(args, sc)}-phaseA.jsonl",
        scenario=f"{_run(args, sc)}-phaseA",
        corpus=corpus_path(args.data, args.dataset).resolve(),
        warm_db=Path("/nonexistent"),
        config=config,
        max_runs=args.max_runs,
        arms=("cold",),
    )
    return 0


def cmd_judge(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    from ragtrail.eval.agent import load_runs
    from ragtrail.eval.judge import judge_runs
    from ragtrail.eval.report import judge_key

    sc = _scenario(args)
    run_name = _run(args, sc) + ("-phaseA" if args.phase_a else "")
    by_id = {q.id: q for q in _questions(args, sc.warm if args.phase_a else sc.test)}
    path = _dir(args) / f"judgments-{run_name}.{args.model}.json"
    verdicts: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    items = []
    for run in load_runs(_dir(args) / f"runs-{run_name}.jsonl"):
        key = judge_key(run_name, run["id"], run["arm"])
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

    doc_of = _doc_of(corpus_path(args.data, args.dataset))
    parts = [
        f"# ragtrail eval — {args.dataset}, cold vs warm",
        "",
        f"Generated by `ragtrail eval --dataset {args.dataset} report`. "
        f"Dataset: {DATASET_TITLES[args.dataset]}, built with subforest. Offline sections use no LLM. "
        f"Answers judged by `{args.judge}` via `claude -p`, blind to the arm.",
        "",
        "How to read the agent runs:",
        "",
        "- Question selection is **matched first**: every test question whose warm recall was not a miss, "
        "then seeded random misses up to `--n`. When `--n` covers the whole test set, that is all questions.",
        "- Both arms use the same model, tools, prompt and call cap; only the trail store differs.",
        "- Questions that miss in both arms run under identical conditions, so their cold→warm change is "
        "run-to-run noise: read it as the noise floor.",
        "",
    ]
    for (dataset, name), sc in SCENARIOS.items():
        if dataset != args.dataset:
            continue
        for suffix, matcher in (("", "lexical MinHash"), ("-embed", "lexical + embeddings")):
            run = name + suffix
            offline = _dir(args) / f"offline-{run}.md"
            if not offline.exists():
                continue
            title = f"## Scenario: {name} — {matcher}"
            parts.append(offline.read_text(encoding="utf-8").replace(f"## {name}", title, 1))
            runs = load_runs(_dir(args) / f"runs-{run}.jsonl")
            if runs:
                jpath = _dir(args) / f"judgments-{run}.{args.judge}.json"
                verdicts = json.loads(jpath.read_text()) if jpath.exists() else {}
                keys = None
                if sc.cold_from:
                    cold_run = sc.cold_from + suffix
                    runs = [r for r in runs if r["arm"] != "cold"] + [
                        r for r in load_runs(_dir(args) / f"runs-{cold_run}.jsonl") if r["arm"] == "cold"
                    ]
                    cpath = _dir(args) / f"judgments-{cold_run}.{args.judge}.json"
                    verdicts = {**(json.loads(cpath.read_text()) if cpath.exists() else {}), **verdicts}
                    keys = {"cold": cold_run}
                paired = pair_runs(run, runs, _questions(args, sc.test), doc_of, verdicts, keys)
                models = ", ".join(sorted({r["model"] for r in runs}))
                parts += [f"### Agent runs ({name}, {matcher})", "", agent_markdown(paired, models)]
    text = "\n".join(parts)
    out = args.out or Path(f"reports/{args.dataset}-eval.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    return 0


def add_eval_parser(sub: Any) -> None:
    """Register `ragtrail eval` and its subcommands on the main parser's subparsers."""
    ev = sub.add_parser("eval", help="cold vs warm evaluation on WixQA or QASPER (needs subforest)")
    ev.add_argument("--data", type=Path, default=data_root(), help="data root (default $RAGTRAIL_DATA)")
    ev.add_argument("--dataset", choices=sorted(CORPUS_NAMES), default="wixqa")
    cmds = ev.add_subparsers(dest="eval_command", required=True)
    cmds.add_parser("fetch", help="download WixQA and build the corpus").set_defaults(func=cmd_fetch)
    p = cmds.add_parser("paraphrase", help="write one paraphrase per test question (claude -p)")
    p.add_argument("--model", default="haiku")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_paraphrase)
    o = cmds.add_parser("offline", help="warm up and score recall without an LLM")
    o.add_argument("--scenario", choices=sorted({name for _, name in SCENARIOS}), required=True)
    o.add_argument("--budget", type=int, default=2000, help="recall token budget")
    o.add_argument("--embed", nargs="?", const=DEFAULT_MODEL, help="also match by embeddings (model)")
    o.set_defaults(func=cmd_offline)
    a = cmds.add_parser("agent", help="run the cold/warm agent pilot (claude -p)")
    a.add_argument("--scenario", choices=sorted({name for _, name in SCENARIOS}), required=True)
    a.add_argument("--n", type=int, default=20, help="pilot questions")
    a.add_argument("--max-runs", type=int, help="stop after this many runs (resume later)")
    a.add_argument("--max-calls", type=int, default=10)
    a.add_argument("--model", default="haiku")
    a.add_argument("--embed", nargs="?", const=DEFAULT_MODEL, help="warm arm also matches by embeddings")
    a.set_defaults(func=cmd_agent)
    sr = cmds.add_parser(
        "selfrecord", help="phase A: the agent answers warm questions and records its trails"
    )
    sr.add_argument("--scenario", default="repeat-self")
    sr.add_argument("--max-runs", type=int, help="stop after this many runs (resume later)")
    sr.add_argument("--max-calls", type=int, default=10)
    sr.add_argument("--model", default="haiku")
    sr.add_argument("--embed", nargs="?", const=DEFAULT_MODEL, help="same server flags as the warm runs")
    sr.set_defaults(func=cmd_selfrecord)
    j = cmds.add_parser("judge", help="grade pilot answers against references (claude -p)")
    j.add_argument("--scenario", choices=sorted({name for _, name in SCENARIOS}), required=True)
    j.add_argument("--model", default="sonnet", help="judge model")
    j.add_argument("--embed", nargs="?", const=DEFAULT_MODEL, help="judge the embeddings variant")
    j.add_argument("--phase-a", action="store_true", help="judge the self-record phase A answers")
    j.set_defaults(func=cmd_judge)
    r = cmds.add_parser("report", help="write the Markdown report")
    r.add_argument("--out", type=Path, help="default reports/<dataset>-eval.md")
    r.add_argument("--judge", default="sonnet", help="whose verdicts to report")
    r.set_defaults(func=cmd_report)
