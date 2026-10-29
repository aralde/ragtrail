# Decisions

One line per decision: date — decision — reason.

- 2026-10-29 — `ragtrail` is free on PyPI (checked 2026-10-29) — keep the name.
- 2026-10-29 — Models are frozen pydantic models with `extra="forbid"` — immutable values are safe to share, and an accidental `answer` field fails loudly.
- 2026-10-29 — `Trajectory` gains `stale: bool = False`; `id` defaults to a uuid4 hex — `mark_stale` needs a representation; ids are generated where trajectories are built.
- 2026-10-29 — `scope` and `id` must be non-empty and must not contain `#`; datetimes must be timezone-aware and `expires_at > created_at` — `#` is the key separator, so this is what keeps scopes from colliding.
- 2026-10-29 — `put(trajectory, band_keys)` takes full band keys from the caller; the store checks each one is a band key of the trajectory's scope — the store stays independent of `MatchConfig`, and scope isolation is enforced at the storage boundary.
- 2026-10-29 — `candidates` raises `ValueError` on a band key outside `scope` instead of ignoring it — a cross-scope lookup is a caller bug and should be loud.
- 2026-10-29 — Stale trajectories are excluded from `candidates` but still returned by `get` — recall never reuses them, debugging still can see them.
- 2026-10-29 — A trajectory is expired when `expires_at <= now`; `get`, `candidates` and `incr_hits` ignore expired items even before `purge_expired` runs — mirrors DynamoDB/Cosmos, whose native TTL deletes lazily.
- 2026-10-29 — Band buckets keep the newest `band_cap` entries (default 32) by `created_at`; older entries are dropped on `put` — bounded reads per band, matching the capped list item in DynamoDB/Cosmos.
- 2026-10-29 — Stores take an injectable `clock` — TTL tests run without sleeping.
- 2026-10-29 — `SQLiteStore` keeps `hits` and `stale` as columns that override the stored JSON — counters update in place without rewriting the document.
- 2026-10-29 — Store tests are written against the `TrajectoryStore` protocol with a parametrized `store` fixture — cloud backends (M6/M7) reuse the same suite against their fakes.
- 2026-10-29 — Docstring examples run as doctests (`--doctest-modules`) — keeps the "every public function has an example" rule honest.
- 2026-10-29 — Normalization strips accents by default (`keep_accents=False`) and drops built-in en+es stopwords; question words are not stopwords; if every word is a stopword the words are kept — "cómo"/"como" should match, "how"/"why" should not, and a query never normalizes to nothing.
- 2026-10-29 — Punctuation, symbols, separators and control chars (Unicode categories P/S/Z/C) become spaces; digits stay — "rate-limit" and "rate limit" match; "v2" stays meaningful.
- 2026-10-29 — Shingles: word 2-grams (`w:`) + char 4-grams (`c:`) over the normalized text; texts shorter than an n-gram contribute themselves — short queries ("delete account") still get a signature.
- 2026-10-29 — MinHash uses blake2b-64 shingle hashes and universal hashing `(a·x + b) mod (2^61 − 1)` with `a, b` from `random.Random(seed)` — stdlib only, identical across processes and Python versions (no `hash()` randomization); values fit a signed 64-bit int for DynamoDB/Cosmos.
- 2026-10-29 — Default LSH layout is 42 bands × 3 rows (126 perms) instead of the planned 32 × 4 — on `tests/fixtures/paraphrases.json`, 32×4 surfaced 31/36 paraphrase pairs as candidates (P(collide | s=0.35) = 0.38); 42×3 surfaces 36/36 with 2/594 unrelated collisions; 64×2 also 36/36 but 18/594 unrelated (more reads). Paraphrase similarity ≥ 0.35, unrelated ≤ 0.10.
- 2026-10-29 — Thresholds live in `MatchConfig`: `prefetch_threshold=0.5`, `hint_threshold=0.25` (hint must be ≤ prefetch) — sit between the fixture's unrelated max (0.10) and paraphrase median (0.58); to be retuned with M5's eval.
- 2026-10-29 — An empty normalized query cannot be signed (`ValueError`) — callers treat it as a miss / refuse to record rather than letting all empty queries collide.
- 2026-10-29 — Band hash is blake2b-64 hex of the band's comma-joined rows — short, stable store keys.
- 2026-10-29 — `NodeResolver` gains `label(node_id) -> str` (breadcrumb) next to `content_hash` and `read`; `content_hash` returns `None` for a deleted node, which counts as changed — the recall contract shows breadcrumbs in hint mode without reading node text; `GenericResolver` defaults the label to the id.
- 2026-10-29 — `text_hash(text)` = first 16 hex chars of sha256 is offered as the default hash helper — short, stable, stdlib.
- 2026-10-29 — Admission also requires a non-empty normalized query and at least one cited node that still resolves; `useful` = cited nodes in citation order with their hash at commit time — a trajectory with nothing to hand back is useless; hashing at commit pins what the answer actually saw.
- 2026-10-29 — Steps are stored as given (tool, args, returned ids); keeping answers out of `args` is the caller's job — ragtrail never receives the answer text in its API.
- 2026-10-29 — Every admitted turn writes a new trajectory, including turns served by a recall hit — new phrasings widen coverage; dedup/merge is deferred until the M5 eval shows store growth matters.
- 2026-10-29 — Ranking: estimated Jaccard desc, then hits desc, then newest; recall walks the ranked list above `hint_threshold` and uses the first trajectory with any still-valid node, marking fully changed ones stale on the way — one dead trajectory does not hide a good older one.
- 2026-10-29 — A miss reports the best candidate's similarity (0.0 if none) — useful for tuning thresholds; `rendered` is empty on a miss so the agent sees nothing.
- 2026-10-29 — Budget: header and footer are always kept; prefetch adds whole node texts in citation order while they fit, lists the rest as one-line refs, and collapses overflow into `(+N more nodes)`; a prefetch where no node text fits is returned as `hint` — never cut a node mid-text; the mode tells the truth about what was included.
- 2026-10-29 — Default `budget_tokens` is 1500, tokens estimated as `ceil(chars / 4)` (pluggable `estimator`) — enough for 2–4 typical sections; no tokenizer dependency in core.
- 2026-10-29 — `recall` increments `hits` on every non-miss — gives ranking and eval a usage signal.
- 2026-10-29 — `turn(...)` recalls on entry and commits on exit; the outcome is set with `t.accept(...)` or `t.outcome`; an exception inside the block drops the turn and propagates — success must be explicit (admission policy), and a failed turn never leaves a trail.
- 2026-10-29 — No `ragtrail[subforest]` extra for now: subforest is not on PyPI and its repo is private, so CI cannot install it. `ragtrail.subforest.SubforestResolver` is typed against a three-method protocol (`get_node`, `ancestors`, `doc_text`) and never imports subforest; CI tests it with a fake tree, and the real-subforest tests and example run locally with `uv run --with-editable ../subforest pytest` (skipped otherwise). Add the extra when subforest is published.
- 2026-10-29 — `SubforestResolver` hashes a node's whole span (subsections included) from the stored doc text, labels skip the `site` node, and dirs/sites have no hash (cannot be cited) — editing a subsection invalidates trails that used its parent, since the agent read that text.
- 2026-10-29 — Examples share a small Markdown corpus in `examples/corpus/` (fictional "Larch" docs); `chunk_rag.py` uses paragraph chunk ids (`c1`…), `subforest_rag.py` uses subforest ids (`n7`…); `tests/test_examples.py` runs both offline — one corpus for both index styles, and the examples cannot rot.
