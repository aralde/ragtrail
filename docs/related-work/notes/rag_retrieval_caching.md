# Retrieval-level caching for RAG and IR: prior art relevant to ragtrail

Scope note: ragtrail caches the retrieval path of an answered question (searches run, node/chunk/doc ids opened, nodes cited), never the answer. It matches similar later questions with MinHash/LSH lexical signatures plus optional embedding SimHash LSH stored as key-value band buckets, with no vector DB. At read time it validates each node's content hash: changed nodes are dropped, and if all nodes changed the lookup is a miss and the trail is marked stale. It also has tenant scoping and TTL. Research for this note was done 2026-10-31. Items marked "[not re-verified this session]" come from background knowledge with a DOI or link. Their bibliographic details are believed correct, but no numbers are given for them.

## Q1. Which works cache retrieved documents/chunks/ids or nearest-neighbour results for similar queries? (what is cached, matching, invalidation, evaluation, accuracy)

### Takeaway
Retrieval-level caching splits into four families:
- **Classic search-engine result caches:** exact query-string match, with a rich literature on invalidation and freshness.
- **Similarity/approximate caches:** in metric or vector spaces (Chierichetti et al., Falchi et al., Pandey et al.), and recently for RAG and vector DBs (Proximity, Aker, ANN-Cache, ARC, CatapultDB).
- **KV-state caches of retrieved chunks:** RAGCache, TurboRAG, CacheBlend, Cache-Craft. These cache model internals keyed by chunk, not query-to-result mappings.
- **LLM response semantic caches:** GPTCache, MeanCache, vCache. These cache answers, which is the opposite of ragtrail's design.

