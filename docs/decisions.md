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
