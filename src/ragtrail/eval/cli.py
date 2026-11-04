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
TITLE_CONTEXT = r'^About ".+?": '


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
    phase_a_from: str | None = None
    gate: tuple[str, ...] | None = None
    gate_by: str = "judge"
    gate_model: str = "haiku"
    gate_prompt: str = "v1"
    scoped: bool = False


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
    ("wixqa", "repeat-gated"): Scenario(
        "wixqa",
        "repeat-gated",
        "Like `repeat-self`, but a trail is admitted only when its phase-A answer was judged correct (a "
        "stand-in for explicit user feedback; the judge sees the reference answer). Phase A and the cold arm "
        "are reused from `repeat-self` and `repeat`.",
        (TEST_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
        trails="self",
        cold_from="repeat",
        phase_a_from="repeat-self",
        gate=("correct",),
    ),
    ("wixqa", "repeat-verified"): Scenario(
        "wixqa",
        "repeat-verified",
        "Like `repeat-gated`, but the gate is reference-free: a trail is admitted only when a model, shown "
        "the question, the phase-A answer and the current text of the cited nodes (never the reference), "
        "says the answer is supported by them. Phase A and the cold arm are reused from `repeat-self` and "
        "`repeat`.",
        (TEST_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
        trails="self",
        cold_from="repeat",
        phase_a_from="repeat-self",
        gate=("supported",),
        gate_by="verify",
    ),
    ("wixqa", "repeat-verified-sonnet"): Scenario(
        "wixqa",
        "repeat-verified-sonnet",
        "Same as `repeat-verified` (reference-free gate on the cited nodes' current text), with Sonnet "
        "instead of Haiku as the verifier. Phase A and the cold arm are reused from `repeat-self` and "
        "`repeat`.",
        (TEST_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
        trails="self",
        cold_from="repeat",
        phase_a_from="repeat-self",
        gate=("supported",),
        gate_by="verify",
        gate_model="sonnet",
    ),
    ("wixqa", "repeat-verified-v2"): Scenario(
        "wixqa",
        "repeat-verified-v2",
        "Same as `repeat-verified`, with a verifier prompt that also rejects answers saying the cited nodes "
        "do not cover the question (v2). Phase A and the cold arm are reused from `repeat-self` and "
        "`repeat`.",
        (TEST_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
        trails="self",
        cold_from="repeat",
        phase_a_from="repeat-self",
        gate=("supported",),
        gate_by="verify",
        gate_prompt="v2",
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
    ("qasper", "repeat-self"): Scenario(
        "qasper",
        "repeat-self",
        "Realistic QASPER: each paper is its own scope and recall matches the question without the paper "
        "title. Phase A: the agent answers the 400 titled questions with an empty cache and records its own "
        "trails; test on the paraphrases. The cold arm is reused from `repeat` (no cache, same questions).",
        (QASPER_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
        trails="self",
        cold_from="repeat",
        scoped=True,
    ),
    ("qasper", "repeat-verified"): Scenario(
        "qasper",
        "repeat-verified",
        "Like QASPER `repeat-self`, but a trail is admitted only when a verifier (shown the question, the "
        "phase-A answer and the cited sections' current text, never the reference) says it is supported.",
        (QASPER_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
        trails="self",
        cold_from="repeat",
        phase_a_from="repeat-self",
        gate=("supported",),
        gate_by="verify",
        scoped=True,
    ),
    ("qasper", "repeat-verified-v2"): Scenario(
        "qasper",
        "repeat-verified-v2",
        "Same as QASPER `repeat-verified`, with a verifier prompt that also rejects answers saying the cited "
        "sections do not cover the question (v2).",
        (QASPER_SPLIT,),
        PARAPHRASE_SPLIT,
        None,
        True,
        trails="self",
        cold_from="repeat",
        phase_a_from="repeat-self",
        gate=("supported",),
        gate_by="verify",
        gate_prompt="v2",
        scoped=True,
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


def _phase_a_name(args: argparse.Namespace, sc: Scenario, embed: bool | None = None) -> str:
    """Run name of the phase A a self-trail scenario records (or reuses)."""
    embed = bool(getattr(args, "embed", None)) if embed is None else embed
    return (sc.phase_a_from or sc.name) + ("-embed" if embed else "") + "-phaseA"


def _phase_a_verdicts(
    args: argparse.Namespace, sc: Scenario, judge: str, embed: bool | None = None
) -> dict[str, str]:
    """Question id → how its phase-A answer was judged (empty if not judged yet)."""
    from ragtrail.eval.agent import load_runs
    from ragtrail.eval.report import judge_key

    name = _phase_a_name(args, sc, embed)
    path = _dir(args) / f"judgments-{name}.{judge}.json"
    if not path.exists():
        return {}
    verdicts: dict[str, str] = json.loads(path.read_text())
    runs = load_runs(_dir(args) / f"runs-{name}.jsonl")
    return {r["id"]: verdicts[k] for r in runs if (k := judge_key(name, r["id"], r["arm"])) in verdicts}


def _verify_path(args: argparse.Namespace, sc: Scenario, model: str, embed: bool | None = None) -> Path:
    suffix = "" if sc.gate_prompt == "v1" else f".{sc.gate_prompt}"
    return _dir(args) / f"verify-{_phase_a_name(args, sc, embed)}.{model}{suffix}.json"


def _gate_verdicts(args: argparse.Namespace, sc: Scenario) -> dict[str, str]:
    """Question id → gate verdict on its phase-A answer: the judge's, or the reference-free verifier's."""
    if sc.gate_by == "verify":
        path = _verify_path(args, sc, sc.gate_model)
        return dict(json.loads(path.read_text())) if path.exists() else {}
    return _phase_a_verdicts(args, sc, "sonnet")


def _scope_of(args: argparse.Namespace, sc: Scenario) -> Any:  # pragma: no cover - needs subforest
    """For a scoped scenario: question → "p<doc>" (the paper holding its first gold section); else None."""
    if not sc.scoped:
        return None
    doc_of = _doc_of(corpus_path(args.data, args.dataset))

    def scope_of(q: EvalQuestion) -> str:
        doc = doc_of(q.gold[0]) if q.gold else None
        if doc is None:
            raise SystemExit(f"error: no paper found for question {q.id}")
        return f"p{doc.lstrip('n')}"

    return scope_of


def _bare(text: str) -> str:
    """The question without its fixed title context.

    >>> _bare('About "BERT": Which datasets?')
    'Which datasets?'
    """
    return re.sub(TITLE_CONTEXT, "", text).strip()


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

            phase_a = load_runs(_dir(args) / f"runs-{_phase_a_name(args, sc)}.jsonl")
            runs = [run for run in phase_a if run["status"] == "ok"]
            if sc.gate:
                verdicts = _gate_verdicts(args, sc)
                if not verdicts:
                    step = "eval verify" if sc.gate_by == "verify" else "eval judge --phase-a"
                    raise SystemExit(f"error: no gate verdicts yet; run {step} first")
                runs = [run for run in runs if verdicts.get(run["id"]) in sc.gate]
            outcome = "feedback" if sc.gate else None
            scope_of = _scope_of(args, sc)
            by_id = {q.id: q for q in warm}
            admitted = 0
            for run in runs:
                scope = scope_of(by_id[run["id"]]) if scope_of else "eval"
                records = [
                    {
                        **r,
                        "query": _bare(str(r.get("query") or "")) if sc.scoped else r.get("query"),
                        "outcome": outcome or r.get("outcome"),
                    }
                    for r in run.get("records", [])
                ]
                admitted += warm_from_records(
                    store, SubforestResolver(tree), records, scope, embedder=embedder
                )
        else:
            admitted = warm_up(store, SubforestResolver(tree), warm, "eval", embedder=embedder)
    scratch = db.with_suffix(".scoring.db")
    shutil.copyfile(
        db, scratch
    )  # recall bumps hit counters; score on a copy so the warm store stays as built
    with TreeStore(corpus_path(args.data, args.dataset)) as tree, SQLiteStore(scratch) as store:
        scope_of = _scope_of(args, sc)
        doc_of = _doc_of(corpus_path(args.data, args.dataset))
        rows = [
            row
            for q in test
            for row in recall_rows(
                store,
                SubforestResolver(tree),
                [q.model_copy(update={"question": _bare(q.question)}) if sc.scoped else q],
                scope_of(q) if scope_of else "eval",
                budget_tokens=args.budget,
                embedder=embedder,
                doc_of=doc_of,
            )
        ]
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
        model=args.model,
        max_calls=args.max_calls,
        embed=args.embed,
        corpus_name=CORPUS_NAMES[args.dataset],
        strip_context=TITLE_CONTEXT if sc.scoped else None,
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
        scope_of=_scope_of(args, sc),
    )
    return 0


def cmd_selfrecord(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    """Phase A of a self-trail scenario: answer the warm questions with an empty cache and let the agent
    record its own trails."""
    from ragtrail.eval.agent import AgentConfig, run_agent

    sc = _scenario(args)
    if sc.trails != "self":
        raise SystemExit(f"error: scenario {sc.name!r} uses oracle trails; nothing to self-record")
    if sc.phase_a_from:
        raise SystemExit(f"error: scenario {sc.name!r} reuses phase A of {sc.phase_a_from!r}; record that")
    config = AgentConfig(
        model=args.model,
        max_calls=args.max_calls,
        embed=args.embed,
        corpus_name=CORPUS_NAMES[args.dataset],
        allow_record=True,
        strip_context=TITLE_CONTEXT if sc.scoped else None,
    )
    run_agent(
        _questions(args, sc.warm),
        _dir(args) / f"runs-{_phase_a_name(args, sc)}.jsonl",
        scenario=_phase_a_name(args, sc),
        corpus=corpus_path(args.data, args.dataset).resolve(),
        warm_db=Path("/nonexistent"),
        config=config,
        max_runs=args.max_runs,
        arms=("cold",),
        scope_of=_scope_of(args, sc),
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:  # pragma: no cover - needs subforest and the claude CLI
    """Reference-free gate: check each phase-A answer against the current text of the nodes it cited."""
    from subforest import TreeStore

    from ragtrail.eval.agent import load_runs
    from ragtrail.eval.verify import verify_runs
    from ragtrail.subforest import SubforestResolver

    sc = _scenario(args)
    if sc.gate_by != "verify":
        raise SystemExit(f"error: scenario {sc.name!r} is not gated by the verifier")
    model = args.model or sc.gate_model
    path = _verify_path(args, sc, model)
    done: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    by_id = {q.id: q for q in _questions(args, sc.warm)}
    items = []
    with TreeStore(corpus_path(args.data, args.dataset)) as tree:
        resolver = SubforestResolver(tree)
        for run in load_runs(_dir(args) / f"runs-{_phase_a_name(args, sc)}.jsonl"):
            if run["status"] != "ok" or run["id"] in done:
                continue
            cited = list(dict.fromkeys(c for r in run.get("records", []) for c in r.get("cited", [])))
            sources = [
                f"[{c}] {resolver.label(c)}\n{resolver.read(c, args.source_tokens)}"
                for c in cited
                if resolver.content_hash(c) is not None
            ]
            if not sources:
                done[run["id"]] = "unsupported"
                continue
            q = by_id[run["id"]]
            items.append(
                {"key": run["id"], "question": q.question, "answer": run["answer"], "sources": sources}
            )
    done.update(verify_runs(items, model=model, prompt_version=sc.gate_prompt))
    path.write_text(json.dumps(done, indent=1), encoding="utf-8")
    print(f"{len(done)} verdicts in {path}: {sum(v == 'supported' for v in done.values())} supported")
    return 0


def cmd_judge(args: argparse.Namespace) -> int:  # pragma: no cover - needs the claude CLI
    from ragtrail.eval.agent import load_runs
    from ragtrail.eval.judge import judge_runs
    from ragtrail.eval.report import judge_key

    sc = _scenario(args)
    run_name = _phase_a_name(args, sc) if args.phase_a else _run(args, sc)
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
    from ragtrail.eval.report import agent_markdown, group_markdown, pair_runs

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
                phase_a = (
                    _phase_a_verdicts(args, sc, args.judge, embed=bool(suffix)) if sc.trails == "self" else {}
                )
                if phase_a:
                    phase_a = {
                        q.id: v for q in _questions(args, sc.test) if (v := phase_a.get(q.source_id or q.id))
                    }
                    if sc.gate_by == "verify":
                        from ragtrail.eval.verify import agreement

                        gate_path = _verify_path(args, sc, sc.gate_model, embed=bool(suffix))
                        gate = json.loads(gate_path.read_text()) if gate_path.exists() else {}
                        raw = _phase_a_verdicts(args, sc, args.judge, embed=bool(suffix))
                        counts = agreement(gate, raw)
                        parts += [
                            "Gate verdicts against the judge's verdict on the same phase-A answer:",
                            "",
                            "| Gate | Judge | Answers |",
                            "|---|---|---|",
                            *(f"| {g} | {j} | {n} |" for (g, j), n in sorted(counts.items())),
                            "",
                        ]
                    parts += [
                        "By how the phase-A answer that recorded the trail was judged:",
                        "",
                        group_markdown(paired, phase_a, "Phase-A answer"),
                    ]
    text = "\n".join(parts)
    out = args.out or Path(f"reports/{args.dataset}-eval.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(text)
    return 0


def _robustness_items(
    args: argparse.Namespace,
) -> tuple[
    list[tuple[EvalQuestion, str]], list[tuple[EvalQuestion, str]], list[EvalQuestion]
]:  # pragma: no cover
    """(warm questions with scope, extra first-time questions with scope, paraphrases) for `edits`/`stream`.

    QASPER uses the paper as scope and matches the bare question (the fixed-context finding); its extra
    questions are the other evidence-backed questions on the same papers. WixQA uses one scope; its extra
    questions are WixQA-Simulated."""
    warm = _questions(args, TEST_SPLITS[args.dataset])
    paraphrases = _questions(args, PARAPHRASE_SPLIT)
    if args.dataset != "qasper":
        return (
            [(q, "eval") for q in warm],
            [(q, "eval") for q in _questions(args, "wixqa_simulated")],
            paraphrases,
        )
    from subforest import TreeStore
    from subforest.eval.datasets import Dataset, build_qasper

    from ragtrail.eval.data import evidence_nodes

    def bare(q: EvalQuestion) -> EvalQuestion:
        m = _TITLED.match(q.question)
        return q.model_copy(update={"question": m["question"]}) if m else q

    _, every = build_qasper(Dataset("qasper", args.data))
    by_id = {q.id: q for q in every}
    papers = {q.id: f"p{by_id[q.id].gold_docs[0]}" for q in warm}
    with TreeStore(corpus_path(args.data, "qasper")) as tree:
        extra = [
            (
                EvalQuestion(
                    id=q.id,
                    split="qasper_other",
                    question=q.question,
                    answer=q.answer,
                    gold=evidence_nodes(tree, q.gold_docs[0], [(s.start, s.end) for s in q.gold_spans]),
                ),
                f"p{q.gold_docs[0]}",
            )
            for q in every
            if q.id not in papers and q.gold_spans and f"p{q.gold_docs[0]}" in set(papers.values())
        ]
    paraphrased = [bare(p).model_copy(update={"split": PARAPHRASE_SPLIT}) for p in paraphrases]
    return [(bare(q), papers[q.id]) for q in warm], extra, paraphrased


def _embedder(args: argparse.Namespace) -> Any:  # pragma: no cover - downloads a model
    if not args.embed:
        return None
    from ragtrail.embed import FastEmbedder

    return FastEmbedder(args.embed)


def cmd_edits(args: argparse.Namespace) -> int:  # pragma: no cover - needs subforest and data
    from subforest import TreeStore

    from ragtrail.eval.offline import warm_up
    from ragtrail.eval.stream import edit_markdown, edit_rows
    from ragtrail.store import SQLiteStore
    from ragtrail.subforest import SubforestResolver

    embedder = _embedder(args)
    warm, _, paraphrases = _robustness_items(args)
    scope_of = {q.id: s for q, s in warm}
    test = [(p, scope_of[p.source_id or ""]) for p in paraphrases if p.source_id in scope_of]
    cited = sorted({g for q, _ in warm for g in q.gold})
    out = _dir(args)
    db = out / f"trails-edits{_suffix(args)}.db"
    db.unlink(missing_ok=True)
    with TreeStore(corpus_path(args.data, args.dataset)) as tree:
        resolver = SubforestResolver(tree)
        with SQLiteStore(db) as store:
            for q, scope in warm:
                warm_up(store, resolver, [q], scope, embedder=embedder)
        scratch = db.with_suffix(".scoring.db")

        def fresh() -> SQLiteStore:
            shutil.copyfile(db, scratch)
            return SQLiteStore(scratch)

        rows = edit_rows(
            fresh, resolver, test, cited, args.rates, budget_tokens=args.budget, embedder=embedder
        )
    scratch.unlink(missing_ok=True)
    md = "\n".join(
        [
            f"## Corpus edits — {args.dataset}{', embeddings' if embedder else ', lexical'}",
            "",
            f"Warm-up: {len(warm)} oracle trails. Test: {len(test)} paraphrased repeats. After recording, "
            f"a seeded random share of the {len(cited)} cited nodes is edited (nested across rates). The "
            "copy cache and the unvalidated pointer cache are assumed to match exactly as ragtrail does, so "
            "only freshness differs.",
            "",
            edit_markdown(rows),
        ]
    )
    (out / f"edits{_suffix(args)}.json").write_text(
        json.dumps({"rows": [asdict(r) for r in rows]}), encoding="utf-8"
    )
    (out / f"edits{_suffix(args)}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def cmd_stream(args: argparse.Namespace) -> int:  # pragma: no cover - needs subforest and data
    from subforest import TreeStore

    from ragtrail.eval.stream import build_stream, run_stream, stream_markdown
    from ragtrail.store import SQLiteStore
    from ragtrail.subforest import SubforestResolver

    embedder = _embedder(args)
    warm, extra, paraphrases = _robustness_items(args)
    new = warm + extra
    doc_of = _doc_of(corpus_path(args.data, args.dataset)) if args.dataset == "wixqa" else None
    by_rate = {}
    with TreeStore(corpus_path(args.data, args.dataset)) as tree:
        for rate in args.rates:
            events = build_stream(new, paraphrases, rate, seed=args.seed)
            with SQLiteStore(":memory:") as store:
                by_rate[rate] = run_stream(
                    store,
                    SubforestResolver(tree),
                    events,
                    budget_tokens=args.budget,
                    embedder=embedder,
                    doc_of=doc_of,
                )
            print(f"rate {rate:.0%}: {len(events)} events", flush=True)
    md = "\n".join(
        [
            f"## Mixed traffic — {args.dataset}{', embeddings' if embedder else ', lexical'}",
            "",
            "Cache starts empty. First-time questions are interleaved with paraphrased repeats at the given "
            "rate; every answer records an oracle trail. `sibling` = a first-time question whose scope "
            "(paper) already holds trails of other questions: it should miss. Hits without gold are false "
            "hits.",
            "",
            stream_markdown(by_rate),
        ]
    )
    (_dir(args) / f"stream{_suffix(args)}.json").write_text(
        json.dumps({str(k): [asdict(r) for r in v] for k, v in by_rate.items()}), encoding="utf-8"
    )
    (_dir(args) / f"stream{_suffix(args)}.md").write_text(md, encoding="utf-8")
    print(md)
    return 0


def _suffix(args: argparse.Namespace) -> str:
    return "-embed" if args.embed else ""


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
    ed = cmds.add_parser("edits", help="edit cited nodes after recording; compare cache designs (offline)")
    ed.add_argument("--rates", type=float, nargs="+", default=[0.0, 0.05, 0.1, 0.25, 0.5])
    ed.add_argument("--budget", type=int, default=2000, help="recall token budget")
    ed.add_argument("--embed", nargs="?", const=DEFAULT_MODEL, help="also match by embeddings (model)")
    ed.set_defaults(func=cmd_edits)
    st = cmds.add_parser("stream", help="empty cache, mixed new and repeated questions (offline)")
    st.add_argument("--rates", type=float, nargs="+", default=[0.1, 0.2, 0.3, 0.4])
    st.add_argument("--seed", type=int, default=7)
    st.add_argument("--budget", type=int, default=2000, help="recall token budget")
    st.add_argument("--embed", nargs="?", const=DEFAULT_MODEL, help="also match by embeddings (model)")
    st.set_defaults(func=cmd_stream)
    v = cmds.add_parser(
        "verify", help="reference-free gate: are phase-A answers supported by their citations"
    )
    v.add_argument("--scenario", default="repeat-verified")
    v.add_argument("--model", help="verifier model (default: the scenario's)")
    v.add_argument("--source-tokens", type=int, default=800, help="max tokens read per cited node")
    v.add_argument("--embed", nargs="?", const=DEFAULT_MODEL, help="same phase A as the embeddings runs")
    v.set_defaults(func=cmd_verify)
    r = cmds.add_parser("report", help="write the Markdown report")
    r.add_argument("--out", type=Path, help="default reports/<dataset>-eval.md")
    r.add_argument("--judge", default="sonnet", help="whose verdicts to report")
    r.set_defaults(func=cmd_report)