Proximity (Middleware '25) is the closest RAG analogue to ragtrail. It maps a query embedding to the top-k doc ids and uses random-hyperplane (SimHash) LSH buckets, but it caches a single-shot NN result, not a multi-step path, and it does not discuss corpus updates or invalidation.

### Cited Findings

#### A. Approximate/semantic caches of retrieval results for RAG and vector search

**Peer-reviewed**

- **Proximity**: Bergman, Kermarrec, Petrescu, Pires, Randl, de Vos, Zhang, "Leveraging Approximate Caching for Faster Retrieval-Augmented Generation". Accepted at ACM Middleware '25 (arXiv v3, 27 Oct 2025). A workshop version also appears on the EuroMLSys '25 site. — [arXiv 2503.05530](https://arxiv.org/abs/2503.05530); [ACM DL (Middleware)](https://dl.acm.org/doi/pdf/10.1145/3721462.3770776); [EuroMLSys'25 PDF](https://euromlsys.eu/pdf/euromlsys25-13.pdf)
  - **Cache key and value:** The key is the query embedding. The value is the list of top-k nearest document indices returned by the vector DB, not the document text. — [arXiv HTML v3](https://arxiv.org/html/2503.05530v3)
  - **Matching:** A hit requires distance ≤ τ, using the vector DB's distance function. τ is a manually set global constant.
  - **Proximity-LSH:** Uses random-hyperplane LSH (Charikar 2002). L hyperplanes give an L-bit bucket signature, with L = 8 in most experiments. Each bucket is a small flat cache of b = 20 entries with FIFO or LRU eviction per bucket and no global policy. — [arXiv HTML v3](https://arxiv.org/html/2503.05530v3)
  - **Hit rates:** Up to 93% on MMLU and 98.4% on MedRAG at τ ≥ 5 (flat). About 79.6% on MedRAG-Zipf with LSH. About 50% on TripClick. — [arXiv HTML v3](https://arxiv.org/html/2503.05530v3)
  - **Latency:** Retrieval latency falls by up to 59% (MMLU) and 75% (MedRAG) with the flat cache. With LSH on skewed MedRAG-Zipf, DB calls fall by 77.2% and retrieval latency by 72.5%. LSH lookup stays at 4.8 µs regardless of cache size, while the flat cache grows to 13.0 ms at 200k entries. — [arXiv HTML v3](https://arxiv.org/html/2503.05530v3); [abstract](https://arxiv.org/abs/2503.05530)
  - **Accuracy:** Recall is 99.4% at τ = 1.0 and 92.2% at τ = 2.5 on TripClick. On MedRAG-Zipf, k-recall stays near 100% for τ < 7.5 and accuracy degrades at τ = 10: LSH-LRU accuracy is 85.8% at τ = 2.5 and 84.1% at τ = 10. MMLU accuracy ranges from 47.9% to 50.2% across settings. — [arXiv HTML v3](https://arxiv.org/html/2503.05530v3)
  - **Invalidation:** Corpus updates, invalidation and staleness are **not discussed**. Multi-step or agentic retrieval is not mentioned. — [arXiv HTML v3](https://arxiv.org/html/2503.05530v3)

- **Aker**: Oh, Kang, Kim, Lu, Liu, Zhang, Chen, Won, "Density-Aware Approximate Caching for Vector Search". PVLDB Vol. 19 No. 10, pp. 2727-2740, 2026; extended version on arXiv, 3 Sep 2026. — [arXiv 2609.03712](https://arxiv.org/abs/2609.03712)
  - **What is cached:** Results of past queries, reused to serve similar future queries in disk-based ANN (integrated into pgvector).
  - **Matching:** Each entry has its own threshold, adjusted dynamically from observed hit patterns to fit local neighbour density.
  - **Freshness:** A "del-consistency" model applies deletions eagerly and insertions lazily, plus a low-overhead refresh that bounds staleness.
  - **Results:** Up to +64 pp recall over prior approximate caches, up to 3.2x QPS, and 0.6x the memory of pgvector shared buffers. — [arXiv 2609.03712](https://arxiv.org/abs/2609.03712)
  - **Relevance:** This is the clearest vector-cache work with an explicit consistency model under corpus updates.

**Preprints**

- **ARC (Agent RAG Cache)**: Lin, Peng, Li, Lin, Zhu, Zhang, "Cache Mechanism for Agent RAG Systems", arXiv 2511.02919 (Nov 2025). — [arXiv](https://arxiv.org/abs/2511.02919)
  - **What is cached:** A small, high-value corpus per agent. This is a passage-level cache, not a query-to-result map.
  - **Scoring:** Combines historical query patterns with embedding-space geometry: a Distance-Rank Frequency score that weights higher-ranked, closer retrievals, plus a hubness score. — [arXiv](https://arxiv.org/abs/2511.02919); [arXiv HTML](https://arxiv.org/html/2511.02919v1)
  - **Results:** The cache is 0.015% of the corpus, reaches up to 79.8% has-answer rate, and cuts average retrieval latency by 80%. — [arXiv](https://arxiv.org/abs/2511.02919)
  - **Invalidation:** The abstract says the cache is "maintained/updated", but the abstract does not specify invalidation rules.
  - **Datasets:** Secondary summaries name SQuAD, MMLU and AdversarialQA, unconfirmed from the primary text. — [Moonlight review](https://www.themoonlight.io/review/cache-mechanism-for-agent-rag-systems)
- **ANN-Cache**: Li, He, Zhang, "Accelerating Approximate Nearest Neighbor Search via Caching", TechRxiv, July 2025. An LSH-based cache of historical queries and their results. Reports 3x-9x speedup with higher accuracy than baselines (per search summary; full text not read). — [TechRxiv](https://www.techrxiv.org/doi/full/10.36227/techrxiv.175339599.94104409/v1)
- **CatapultDB**: Abuzakuk, Kermarrec, Pires, Randl, de Vos (same group as Proximity), "Catapults to the Rescue: Accelerating Vector Search by Exploiting Query Locality", arXiv 2603.02164 (Mar 2026). — [arXiv](https://arxiv.org/abs/2603.02164)
  - **What is cached:** Not results. It caches shortcut edges ("catapults") from query regions to frequently visited graph nodes, so queries start at better entry points.
  - **Results:** Up to 2.51x throughput over DiskANN at equivalent or better recall.
  - **Updates:** Supports dynamic insertions; invalidation details are not given in the abstract.
- **VoiceAgentRAG**, arXiv 2603.02206: caches document chunks rather than query answers, with TTL expiry (default 300 s) and LRU eviction. Its authors report that indexing by the predicted query's embedding gave irrelevant hits, so they indexed by document embeddings instead (per search summary). — [arXiv PDF](https://arxiv.org/pdf/2603.02206)
- **RAGBoost**, arXiv 2511.03475: retrieved documents overlap heavily across related queries, yet the KV-cache hit rate on MultihopRAG with Qwen3-32B is only 4.6%. It reorders retrieved documents to increase reuse. — [arXiv HTML](https://arxiv.org/html/2511.03475v1)

#### B. Classic similarity caching (metric spaces, LSH, approximate hits)

All peer-reviewed.

- **Similarity Caching**: Chierichetti, Kumar, Vassilvitskii, PODS 2009 (DOI 10.1145/1559795.1559815). — [BibSLEIGH](https://bibtex.github.io/PODS-2009-ChierichettiKV.html); [IRIS](https://iris.uniroma1.it/handle/11573/497784)
  - **Problem:** Formalises caching where a hit may return a cached item similar, but not identical, to the query, within threshold r.
  - **Results:** Without extra cache size or threshold slack relative to the offline optimum, the problem is intractable. Hardness depends on the metric-space complexity. The paper also studies query-dependent thresholds and a smooth trade-off between miss cost and similarity.
- **Nearest-Neighbor Caching for Content-Match Applications**: Pandey, Broder, Chierichetti, Josifovski, Kumar, Vassilvitskii, WWW 2009, pp. 441-450. Applies similarity caching to contextual advertising: a hit occurs if the request is similar to a cached item. — [Webis IR anthology](https://ir.webis.de/anthology/2009.wwwconf_conference-2009.45/); [ResearchGate](https://www.researchgate.net/publication/221023479_Nearest-neighbor_caching_for_content-match_applications)
- **A Metric Cache for Similarity Search**: Falchi, Lucchese, Orlando, Perego, Rabitti, LSDS-IR @ CIKM 2008, pp. 43-50 (DOI 10.1145/1458469.1458473). — [Webis IR anthology](https://ir.webis.de/anthology/2008.cikm_workshop-2008lsdsir.7); [dblp](https://dblp.uni-trier.de/rec/conf/cikm/FalchiLOPR08.html)
  - **What is cached:** k-NN result sets in metric space. When there is no exact match, it returns approximate result sets with quality guarantees by exploiting query-to-cache similarity.
  - **Evaluation:** About 1M images; robust to cache pollution by near-duplicate queries.
  - **Follow-ups:** "Caching algorithms for similarity search" (SEBD 2009) — [CNR](https://data.cnr.it/data/http:/www.cnr.it/ontology/cnr/individuo/prodotto/ID91956); "Similarity caching in large-scale image retrieval" (QCache for kNN and range queries) — [Bohrium listing](https://www.bohrium.com/paper-details/similarity-caching-in-large-scale-image-retrieval/811682275509927937-2438). Attribution of the latter was not confirmed.

#### C. Classic search-engine query result caching, invalidation and freshness

All peer-reviewed.

- **Caching Search Engine Results over Incremental Indices**: Blanco, Bortnikov, Junqueira, Lempel, Telloli, Zaragoza, SIGIR 2010 (full paper; WWW 2010 poster pp. 1065-1066). — [PDF (UDC)](https://www.dc.fi.udc.es/~roi/publications/sigir2010b.pdf); [WWW poster](https://archives.iw3c2.org/www2010/proceedings/www/p1065.pdf)
  - **Mechanism:** Cache Invalidation Predictors (CIPs) sit between indexer and runtime and selectively invalidate only the queries whose results are affected by index updates.
  - **Results:** On Wikipedia plus a Yahoo! query log, up to 30% fewer unnecessary query evaluations than TTL-based invalidation.
- **A Refreshing Perspective of Search Engine Caching**: Cambazoglu, Junqueira, Plachouras, Banachowski, Cui, Lim, Bridge, WWW 2010, pp. 181-190 (DOI 10.1145/1772690.1772710). Proactively refreshes stale entries (TTL plus a prioritised refresh driven by idle backend capacity) instead of only evicting them. Claims to be the first to study refreshing result entries. — [PDF](https://www.site.uottawa.ca/~nelkadri/CSI5389/Papers/27-Cambazoglu_et_al_WWW2010.pdf); [Webis](https://ir.webis.de/anthology/2010.wwwconf_conference-2010.19/)
- **Timestamp-based Result Cache Invalidation for Web Search Engines**: Alici, Altingövde, Ozcan, Cambazoglu, Ulusoy, SIGIR 2011, pp. 973-982 (DOI 10.1145/2009916.2010046). — [Bilkent repository](https://repository.bilkent.edu.tr/items/557f4a79-6388-4e1a-9a3c-4928842c2956); [METU PDF](https://open.metu.edu.tr/bitstream/handle/11511/48372/index.pdf); [dblp](https://dblp.org/rec/bibtex/conf/sigir/AliciAOCU11)
  - **Mechanism:** Each cache entry is tagged with its generation time. On a hit, that timestamp is compared with the timestamps of the associated posting lists and documents to decide whether the cached result is stale.
  - **Staleness definition:** Any change in the ids or the order of result documents.
  - **Results:** Per a third-party summary, it beats TTL and is generally below CIP, but is simpler. — [Liner review](https://liner.com/review/timestampbased-result-cache-invalidation-for-web-search-engines)
- **Caching for Realtime Search**: Bortnikov, Lempel, Vornovitsky, ECIR 2011 (DOI 10.1007/978-3-642-20161-5_12). LRU "completely fails to guarantee freshness over time", while CIPs serve 97% of queries with fresh results. Attribution comes from citing literature. — [Springer DOI](https://dx.doi.org/10.1007/978-3-642-20161-5_12)
- **Foundational result-caching papers [not re-verified this session]:**
  - Markatos, "On caching search engine query results", Computer Communications 24(2), 2001 — [DOI](https://doi.org/10.1016/S0140-3664(00)00308-X)
  - Lempel & Moran, "Predictive caching and prefetching of query results in search engines", WWW 2003 — [DOI](https://doi.org/10.1145/775152.775156)
  - Fagni, Perego, Silvestri, Orlando, "Boosting the performance of Web search engines: caching and prefetching query results by exploiting historical usage data" (static-dynamic cache, SDC), ACM TOIS 24(1), 2006 — [DOI](https://doi.org/10.1145/1125857.1125859)
  - Baeza-Yates, Gionis, Junqueira, Murdock, Plachouras, Silvestri, "The impact of caching on search engines", SIGIR 2007 — [DOI](https://doi.org/10.1145/1277741.1277775)
  - These papers use exact query-string keys, with static, dynamic or hybrid admission and eviction. No numbers are given here because they were not verified.

#### D. KV-state caching of retrieved chunks (caches model internals, not retrieval decisions)

- **RAGCache**: Jin, Zhang, Jiang, Liu, Liu, Liu, Jin (PKU). arXiv 2404.12457 (Apr 2024); later in ACM TOCS (DOI 10.1145/3768628). — [arXiv](https://arxiv.org/abs/2404.12457); [ACM DL](https://dl.acm.org/doi/full/10.1145/3768628)
  - **What is cached:** Intermediate (KV) states of retrieved documents, organised as a "knowledge tree" across GPU and host memory. Replacement is aware of LLM inference and retrieval patterns, and retrieval overlaps with inference.
  - **Results:** Up to 4x lower TTFT and 2.1x higher throughput versus vLLM + Faiss.
  - **Invalidation:** Corpus-update invalidation is not described in the abstract.
- **TurboRAG**: Lu, Wang, Rong, Chen, Tang, arXiv 2410.07590 (Oct 2024, preprint). Precomputes document KV caches offline. TTFT is up to 9.4x lower (avg. 8.6x), with "comparable performance" to standard RAG. Requires fine-tuning the LLM and adjusting the attention mask and positions. — [arXiv](https://arxiv.org/abs/2410.07590)
- **CacheBlend**: Yao, Li, Liu, Ray, Cheng, Zhang, Du, Lu, Jiang, arXiv 2405.16444. Published at EuroSys 2025 [venue from background knowledge, not re-verified]. Reuses precomputed chunk KV caches at non-prefix positions by selectively recomputing a small subset of tokens. TTFT is 2.2-3.3x lower and throughput 2.8-5x higher than full recompute, "without compromising generation quality". — [arXiv](https://arxiv.org/abs/2405.16444)
- **Cache-Craft**: Agarwal et al. (Adobe Research), SIGMOD 2025, arXiv 2502.15734. — [arXiv](https://arxiv.org/abs/2502.15734)
  - **What is cached:** "Chunk-caches" (KV of retrieved chunks). It identifies reusable chunk-caches, repairs them by recomputing a small fraction, and manages storage and eviction.
  - **Results:** 51% less redundant compute than prefix caching and 75% less than full recompute. In production it achieves 1.6x throughput and 2x lower end-to-end latency (LLaMA-3-8B/70B). Naive reuse degrades quality.
- **AgentKVShift**, arXiv 2607.21604: KV reuse for agentic memory systems. It argues that reused KV states accumulate errors and corrects the values of unrefreshed tokens (search snippet only). — [arXiv PDF](https://arxiv.org/pdf/2607.21604)

#### E. LLM response semantic caches (adjacent; they cache answers)

- **GPTCache**: Bang, NLP-OSS @ EMNLP 2023, pp. 212-218. An open-source embedding-similarity cache of LLM responses. — [ACL Anthology](https://aclanthology.org/2023.nlposs-1.24/)
- **MeanCache**: Gill et al., IPDPS 2025 (arXiv 2403.02694). A user-side semantic cache with a federated-learned similarity model. Versus GPTCache: +17% F-score, about +20% precision, and 83% less storage. — [arXiv](https://arxiv.org/abs/2403.02694v4)
- **vCache**: Schroeder et al., ICLR 2026 (arXiv 2502.03771). Learns an online, per-entry similarity threshold with a user-specified error-rate guarantee. Reports up to 12.5x higher hit rate and 26x lower error than static-threshold baselines. — [arXiv HTML](https://arxiv.org/html/2502.03771v5); [ICLR](https://iclr.cc/virtual/2026/poster/10006471)
- **GPT Semantic Cache**: Regmi & Pun, arXiv 2411.05276 (preprint). Redis-stored query embeddings; up to 68.8% fewer API calls. — [arXiv](https://arxiv.org/abs/2411.05276)

#### F. Practitioner and blog sources (non-peer-reviewed)

- **Redis:** The Redis agentic-retrieval guide recommends caching evidence separately from answers, using tiered TTLs (retrieval results expiring in minutes to hours), checking permissions before reuse, and starting semantic thresholds around 0.95. It cites the ARC algorithm. — [Redis blog](https://redis.io/blog/agentic-retrieval-techniques/)
- **hemju.me:** Argues that a vector DB is effectively a derived cache. Recommends stable chunk IDs, upserts, tombstones, embedding-model version tags, and TTL combined with event-driven invalidation, with the version or timestamp in the cache key. — [hemju.me](https://hemju.me/posts/post-018/)
- **DEV Community:** Warns that cache keys missing a tenant or org ID can leak chunks across tenants. Recommends per-knowledge-base tag purges (the post is promotional). — [DEV](https://dev.to/alok1663/rag-apps-your-vector-db-bill-is-mostly-deja-vu-444f)
- **Medium:** Proposes caching partial successful trajectories for repeated multi-hop questions. — [Medium (Spacagna)](https://gm-spacagna.medium.com/caching-strategies-for-agentic-retrieval-systems-98de4f8848ff)

### Inferences
- ragtrail's matching (SimHash band buckets over embeddings) is close to Proximity-LSH's random-hyperplane buckets. Its lexical MinHash/LSH path has older precedents in similarity caching (Chierichetti et al.; Pandey et al.). Neither the LSH lookup itself nor "cache retrieval ids instead of answers" is novel. Proximity already caches top-k doc **indices**, not text or answers.
- What sets ragtrail apart from Proximity, ARC, Aker and ANN-Cache:
  - It caches a **multi-step path**: searches, opened nodes, and the cited subset.
  - It records **which nodes were cited**, a usefulness signal comparable to ARC's DRF rank weighting but taken from the agent's own citations.
  - It validates content hashes per node at read time.
  - It applies tenant scoping.
- The KV-cache family (RAGCache, TurboRAG, CacheBlend, Cache-Craft) is complementary rather than competing. It speeds up prefill for chunks once retrieved, while ragtrail skips the retrieval and search steps. The two could stack.
- Accuracy effects in approximate retrieval caches depend on the threshold. Proximity shows near-full recall at small τ and degradation at large τ. Aker and vCache argue that a single global threshold is inadequate and use per-entry adaptive thresholds. This is relevant if ragtrail uses fixed LSH band and threshold settings.

### Gaps
- Full texts of ANN-Cache, ARC (datasets and eviction details) and the Falchi et al. experiments were not read. Their numbers come from abstracts or summaries.
- RAGCache's journal venue (TOCS) was inferred from the ACM DL DOI listing in search results and was not opened directly.
- CacheBlend's EuroSys 2025 venue was not re-verified this session.
- No numbers are given for Markatos 2001, Lempel & Moran 2003, Fagni et al. 2006 or Baeza-Yates et al. 2007. They were not re-verified.
- QVCache (cited by CatapultDB as a query-aware vector cache) was not located.

## Q2. Any work that validates cached retrieval results against document content hashes or versions, or downgrades partially stale cache entries?

### Takeaway
The closest prior art is from classic web-search result caching. Alici et al. (SIGIR 2011) validate a cached result at hit time by comparing its generation timestamp with the timestamps of the associated documents and posting lists. Blanco et al. (SIGIR 2010) predict which entries an index update invalidates. Aker (PVLDB 2026) applies deletions eagerly to cached vector results.

No work found validates per-document **content hashes** at read time and serves a **partially pruned** entry (drop changed items, keep the rest, mark the entry stale only when all items changed). ragtrail's validation design appears unreported in the retrieval-cache literature.

### Cited Findings
- **Timestamp check at hit time:** Alici et al. compare cache-entry timestamps with document and posting-list timestamps on a hit to decide staleness. A result counts as stale if the ids or order of its documents change, so the decision is binary (stale or fresh, not partial reuse). — [Bilkent](https://repository.bilkent.edu.tr/items/557f4a79-6388-4e1a-9a3c-4928842c2956); [METU PDF](https://open.metu.edu.tr/bitstream/handle/11511/48372/index.pdf)
- **Selective invalidation on update:** Blanco et al. use CIPs to invalidate only entries affected by updates, with up to 30% fewer unnecessary re-evaluations than TTL. — [SIGIR'10 PDF](https://www.dc.fi.udc.es/~roi/publications/sigir2010b.pdf)
- **Refresh on idle capacity:** Cambazoglu et al. refresh stale entries proactively, combining TTL with refresh prioritisation, instead of only invalidating them. — [WWW'10 PDF](https://www.site.uottawa.ca/~nelkadri/CSI5389/Papers/27-Cambazoglu_et_al_WWW2010.pdf)
- **CIPs under real-time updates:** In real-time search, LRU fails to guarantee freshness, while CIPs serve 97% of queries fresh. — [ECIR'11 DOI](https://dx.doi.org/10.1007/978-3-642-20161-5_12)
- **Eager deletions in vector caches:** Aker's del-consistency applies deletions eagerly and insertions lazily to cached vector-search results, with bounded-staleness refresh. This is the nearest analogue to "drop changed or removed items from a cached result set". — [arXiv 2609.03712](https://arxiv.org/abs/2609.03712)
- **No invalidation in Proximity:** Proximity does not discuss corpus updates, invalidation or staleness. — [arXiv HTML v3](https://arxiv.org/html/2503.05530v3)
- **Practitioner advice:** Include a source version or timestamp in cache keys, combine TTL with event-driven invalidation, and use embedding-model version tags. — [hemju.me](https://hemju.me/posts/post-018/); [Redis blog](https://redis.io/blog/agentic-retrieval-techniques/)
- **KV caches:** KV-cache systems "repair" reused chunk caches by selective recomputation (CacheBlend, Cache-Craft). That is about cross-attention context, not source-content changes. — [CacheBlend](https://arxiv.org/abs/2405.16444); [Cache-Craft](https://arxiv.org/abs/2502.15734)

### Inferences
- ragtrail's per-node content-hash check is a content-addressed version of Alici et al.'s timestamp check, moved from index posting lists to individual nodes. Its partial downgrade (keep the unchanged nodes) is a new twist: classic work treats a result as atomic, so any change in ids or order makes it stale.
- Classic work flags a trade-off that ragtrail should acknowledge. Hash or timestamp validation detects **changed** cached items, but not **new** documents that would now rank higher (false freshness). Blanco et al. and Aker address insertions explicitly (CIP prediction; lazy insertion with bounded staleness). ragtrail's TTL is the only guard against this "missing new evidence" case.

### Gaps
- No paper found that uses cryptographic content hashes for retrieval-cache validation. It may exist in systems or industry documentation (for example, prefix-hash keys in KV-cache stores), but no citable retrieval-level source was found.
- Alici et al.'s quantitative results were not extracted from the full paper.

## Q3. Any work specifically on caching for multi-step/agentic retrieval (several search/read calls per question) rather than single-shot RAG?

### Takeaway
This area is thin. ARC (arXiv, Nov 2025) is the only retrieval cache framed for "Agent RAG". It caches a small per-agent passage corpus, not per-question paths. Agentic Plan Caching (NeurIPS 2025) caches plan **templates** from completed agent runs and matches new tasks by keyword. That is the closest conceptual neighbour to ragtrail's trajectory caching, but it caches plans, not retrieval ids.

No peer-reviewed work found caches the full **retrieval trajectory** (queries, opened ids, cited ids) for reuse on similar later questions with content validation.

### Cited Findings
- **Agentic Plan Caching (APC):** Zhang, Wornow, Wan, Olukotun (Stanford), NeurIPS 2025, arXiv 2506.14852 (v2 Jan 2026). — [arXiv](https://arxiv.org/abs/2506.14852); [NeurIPS](https://neurips.cc/virtual/2025/poster/116166)
  - **Mechanism:** Extracts structured plan templates from completed plan-then-act executions at test time, matches new requests by keyword extraction, and adapts the plans with a lightweight model.
  - **Results:** On average 50.31% lower cost and 27.28% lower latency, keeping 96.61% of optimal accuracy (v2 numbers; v1 reported 46.62% cost reduction).
  - **Argument:** Semantic and context caching are inadequate when outputs depend on external data. Tested with an Open Deep Research agent on GAIA. — [arXiv HTML v2](https://arxiv.org/html/2506.14852v2)
- **ARC:** The only cache paper explicitly framed for agent RAG. It builds per-agent passage caches from query history and embedding geometry, at 0.015% of the corpus, up to 79.8% has-answer rate and 80% lower retrieval latency. — [arXiv 2511.02919](https://arxiv.org/abs/2511.02919)
- **Workload-Aware Caching for Multi-Agent Systems**, arXiv 2607.20495 (2026): caches intermediate node results in multi-agent DAGs, using invocation counts as a reuse proxy (search summary only). — [arXiv HTML](https://arxiv.org/html/2607.20495v1)
- **DeepPlanner**, arXiv 2510.12979: caches search queries and their results inside one run for later browsing steps. This is intra-trajectory reuse, not cross-question. — [arXiv PDF](https://arxiv.org/pdf/2510.12979)
- **"Don't Break the Cache"**, arXiv 2601.06007 (Jan 2026): evaluates provider prompt caching on DeepResearch Bench agents with 30-50+ tool calls. It suggests practitioners consider caching tool calls and results, but it is about prompt/KV caching, not cross-query retrieval reuse. — [arXiv PDF](https://arxiv.org/pdf/2601.06007)
- **Experience and trajectory reuse:** These store agent trajectories as in-context exemplars, not as a retrieval shortcut with validation.
  - "Retrieval-Augmented LLM Agents: Learning to Learn from Experience" (2026) retrieves the top-K past trajectories for a new task. — [alphaXiv 2603.18272](https://www.alphaxiv.org/abs/2603.18272)
  - Doctor-RAG (arXiv 2604.00865) keeps validated prefix steps of failed agentic-RAG trajectories and repairs only at the failure point. — [arXiv PDF](https://arxiv.org/pdf/2604.00865)
- **Practitioner posts:** These propose caching partial or complete successful trajectories for repeated multi-hop questions, and caching retrieval across agent steps, without evaluation. — [Medium (Spacagna)](https://gm-spacagna.medium.com/caching-strategies-for-agentic-retrieval-systems-98de4f8848ff); [Redis blog](https://redis.io/blog/agentic-retrieval-techniques/); [Towards Data Science](https://towardsdatascience.com/zero-waste-agentic-rag-designing-caching-architectures-to-minimize-latency-and-llm-costs-at-scale/)
- **Overlap evidence:** Retrieved documents overlap substantially across related multi-hop queries (MultihopRAG), which supports the premise of cross-question reuse. Yet the naive KV hit rate there was only 4.6%. — [RAGBoost arXiv HTML](https://arxiv.org/html/2511.03475v1)

### Inferences
- ragtrail fills a gap between the following:
  - APC: task-level reuse of **plans**, keyword match, no content validation.
  - Proximity, Aker and ARC: reuse of **single-shot retrieval results** or passages, embedding match, little or no per-item validation except Aker's deletions.
  - Classic search caches: exact match, with strong invalidation theory.
- ragtrail's combination of multi-step path, cited-node subset, LSH lookup without a vector DB, per-node hash validation with partial downgrade, and tenant scope and TTL was not found in any single prior work.
- Evaluation baselines suggested by the literature:
  - Proximity-style top-k id cache, for single-shot reuse.
  - APC, for task-level reuse.
  - ARC, for an agent passage cache.
  - TTL-only invalidation versus validation-based invalidation, following the CIP and Alici et al. comparisons.
- Metrics to report, following Proximity, ARC and APC: hit rate, retrieval calls avoided, end-task accuracy or recall versus the similarity threshold, and stale-serve rate under corpus edits.

### Gaps
- No peer-reviewed benchmark exists for cross-question caching of agentic retrieval. Evaluation would need to be built, for example from multi-hop QA (MultihopRAG, HotpotQA) with paraphrased repeats and controlled corpus edits.
- Workload-Aware Caching (2607.20495), AgentKVShift (2607.21604) and Doctor-RAG (2604.00865) were seen only through search snippets. Their details and venues are unverified.
- Coverage through October 2026 relies on web search. Very recent venue proceedings (for example SIGIR/VLDB/EuroSys 2026 papers not on arXiv) may be missing.
