import json
import sys
from pathlib import Path
from typing import Any

import anyio
import pytest

pytest.importorskip("mcp")

from mcp import Client, StdioServerParameters

from ragtrail.cli import load_resolver, main
from ragtrail.mcp import create_server
from ragtrail.store import SQLiteStore
from tests.corpus import Corpus

Q1 = "How do I reset my password?"
Q2 = "How can I reset my password if I forgot it"


def text_of(result: object) -> str:
    return "".join(getattr(c, "text", "") for c in getattr(result, "content", []))


def data_of(result: Any) -> dict[str, Any]:
    assert result.structured_content is not None
    return dict(result.structured_content)


def test_tools_listed_with_schemas() -> None:
    async def scenario() -> None:
        async with Client(create_server(SQLiteStore(":memory:"), Corpus().resolver(), "acme")) as client:
            tools = {t.name: t for t in (await client.list_tools()).tools}
            assert sorted(tools) == ["recall", "record"]
            assert set(tools["recall"].input_schema["properties"]) == {"query", "budget_tokens"}
            assert set(tools["record"].input_schema["properties"]) == {"query", "cited", "outcome", "steps"}
            assert "scope" not in json.dumps(tools["recall"].input_schema)

    anyio.run(scenario)


def test_recorded_trail_is_recalled_next_turn() -> None:
    corpus = Corpus()
    store = SQLiteStore(":memory:")

    async def scenario() -> None:
        async with Client(create_server(store, corpus.resolver(), "acme")) as client:
            miss = await client.call_tool("recall", {"query": Q1})
            assert data_of(miss)["mode"] == "miss" and "Search as usual" in text_of(miss)

            rec = await client.call_tool(
                "record",
                {
                    "query": Q1,
                    "cited": ["n70", "n72"],
                    "outcome": "verified",
                    "steps": [
                        {"tool": "search", "args": {"q": "reset password"}, "returned": ["n70", "n72"]}
                    ],
                },
            )
            assert not rec.is_error and data_of(rec)["recorded"] is True

            hit = await client.call_tool("recall", {"query": Q2})
            data = data_of(hit)
            assert data["mode"] == "prefetch" and data["nodes"] == ["n70", "n72"]
            assert corpus.texts["n70"] in text_of(hit)
            assert data["text"] == text_of(hit)

    anyio.run(scenario)
    t = store.get("acme", data_of_last_trajectory(store))
    assert t is not None and t.steps[0].tool == "search"


def data_of_last_trajectory(store: SQLiteStore) -> str:
    row = store._conn.execute("SELECT data FROM trajectories ORDER BY created_at DESC LIMIT 1").fetchone()
    return str(json.loads(row[0])["id"])


def test_record_rejections() -> None:
    async def scenario() -> None:
        async with Client(create_server(SQLiteStore(":memory:"), Corpus().resolver(), "acme")) as client:
            nothing = await client.call_tool("record", {"query": Q1, "cited": ["nope"]})
            assert not nothing.is_error and data_of(nothing)["recorded"] is False
            bad = await client.call_tool("record", {"query": Q1, "cited": ["n70"], "steps": [{"args": {}}]})
            assert bad.is_error
            budget = await client.call_tool("recall", {"query": Q1, "budget_tokens": 0})
            assert budget.is_error

    anyio.run(scenario)


def test_unverified_mode_only_hints() -> None:
    async def scenario() -> None:
        async with Client(create_server(SQLiteStore(":memory:"), None, "acme")) as client:
            rec = await client.call_tool("record", {"query": Q1, "cited": ["doc-7"], "outcome": "accepted"})
            assert data_of(rec)["recorded"] is True
            hit = await client.call_tool("recall", {"query": Q1})
            assert data_of(hit)["mode"] == "hint"
            assert "[doc-7]" in text_of(hit) and "not re-checked" in text_of(hit)

    anyio.run(scenario)


