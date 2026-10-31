import json
from pathlib import Path

import pytest

from ragtrail.eval.agent import AgentConfig, load_runs, run_agent, run_one
from ragtrail.eval.claude import UsageLimitReached, json_block, parse_output
from ragtrail.eval.data import EvalQuestion, load_questions, save_questions
from ragtrail.eval.judge import judge_runs, parse_verdicts
from ragtrail.eval.offline import (
    OfflineReport,
    best_matches,
    exact_duplicates,
    recall_rows,
    warm_up,
)
from ragtrail.eval.paraphrase import apply_paraphrases, paraphrase_all
from ragtrail.eval.report import agent_markdown, judge_key, pair_runs
from ragtrail.eval.stats import bootstrap_ci, wilson
from ragtrail.match import DEFAULT_CONFIG
from ragtrail.store import SQLiteStore
from tests.corpus import Corpus


def q(i: str, text: str, gold: list[str], answer: str = "Open Settings › Security.") -> EvalQuestion:
    return EvalQuestion(id=i, split="s", question=text, answer=answer, gold=gold)


WARM = [q("w1", "How do I reset my password?", ["n70"]), q("w2", "Why was my payment declined?", ["n90"])]
TEST = [
    q("t1", "How can I reset my password if I forgot it", ["n70"]),
    q("t2", "Where do I download invoices?", ["n90"]),
]


def test_questions_round_trip(tmp_path: Path) -> None:
    save_questions(tmp_path / "q.jsonl", WARM)
    assert load_questions(tmp_path / "q.jsonl") == WARM


def test_offline_warm_up_and_recall() -> None:
    store = SQLiteStore(":memory:")
    resolver = Corpus().resolver()
    assert warm_up(store, resolver, [*WARM, q("w3", "?!", ["n70"])], "eval") == 2
    rows = recall_rows(store, resolver, TEST, "eval", budget_tokens=500)
    assert [(r.id, r.mode, r.gold_hit) for r in rows] == [("t1", "prefetch", True), ("t2", "miss", False)]
    report = OfflineReport(
        "demo",
        "desc",
        3,
        2,
        2,
        exact_duplicates(WARM, TEST),
        rows,
        DEFAULT_CONFIG,
        500,
        best_matches(WARM, TEST),
        "dev",
    )
    md = report.markdown()
    assert "| prefetch | 1 | 50% | 1/1 = 100%" in md
    assert "Threshold sweep on the dev pairing (dev)" in md


def test_best_matches_and_duplicates() -> None:
    assert exact_duplicates(WARM, [q("x", "how do i RESET my password", [])]) == 1
    (sim, same), (_, other) = best_matches(WARM, TEST)
    assert sim >= 0.5 and same and not other


def test_paraphrases_drop_copies_and_unknown_ids() -> None:
    out = apply_paraphrases(
        WARM,
        json.dumps(
            [
                {"id": "w1", "question": "I can't log in, how do I set a new password?"},
                {"id": "w2", "question": "why was my payment declined?"},
                {"id": "zz", "question": "?"},
            ]
        ),
    )
    assert [(p.id, p.source_id, p.gold) for p in out] == [("w1-p", "w1", ["n70"])]


def fake_claude(result: str) -> object:
    def invoke(cmd: list[str], cwd: Path) -> str:
        return json.dumps({"result": result, "is_error": False})

    return invoke


def test_paraphrase_all_batches() -> None:
    reply = json.dumps([{"id": w.id, "question": w.question + " please"} for w in WARM])
    out = paraphrase_all(WARM, batch_size=1, invoke=fake_claude(reply), echo=lambda s: None)  # type: ignore[arg-type]
    assert [p.id for p in out] == ["w1-p", "w2-p"]


def test_judge_parsing_and_runs() -> None:
    assert parse_verdicts(
        '```json\n[{"key": "a", "verdict": "correct"}, {"key": "a2", "verdict": "meh"}]\n```', ["a", "a2"]
    ) == {"a": "correct"}
    items = [{"key": k, "question": "?", "reference": "r", "candidate": "c"} for k in ("a", "b")]
    reply = json.dumps([{"key": "a", "verdict": "partial"}, {"key": "b", "verdict": "incorrect"}])
    got = judge_runs(items, invoke=fake_claude(reply), echo=lambda s: None)  # type: ignore[arg-type]
    assert got == {"a": "partial", "b": "incorrect"}


def test_claude_output_parsing() -> None:
    assert json_block('noise {"a": 1} tail') == {"a": 1}
    with pytest.raises(ValueError):
        json_block("nothing")
    with pytest.raises(UsageLimitReached):
        parse_output(json.dumps({"is_error": True, "result": "Claude usage limit reached"}))


