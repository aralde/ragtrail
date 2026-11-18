import io
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from ragtrail.cli import main
from ragtrail.export import EXIT_CHANGED, TrailChanged, export_problems, fetch, find_trail, run
from ragtrail.models import NodeRef, Trajectory
from ragtrail.recorder import Recorder
from ragtrail.store import SQLiteStore
from tests.corpus import FIXTURE, Corpus

ROOT = Path(__file__).parent.parent
SPEC = "tests.export_resolver:resolver"
Q = "What are the rate limits of the API?"


def record(db: Path, corpus: Corpus, cited: list[str], query: str = Q) -> Trajectory:
    with SQLiteStore(db) as store:
        rec = Recorder(store, corpus.resolver(), "acme", query)
        rec.step("search", {"q": "rate limits"}, cited)
        rec.cite(cited)
        trajectory = rec.commit("verified")
    assert trajectory is not None
    return trajectory


def corpus_file(tmp_path: Path, edits: dict[str, str] | None = None) -> Path:
    data = json.loads(FIXTURE.read_text())
    for node_id, text in (edits or {}).items():
        data["nodes"][node_id]["text"] = text
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(data))
    return path


def export(tmp_path: Path, *args: str) -> int:
    return main(["export", *args, "--db", str(tmp_path / "t.db"), "--scope", "acme", "--resolver", SPEC])


def run_script(script: Path, corpus: Path) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "RAGTRAIL_TEST_CORPUS": str(corpus), "PYTHONPATH": str(ROOT)}
    return subprocess.run([sys.executable, str(script)], capture_output=True, text=True, env=env, check=False)


def test_script_returns_cited_documents_and_fails_on_change(tmp_path: Path) -> None:
    corpus = Corpus()
    t = record(tmp_path / "t.db", corpus, ["n33", "n35"])
    script = tmp_path / "fetch.py"
    assert export(tmp_path, t.id, "-o", str(script)) == 0
    assert os.access(script, os.X_OK)

    ok = run_script(script, corpus_file(tmp_path))
    assert ok.returncode == 0, ok.stderr
    out = json.loads(ok.stdout)
    assert out["trail"] == t.id
    assert [d["node_id"] for d in out["documents"]] == ["n33", "n35"]
    assert out["documents"][0]["text"] == corpus.texts["n33"]
    assert out["documents"][0]["label"] == "Authentication › Tokens"
    assert "answer" not in ok.stdout

    changed = run_script(script, corpus_file(tmp_path, {"n35": "Refresh is now POST /v2/token."}))
    assert changed.returncode == EXIT_CHANGED
    assert changed.stdout == ""
    assert "n35" in changed.stderr and "n33" not in changed.stderr


def test_export_is_deterministic(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    t = record(tmp_path / "t.db", Corpus(), ["n33"])
    assert export(tmp_path, t.id) == 0
    first = capsys.readouterr().out
    assert export(tmp_path, t.id) == 0
    assert capsys.readouterr().out == first
    assert first.startswith("#!/usr/bin/env python3\n")
    assert f"TRAIL_ID = {t.id!r}" in first


def test_export_by_query_picks_the_matching_trail(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    corpus = Corpus()
    record(tmp_path / "t.db", corpus, ["n58"], query="How long do API sessions last?")
    t = record(tmp_path / "t.db", corpus, ["n33"])
    assert export(tmp_path, "--query", "what are the rate limits of the api") == 0
    assert f"TRAIL_ID = {t.id!r}" in capsys.readouterr().out
    assert export(tmp_path, "--query", "how do I delete my account forever") == 1


def test_export_refuses_unstable_trails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = Corpus()
    t = record(tmp_path / "t.db", corpus, ["n33"])
    edited = corpus_file(tmp_path, {"n33": "Tokens now expire after 30 minutes."})
    with monkeypatch.context() as m:
        m.setenv("RAGTRAIL_TEST_CORPUS", str(edited))
        assert export(tmp_path, t.id) == 1
        assert "n33" in capsys.readouterr().err
    with SQLiteStore(tmp_path / "t.db") as store:
        store.incr_rejections("acme", t.id)
    assert export(tmp_path, t.id) == 1
    assert "rejected" in capsys.readouterr().err
    assert export(tmp_path, "nope") == 1
    assert export(tmp_path, t.id, "--query", Q) == 2
    assert export(tmp_path) == 2


def test_export_never_crosses_scopes(tmp_path: Path) -> None:
    t = record(tmp_path / "t.db", Corpus(), ["n33"])
    db = str(tmp_path / "t.db")
    assert main(["export", t.id, "--db", db, "--scope", "globex", "--resolver", SPEC]) == 1


def test_export_problems_flags_unverified_and_stale() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    t = Trajectory.expiring_in(
        timedelta(days=1),
        now=now,
        scope="acme",
        query="q",
        query_norm="q",
        signature=[1],
        outcome="accepted",
        useful=[NodeRef(node_id="n33", content_hash="unverified")],
        stale=True,
    )
    problems = export_problems(t, Corpus().resolver())
    assert any("stale" in p for p in problems)
    assert any("unverified" in p for p in problems)


def test_fetch_checks_every_hash_before_reading() -> None:
    corpus = Corpus()
    resolver = corpus.resolver()
    refs = [NodeRef(node_id=n, content_hash=resolver.content_hash(n) or "") for n in ("n33", "n35")]
    corpus.edit("n35", "changed")
    with pytest.raises(TrailChanged) as exc:
        fetch(resolver, [*refs, NodeRef(node_id="gone", content_hash="x")])
    assert exc.value.changed == ["n35", "gone"]
    assert corpus.reads == 0


def test_fetch_fails_after_expiry() -> None:
    corpus = Corpus()
    resolver = corpus.resolver()
    refs = [NodeRef(node_id="n33", content_hash=resolver.content_hash("n33") or "")]
    expires = datetime(2026, 1, 1, tzinfo=UTC)
    assert fetch(resolver, refs, expires_at=expires, now=expires - timedelta(seconds=1))
    with pytest.raises(TrailChanged) as exc:
        fetch(resolver, refs, expires_at=expires, now=expires)
    assert exc.value.expired


def test_run_reports_resolver_errors() -> None:
    err = io.StringIO()
    assert run("t1", [("n33", "h")], "2999-01-01T00:00:00+00:00", "no_colon", None, 100, err=err) == 2
    assert "resolver" in err.getvalue()


def test_find_trail_skips_rejected(tmp_path: Path) -> None:
    corpus = Corpus()
    t = record(tmp_path / "t.db", corpus, ["n33"])
    with SQLiteStore(tmp_path / "t.db") as store:
        assert find_trail(store, corpus.resolver(), Q, "acme") is not None
        store.incr_rejections("acme", t.id)
        assert find_trail(store, corpus.resolver(), Q, "acme") is None
