from ragtrail.eval.data import EvalQuestion
from ragtrail.eval.offline import warm_up
from ragtrail.eval.stream import (
    EditedResolver,
    Event,
    build_stream,
    edit_markdown,
    edit_rows,
    run_stream,
    stream_markdown,
)
from ragtrail.resolver import GenericResolver
from ragtrail.store import SQLiteStore

RESOLVER = GenericResolver(lambda i: "h", lambda i, n: "text")


def q(id_: str, text: str, gold: list[str], source: str | None = None) -> EvalQuestion:
    return EvalQuestion(id=id_, split="s", question=text, answer="", gold=gold, source_id=source)


def test_edited_resolver_passes_reads_through() -> None:
    r = EditedResolver(RESOLVER, edited={"a"})
    assert r.read("a", 10) == "text" and r.label("a") == "a"


def test_build_stream_hits_the_rate_by_dropping_new_questions() -> None:
    new = [(q(f"q{i}", f"q{i}", []), "s") for i in range(20)]
    paras = [q(f"p{i}", "p", [], f"q{i}") for i in range(3)]
    events = build_stream(new, paras, 0.5)
    repeats = [e for e in events if e.kind == "repeat"]
    assert len(repeats) == 3 and len(events) == 6
    assert {e.question.id for e in events} >= {"q0", "q1", "q2"}


def test_build_stream_marks_siblings_per_scope() -> None:
    new = [(q("a", "a", []), "paper1"), (q("b", "b", []), "paper1"), (q("c", "c", []), "paper2")]
    kinds = {e.question.id: e.kind for e in build_stream(new, [], 0.0)}
    assert sorted(kinds.values()) == ["new", "new", "sibling"]
    assert kinds["c"] == "new"


def test_build_stream_rejects_bad_rate() -> None:
    try:
        build_stream([], [], 1.0)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_stream_counts_false_hits() -> None:
    a = q("a", "How do I add a custom domain to my site?", ["n1"])
    b = q("b", "How do I add a custom domain to my site", ["n2"])
    rows = run_stream(SQLiteStore(":memory:"), RESOLVER, [Event(a, "s", "new"), Event(b, "s", "new")])
    assert [(r.mode, r.gold_hit) for r in rows] == [("miss", False), ("prefetch", False)]
    md = stream_markdown({0.1: rows})
    assert "| 10% | new | 2 | 1 = 50%" in md and "| 10% | all |" in md


def test_edit_rows_never_serve_changed_nodes() -> None:
    warm = [
        q(f"w{i}", f"how do I configure feature number {i} on my site", [f"n{i}", f"m{i}"]) for i in range(6)
    ]

    def fresh() -> SQLiteStore:
        store = SQLiteStore(":memory:")
        warm_up(store, RESOLVER, warm, "s")
        return store

    test = [(w.model_copy(update={"id": f"t{w.id}"}), "s") for w in warm]
    cited = [g for w in warm for g in w.gold]
    rows = edit_rows(fresh, RESOLVER, test, cited, [0.0, 0.5])
    assert all(r.served_changed == 0 for r in rows)
    half = [r for r in rows if r.rate == 0.5]
    assert sum(r.changed for r in half) == 6 and any(r.mode == "hint" for r in half)
    assert "| 50% | 6 |" in edit_markdown(rows)