def scripted_invoke(cmd: list[str], cwd: Path) -> str:
    """Pretend to be claude -p: write the servers' call logs, as the real MCP servers would."""
    config = json.loads(Path(cmd[cmd.index("--mcp-config") + 1]).read_text())
    trails_db = Path(config["mcpServers"]["trails"]["args"][4])
    warm = trails_db.exists() and trails_db.stat().st_size > 0
    with (cwd / "trails.jsonl").open("w") as f:
        f.write(
            json.dumps(
                {"tool": "recall", "mode": "prefetch" if warm else "miss", "nodes": ["n70"] if warm else []}
            )
            + "\n"
        )
    if not warm:
        with (cwd / "docs.jsonl").open("w") as f:
            f.write(
                json.dumps(
                    {
                        "tool": "search",
                        "args": {"query": "x"},
                        "text": "Password [n70]",
                        "error": False,
                        "blocked": False,
                    }
                )
                + "\n"
            )
            f.write(
                json.dumps(
                    {
                        "tool": "read",
                        "args": {"node_id": "n70"},
                        "text": "...",
                        "error": False,
                        "blocked": False,
                    }
                )
                + "\n"
            )
    usage = {"input_tokens": 100, "cache_read_input_tokens": 900 if not warm else 300, "output_tokens": 20}
    return json.dumps(
        {"result": "Open Settings › Security.", "is_error": False, "usage": usage, "num_turns": 3}
    )


def test_run_one_records_calls(tmp_path: Path) -> None:
    warm_db = tmp_path / "warm.db"
    warm_db.write_bytes(b"x")
    cold = run_one(TEST[0], "cold", "demo", tmp_path / "c.db", warm_db, AgentConfig(), scripted_invoke)
    warm = run_one(TEST[0], "warm", "demo", tmp_path / "c.db", warm_db, AgentConfig(), scripted_invoke)
    assert (len(cold["docs_calls"]), cold["trail_calls"][0]["mode"], cold["input_tokens"]) == (
        2,
        "miss",
        1000,
    )
    assert (len(warm["docs_calls"]), warm["trail_calls"][0]["mode"], warm["input_tokens"]) == (
        0,
        "prefetch",
        400,
    )
    assert cold["docs_calls"][0]["shown"] == ["n70"]


def test_run_agent_resumes_after_usage_limit(tmp_path: Path) -> None:
    warm_db = tmp_path / "warm.db"
    warm_db.write_bytes(b"x")
    runs = tmp_path / "runs.jsonl"
    calls = {"n": 0}

    def limited(cmd: list[str], cwd: Path) -> str:
        calls["n"] += 1
        if calls["n"] == 3:
            return json.dumps({"is_error": True, "result": "usage limit reached"})
        return scripted_invoke(cmd, cwd)

    kw = {
        "scenario": "demo",
        "corpus": tmp_path / "c.db",
        "warm_db": warm_db,
        "config": AgentConfig(),
        "echo": lambda s: None,
    }
    assert run_agent(TEST, runs, invoke=limited, **kw) == 2  # type: ignore[arg-type]
    assert run_agent(TEST, runs, invoke=scripted_invoke, **kw) == 2  # type: ignore[arg-type]
    assert len(load_runs(runs)) == 4


def test_pairing_scoring_and_report(tmp_path: Path) -> None:
    warm_db = tmp_path / "warm.db"
    warm_db.write_bytes(b"x")
    runs = [
        run_one(t, arm, "demo", tmp_path / "c.db", warm_db, AgentConfig(), scripted_invoke)
        for t in TEST
        for arm in ("cold", "warm")
    ]
    verdicts = {judge_key("demo", t.id, arm): "correct" for t in TEST for arm in ("cold", "warm")}
    paired = pair_runs("demo", runs, TEST, lambda n: n, verdicts)
    assert paired.ids == ["t1", "t2"]
    assert [s.calls for s in paired.arms["cold"]] == [3, 3]
    assert [s.calls for s in paired.arms["warm"]] == [1, 1]
    assert paired.arms["warm"][0].gold_seen and not paired.arms["warm"][1].gold_seen
    md = agent_markdown(paired, "haiku")
    assert "| Tool calls (incl. recall) | 3.00 | 1.00 | -2.00 |" in md
    assert "Judge accuracy (n=2)" in md and "| prefetch | 2 | 3.0 → 1.0 |" in md
    assert agent_markdown(pair_runs("demo", runs[:1], TEST, lambda n: n, {}), "haiku").startswith(
        "No question"
    )


def test_stats_helpers() -> None:
    assert bootstrap_ci([]) == (0.0, 0.0)
    assert wilson(0, 0) == (0.0, 0.0)


def test_session_limit_message_is_a_usage_limit() -> None:
    with pytest.raises(UsageLimitReached):
        parse_output(
            json.dumps({"is_error": True, "result": "You've hit your session limit · resets 11:10pm (UTC)"})
        )


def test_gold_sections_must_be_seen_directly() -> None:
    from ragtrail.eval.report import score_run

    q = EvalQuestion(id="q", split="s", question="?", answer="a", gold=["n12"])
    doc_of = {"n12": "n10", "n11": "n10", "n10": "n10"}.get
    run = {
        "docs_calls": [
            {"tool": "read", "args": {"node_id": "n11"}, "shown": [], "error": False, "blocked": False}
        ],
        "trail_calls": [],
        "input_tokens": 1,
        "seconds": 1.0,
        "answer": "a",
    }
    assert not score_run(run, q, doc_of, None).gold_seen
    run["trail_calls"] = [{"mode": "prefetch", "nodes": ["n12"]}]
    assert score_run(run, q, doc_of, None).gold_seen
