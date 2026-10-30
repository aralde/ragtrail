"""MCP server exposing `recall` and `record` over stdio. Requires the `ragtrail[mcp]` extra.

The server is bound to one scope: tools never take a scope argument, so a client cannot read
another tenant's trails.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer
from mcp_types import CallToolResult, TextContent, ToolAnnotations
from pydantic import ValidationError

from ragtrail.embed import Embedder
from ragtrail.match import DEFAULT_CONFIG, MatchConfig
from ragtrail.models import Outcome, RecallResult, Step
from ragtrail.recall import DEFAULT_BUDGET_TOKENS
from ragtrail.recall import recall as recall_trail
from ragtrail.recorder import DEFAULT_TTL, Recorder
from ragtrail.resolver import NodeResolver
from ragtrail.store import TrajectoryStore

INSTRUCTIONS = """\
ragtrail remembers which documentation nodes answered similar questions before.
1. At the start of a question, call `recall` with the user's question copied verbatim (do not rephrase it
   or turn it into keywords: matching works on the original wording).
   - mode=prefetch: the useful node texts are included; answer from them, search only if something is missing.
   - mode=hint: read the listed node ids first, before searching.
   - mode=miss: search as usual.
2. After answering, call `record` with the question, the node ids your answer cites and the tool calls
   you made.
   Only record when the answer is grounded in those nodes. Never pass the answer text."""

UNVERIFIED_NOTE = "  (ragtrail runs without an index here: node contents were not re-checked; read them.)"

_ANNOTATIONS = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=False, open_world_hint=False
)


class UnverifiedResolver:
    """Resolver used when the server has no access to the index: every node counts as unchanged.

    Recall is capped at `hint` in this mode, since node text cannot be read or checked.

    >>> UnverifiedResolver().content_hash("anything")
    'unverified'
    """

    def content_hash(self, node_id: str) -> str | None:
        return "unverified"

    def label(self, node_id: str) -> str:
        return node_id

    def read(self, node_id: str, max_tokens: int) -> str:
        return ""


def _result(text: str, data: dict[str, Any], *, error: bool = False) -> CallToolResult:
    # Some clients show only structured content when present, so it carries the text too.
    return CallToolResult(
        content=[TextContent(type="text", text=text)],
        structured_content={"text": text, **data},
        is_error=error,
    )


def _recall_data(result: RecallResult) -> dict[str, Any]:
    return {
        "mode": result.mode,
        "similarity": round(result.similarity, 4),
        "trajectory_id": result.trajectory_id,
        "nodes": [n.node_id for n in result.nodes],
        "stale": result.stale,
        "matched_by": result.matched_by,
    }


def create_server(
    store: TrajectoryStore,
    resolver: NodeResolver | None,
    scope: str,
    *,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    config: MatchConfig = DEFAULT_CONFIG,
    ttl: timedelta = DEFAULT_TTL,
    log: Path | None = None,
    allow_record: bool = True,
    embedder: Embedder | None = None,
) -> MCPServer:
    """Build an MCP server with `recall` and `record` bound to `store`, `resolver` and `scope`.

    `allow_record=False` serves `recall` only (evals keep the trail store fixed).
    `log` appends one JSON line per call (tool, arguments, structured result); evals count calls with it.

    With `resolver=None` the server runs unverified: hashes are not checked and recall never prefetches.

    >>> import asyncio
    >>> from ragtrail.store import SQLiteStore
    >>> server = create_server(SQLiteStore(":memory:"), None, "acme")
    >>> sorted(t.name for t in asyncio.run(server.list_tools()))
    ['recall', 'record']
    """
    verified = resolver is not None
    active: NodeResolver = resolver if resolver is not None else UnverifiedResolver()
    instructions = INSTRUCTIONS if allow_record else INSTRUCTIONS.split("\n2.")[0]
    server: MCPServer = MCPServer(name="ragtrail", instructions=instructions)

    def emit(tool: str, args: dict[str, Any], result: CallToolResult) -> CallToolResult:
        if log is not None:
            entry = {
                "tool": tool,
                "args": args,
                "error": result.is_error,
                **(result.structured_content or {}),
            }
            with log.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return result

    def do_recall(query: str, budget_tokens: int) -> CallToolResult:
        if budget_tokens < 1:
            return _result("budget_tokens must be at least 1.", {}, error=True)
        result = recall_trail(
            store,
            active,
            query,
            scope,
            budget_tokens=budget_tokens,
            config=config,
            allow_prefetch=verified,
            embedder=embedder,
        )
        if result.mode == "miss":
            text = "ragtrail: no similar question solved before. Search as usual."
        elif not verified:
            text = result.rendered + "\n" + UNVERIFIED_NOTE
        else:
            text = result.rendered
        return _result(text, _recall_data(result))

    def do_record(
        query: str, cited: list[str], outcome: Outcome, steps: list[dict[str, Any]] | None
    ) -> CallToolResult:
        try:
            parsed = [Step.model_validate(s) for s in steps or []]
        except ValidationError as exc:
            return _result(f"Invalid steps: {exc.errors()[0]['msg']}.", {"recorded": False}, error=True)
        recorder = Recorder(store, active, scope, query, config=config, ttl=ttl, embedder=embedder)
        for s in parsed:
            recorder.step(s.tool, s.args, s.returned)
        recorder.cite(cited)
        trajectory = recorder.commit(outcome)
        if trajectory is None:
            return _result(
                "Not recorded: needs a non-empty question and at least one cited node that exists.",
                {"recorded": False},
            )
        nodes = [n.node_id for n in trajectory.useful]
        return _result(
            f"Recorded trajectory {trajectory.id} with {len(nodes)} node(s).",
            {"recorded": True, "trajectory_id": trajectory.id, "nodes": nodes},
        )

    @server.tool(annotations=_ANNOTATIONS)
    async def recall(query: str, budget_tokens: int = budget_tokens) -> CallToolResult:
        """Look up the retrieval path of a similar question answered before. Call it first, with the user's
        question copied verbatim (not rephrased or reduced to keywords).
        Returns mode=prefetch (node texts included), hint (node ids to read first) or miss (search)."""
        return emit(
            "recall", {"query": query, "budget_tokens": budget_tokens}, do_recall(query, budget_tokens)
        )

    async def record(
        query: str,
        cited: list[str],
        outcome: Literal["verified", "feedback", "accepted"] = "accepted",
        steps: list[dict[str, Any]] | None = None,
    ) -> CallToolResult:
        """Save the path that answered `query`: the node ids the answer cites, and optionally the tool calls
        made (each {"tool": name, "args": {...}, "returned": [node ids]}). Never include the answer text."""
        args = {"query": query, "cited": cited, "outcome": outcome, "steps": steps}
        return emit("record", args, do_record(query, cited, outcome, steps))

    if allow_record:
        server.tool(annotations=_ANNOTATIONS)(record)
    return server