def test_servers_are_scope_bound() -> None:
    store = SQLiteStore(":memory:")
    corpus = Corpus()

    async def scenario() -> None:
        async with Client(create_server(store, corpus.resolver(), "acme")) as client:
            await client.call_tool("record", {"query": Q1, "cited": ["n70"]})
        async with Client(create_server(store, corpus.resolver(), "globex")) as client:
            assert data_of(await client.call_tool("recall", {"query": Q1}))["mode"] == "miss"

    anyio.run(scenario)


def test_serve_over_stdio_subprocess(tmp_path: Path) -> None:
    db = tmp_path / "trails.db"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ragtrail.cli", "serve", "--db", str(db), "--scope", "acme"],
    )

    async def scenario() -> None:
        async with Client(params) as client:
            assert len((await client.list_tools()).tools) == 2
            await client.call_tool("record", {"query": Q1, "cited": ["c1"], "outcome": "accepted"})
        async with Client(params) as client:
            hit = await client.call_tool("recall", {"query": Q2})
            assert data_of(hit)["mode"] == "hint" and data_of(hit)["nodes"] == ["c1"]

    anyio.run(scenario)


def test_cli_errors(tmp_path: Path) -> None:
    db = str(tmp_path / "t.db")
    assert main(["serve", "--db", db, "--subforest", str(tmp_path / "missing.db")]) == 2
    assert main(["serve", "--db", db, "--resolver", "no_colon"]) == 2
    assert main(["serve", "--db", db, "--resolver", "ragtrail.models:NodeRef"]) == 2
    assert main(["serve", "--db", db, "--scope", "a#b"]) == 2
    assert main(["serve", "--db", db, "--ttl-days", "0"]) == 2
    with pytest.raises(ValueError):
        load_resolver("nope")


def test_purge(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["purge", "--db", str(tmp_path / "t.db")]) == 0
    assert "purged 0" in capsys.readouterr().out


def test_serve_with_subforest_index(tmp_path: Path) -> None:
    pytest.importorskip("subforest")
    from subforest import TreeStore
    from subforest.build import build_corpus

    corpus_db = tmp_path / "corpus.db"
    with TreeStore(corpus_db) as tree:
        build_corpus(Path(__file__).parents[1] / "examples" / "corpus", corpus_id="larch").write(tree)
        tokens = next(n for n in (tree.get_node(i) for i in range(1, 30)) if n.title == "Tokens")
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "ragtrail.cli", "serve", "--db", str(tmp_path / "t.db"), "--subforest", str(corpus_db)],
    )

    async def scenario() -> None:
        async with Client(params) as client:
            q = "When do access tokens expire?"
            await client.call_tool("record", {"query": q, "cited": [tokens.short_id], "outcome": "verified"})
            hit = await client.call_tool("recall", {"query": "when do the access tokens expire"})
            assert data_of(hit)["mode"] == "prefetch"
            assert "Authentication › Tokens" in text_of(hit) and "60 minutes" in text_of(hit)

    anyio.run(scenario)


def test_calls_are_logged(tmp_path: Path) -> None:
    log = tmp_path / "calls.jsonl"

    async def scenario() -> None:
        server = create_server(SQLiteStore(":memory:"), Corpus().resolver(), "acme", log=log)
        async with Client(server) as client:
            await client.call_tool("recall", {"query": Q1})
            await client.call_tool("record", {"query": Q1, "cited": ["n70"]})

    anyio.run(scenario)
    lines = [json.loads(line) for line in log.read_text().splitlines()]
    assert [(e["tool"], e.get("mode"), e.get("recorded")) for e in lines] == [
        ("recall", "miss", None),
        ("record", None, True),
    ]
    assert lines[0]["args"]["query"] == Q1


def test_recall_only_server() -> None:
    async def scenario() -> None:
        server = create_server(SQLiteStore(":memory:"), Corpus().resolver(), "acme", allow_record=False)
        async with Client(server) as client:
            assert [t.name for t in (await client.list_tools()).tools] == ["recall"]

    anyio.run(scenario)
