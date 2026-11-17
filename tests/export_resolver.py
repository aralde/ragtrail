"""Resolver factory for exported fetch scripts in tests: the corpus file comes from `RAGTRAIL_TEST_CORPUS`."""

import json
import os
from pathlib import Path

from ragtrail.resolver import GenericResolver, text_hash

FIXTURE = Path(__file__).parent / "fixtures" / "corpus.json"


def resolver() -> GenericResolver:
    path = Path(os.environ.get("RAGTRAIL_TEST_CORPUS", FIXTURE))
    nodes = json.loads(path.read_text())["nodes"]
    return GenericResolver(
        hash_fn=lambda i: text_hash(nodes[i]["text"]) if i in nodes else None,
        read_fn=lambda i, max_tokens: nodes[i]["text"],
        label_fn=lambda i: nodes[i]["label"] if i in nodes else i,
    )
