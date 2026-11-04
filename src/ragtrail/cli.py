"""Command-line interface: `ragtrail serve` (MCP over stdio) and `ragtrail purge`."""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from ragtrail.embed import DEFAULT_MODEL
from ragtrail.recall import DEFAULT_BUDGET_TOKENS
from ragtrail.resolver import NodeResolver
from ragtrail.store import SQLiteStore


def load_resolver(spec: str) -> NodeResolver:
    """Import `module:factory` and call the factory to get a resolver.

    >>> load_resolver("ragtrail.mcp:UnverifiedResolver").content_hash("x")
    'unverified'
    """
    module_name, sep, attr = spec.partition(":")
    if not sep or not module_name or not attr:
        raise ValueError(f"expected module:factory, got {spec!r}")
    factory = getattr(importlib.import_module(module_name), attr)
    resolver = factory()
    if not isinstance(resolver, NodeResolver):
        raise TypeError(f"{spec} did not return a NodeResolver")
    return resolver


def _subforest_resolver(db: Path) -> NodeResolver:
    try:
        subforest = importlib.import_module("subforest")
    except ImportError:
        raise RuntimeError("--subforest needs subforest installed next to ragtrail") from None
    from ragtrail.subforest import SubforestResolver

    return SubforestResolver(subforest.TreeStore(db))


def _serve(args: argparse.Namespace) -> int:
    try:
        from ragtrail.mcp import create_server
    except ImportError:
        print("error: the MCP server needs the extra: pip install 'ragtrail[mcp]'", file=sys.stderr)
        return 2
    resolver: NodeResolver | None = None
    try:
        if args.subforest is not None:
            if not args.subforest.exists():
                print(f"error: {args.subforest} does not exist", file=sys.stderr)
                return 2
            resolver = _subforest_resolver(args.subforest)
        elif args.resolver is not None:
            resolver = load_resolver(args.resolver)
    except (RuntimeError, ValueError, TypeError, ImportError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    embedder = None
    if args.embed is not None:
        try:
            from ragtrail.embed import FastEmbedder

            embedder = FastEmbedder(args.embed)
        except ImportError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if resolver is None:
        print("ragtrail: no index attached (--subforest/--resolver); running unverified", file=sys.stderr)
    with SQLiteStore(args.db) as store:
        server = create_server(
            store,
            resolver,
            args.scope,
            budget_tokens=args.budget,
            ttl=timedelta(days=args.ttl_days),
            log=args.log,
            allow_record=not args.no_record,
            embedder=embedder,
            strip_context=args.strip_context,
        )
        server.run("stdio")
    return 0


def _purge(args: argparse.Namespace) -> int:
    with SQLiteStore(args.db) as store:
        print(f"purged {store.purge_expired()} expired trajectories")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """The `ragtrail` argument parser.

    >>> build_parser().parse_args(["serve", "--db", "t.db"]).scope
    'default'
    """
    parser = argparse.ArgumentParser(prog="ragtrail", description="Trajectory cache for agentic RAG.")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="serve recall/record as an MCP server over stdio")
    serve.add_argument("--db", type=Path, required=True, help="SQLite file for trails (created if missing)")
    serve.add_argument("--scope", default="default", help="tenant / permission group this server serves")
    index = serve.add_mutually_exclusive_group()
    index.add_argument("--subforest", type=Path, help="subforest corpus DB used to check and read nodes")
    index.add_argument("--resolver", help="module:factory returning a NodeResolver for your index")
    serve.add_argument(
        "--budget", type=int, default=DEFAULT_BUDGET_TOKENS, help="default recall token budget"
    )
    serve.add_argument("--ttl-days", type=float, default=30.0, help="days a recorded trail stays valid")
    serve.add_argument("--log", type=Path, help="append one JSON line per tool call to this file")
    serve.add_argument(
        "--embed",
        nargs="?",
        const=DEFAULT_MODEL,
        help=f"also match by embeddings (needs ragtrail[embed]); optional model, default {DEFAULT_MODEL}",
    )
    serve.add_argument(
        "--no-record", action="store_true", help="serve recall only; the trail store stays fixed"
    )
    serve.add_argument(
        "--strip-context", metavar="REGEX", help="remove this fixed context from queries before matching"
    )
    serve.set_defaults(func=_serve)

    from ragtrail.eval.cli import add_eval_parser

    add_eval_parser(sub)

    purge = sub.add_parser("purge", help="delete expired trails")
    purge.add_argument("--db", type=Path, required=True)
    purge.set_defaults(func=_purge)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point of the `ragtrail` command."""
    args = build_parser().parse_args(argv)
    if getattr(args, "ttl_days", 1) <= 0 or getattr(args, "budget", 1) < 1:
        print("error: --ttl-days and --budget must be positive", file=sys.stderr)
        return 2
    scope = getattr(args, "scope", "default")
    if not scope or "#" in scope:
        print(f"error: invalid --scope {scope!r} (non-empty, no '#')", file=sys.stderr)
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
