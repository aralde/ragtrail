# Prior work on caching and reusing LLM agent plans, workflows and trajectories (through Oct 2026)

Scope note: ~16 search/fetch calls. Figures marked "(abstract/snippet)" come from arXiv abstract pages or search snippets, not full-text reading. Figures marked "(full text)" come from the paper's HTML. Peer-review status is given per item. Today: 2026-10-31.

## Q1. Which papers/systems cache or reuse agent plans, workflows, trajectories or tool-call sequences, and how does each work?

### Takeaway
The literature splits into (a) **serving-oriented caches** that reuse plans, skills or tool results to cut cost and latency, with matching by keyword, intent or parameter and accuracy held near parity (APC, AgentReuse, TRIAGE, Hierarchical Caching, TVCache, ToolCaching), and (b) **agent-memory / self-evolution** work that reuses trajectories, workflows or distilled strategies as in-context guidance to *raise* success rates, with matching by embedding or LLM (Synapse, ExpeL, AWM, LEGOMem, ReasoningBank, QCR). Almost none handle staleness of the cached content against a changing corpus. None of the confirmed items targets the retrieval path of a RAG agent.

### Cited Findings

#### A. Serving-oriented plan / skill / tool caches

**Agentic Plan Caching (APC)**: Zhang, Wornow, Wan, Olukotun. **Peer-reviewed: NeurIPS 2025** (arXiv v2 Jan 2026).
- What is cached: "structured plan templates" taken from the planning stage of completed agent runs. On a miss, a large planner generates the plan. After a *successful* run, a rule-based filter pulls key info from the execution log and a lightweight LLM strips context-specific details into a template. Cache generation averages 3.99 s per entry. Eviction is LRU. — [arXiv 2506.14852](https://arxiv.org/abs/2506.14852), [HTML v2](https://arxiv.org/html/2506.14852v2), [OpenReview PDF](https://openreview.net/pdf?id=n4V3MSqK77)
- Matching: a small model (GPT-4o-mini) extracts a keyword for the task's higher-level intent (example: "compute the average of all numbers listed in an external document" → "mean calculation"). The default is **exact match on the keyword**, chosen to minimize false positives. Fuzzy matching was prototyped with all-MiniLM-L6-v2 at threshold 0.8. At 10^6 entries, a hit costs 148,449 μs fuzzy versus 56 μs exact. On a hit, a small LM (LLaMA-3.1-8B) adapts the template into a task-specific plan. — [HTML v2](https://arxiv.org/html/2506.14852v2) (full text)
- Staleness/invalidation: none described. Caching is auto-disabled when the hit rate stays low. — [HTML v2](https://arxiv.org/html/2506.14852v2)
- Evaluation: FinanceBench, QASPER, TabMWP, AIME 2024/2025, GAIA. Architectures: Minion and HF smolagents Open Deep Research. Models: GPT-4o (large planner), LLaMA-3.1-8B (small planner/actor), GPT-4o-mini (keywords/cache generation). Latency test used 100 FinanceBench queries. — [HTML v2](https://arxiv.org/html/2506.14852v2)
- Headline: −50.31% cost and −27.28% latency on average, "while maintaining performance". 96.61% of optimal application performance retained. FinanceBench hit rate 46%. Fuzzy matching raised hits to 54% (>0.8) and 64% (>0.6) but accuracy fell 85.50% → 83.00% / 77.00%. GAIA with Open Deep Research: accuracy 37.58% → 36.97% and cost $69.02 → $16.27. So the result is **near-parity with small losses**. — [arXiv abstract](https://arxiv.org/abs/2506.14852); [HTML v2](https://arxiv.org/html/2506.14852v2)
- RAG relevance: QASPER, FinanceBench and Open Deep Research are document/search workloads, but APC caches the *plan template*, not the documents read.

**AgentReuse ("A Plan Reuse Mechanism for LLM-Driven Agent")**: Li, Wu, Tan. Peer-reviewed in Chinese (Journal of Computer Research and Development, 2024). The English arXiv version is from Dec 2025.
- Caches structured plans. The paper argues raw-text similarity (threshold 0.75) misses requests that differ only in key parameters (city, date). It extracts key parameters, classifies intent, and searches within the intent category. Above a semantic-similarity threshold, it reuses the plan. — [arXiv 2512.21309](https://arxiv.org/abs/2512.21309)
- Headline (abstract/snippet): 93% effective plan reuse rate. Similarity judgment F1 0.9718, accuracy 0.9459. Latency −93.12% vs no reuse and −60.61% vs GPTCache. Baselines: GPTCache, MeanCache. No staleness handling reported in what was read. — [arXiv 2512.21309](https://arxiv.org/abs/2512.21309)

**TRIAGE: Three-level Routing and Intelligent Agent Guidance for Efficient Execution**: R. Wei. **Preprint**, arXiv Sep 2026.
- "Trajectory-as-a-Skill" (TaaS) turns past ReAct trajectories into reusable skills, with frequent patterns auto-extracted into deterministic skills. Routing: L1 identical query → reuse prior result (0 tokens). L2 similar query → deterministic parameter substitution into a skill (0 tokens). L3 novel query → full ReAct, then store the trajectory. — [arXiv 2609.01428](https://arxiv.org/abs/2609.01428)
- Eval: 1,007 security-monitoring queries, plus ToolBench (15 domains, 345 queries). Token savings were 62.3% on security (56.0% of queries at L2, 5.5% at L1) and 76.3% on ToolBench. In an online cold start, the L2 hit rate went 0% → 57% within 100 queries and average token cost went 198 → 74.7. Models were not named on the abstract page, and accuracy impact was not stated there. — [arXiv 2609.01428](https://arxiv.org/abs/2609.01428)
- Note: an unrelated arXiv 2606.32017 is also named "TRIAGE" (role-typed credit assignment for agentic RL). — [arXiv 2606.32017](https://arxiv.org/pdf/2606.32017)

**Hierarchical Caching for Agentic Workflows: A Multi-Level Architecture to Reduce Tool Execution Overhead**: Begum, Scott, Nyarko, Jeihani, Khalifa (Morgan State Univ.). **Peer-reviewed journal: MDPI Machine Learning and Knowledge Extraction 2026, 8(2):30**, published 27 Jan 2026, DOI 10.3390/make8020030.
- Caches at the **workflow level and the tool level**. The tool-level cache holds deterministic results (weather lookups, computation outputs, DB queries) that are "valid across users". It uses **dependency-aware, graph-based invalidation**. The motivating case: plan-level caching misses a shared weather call inside two different workflows. — [MDPI](https://www.mdpi.com/2504-4990/8/2/30), [OpenAlex](https://api.openalex.org/works/doi:10.3390%2FMAKE8020030), [ResearchGate](https://www.researchgate.net/publication/400124581_Hierarchical_Caching_for_Agentic_Workflows_A_Multi-Level_Architecture_to_Reduce_Tool_Execution_Overhead)
- The MDPI page returned 403, so evaluation numbers were **not verified** (see Gaps).

**TVCache: A Stateful Tool-Value Cache for Post-Training LLM Agents**: **preprint**, arXiv Feb 2026.
- Caches tool-call outputs during RL post-training. It argues naive output caching is incorrect because outputs depend on environment state. It keeps a tree of observed tool-call sequences and uses longest-prefix matching. A hit requires the full tool history to match, which guarantees identical state. — [arXiv 2602.10986](https://www.arxiv.org/abs/2602.10986) (abstract/snippet; numbers not read)

**ToolCaching: Towards Efficient Caching for LLM Tool-calling**: **preprint**, arXiv Jan 2026. A feature-driven adaptive cache for tool calls. It says conventional cache policies fail because of heterogeneous request semantics, dynamic workloads and "varying freshness requirements". — [arXiv 2601.15335](https://arxiv.org/abs/2601.15335) (snippet only)

**Other serving-side items (snippet-level only):**
- AgenticCache (embodied agents): queries a runtime cache of frequent plan transitions, and a background updater validates entries with the LLM. — [arXiv 2604.24039](https://arxiv.org/html/2604.24039v1)
- Temporal semantic caching for plan-execute pipelines: argues embedding caches break when validity depends on time, asset or sensor parameters. — [arXiv 2605.20630](https://arxiv.org/html/2605.20630v1)
- GenCache: caching for structurally similar prompts, with >83% hit rate on WebShop. — [arXiv 2511.17565](https://arxiv.org/pdf/2511.17565v1)
- SemReuse: "certified reuse of cached natural-language views for semantic operators". — [arXiv 2610.16035](https://arxiv.org/html/2610.16035)
- "Don't Break the Cache": evaluates **prompt/KV caching** (not plan caching) for long-horizon agents on DeepResearch Bench across OpenAI, Anthropic and Google. — [arXiv 2601.06007](https://arxiv.org/abs/2601.06007v1)
- KV-level agent caching (orthogonal): KVFlow, NeurIPS 2025, prefix caching for multi-agent workflows ([NeurIPS](https://papers.neurips.cc/paper_files/paper/2025/hash/b7971d31a7d5eb0f1eed2f8f6f368195-Abstract-Conference.html)). AgentKVShift, which refreshes only 10–30% of the KV cache ([arXiv 2607.21604](https://arxiv.org/abs/2607.21604)). Cache Engineering for Agents ([arXiv 2610.28577](https://arxiv.org/abs/2610.28577)).
- Open-source, non-peer-reviewed: ThriftLM "plan cache … reuse workflow skeletons, skip repeated planning" ([GitHub](https://github.com/samujure/ThriftLM)). A vendor blog on tool-result caching makes unverified claims (−70% latency, −40–60% cost) ([blog](https://www.channel.tel/blog/tool-result-caching-ai-agents)). A practitioner blog on a "five-layer" agent caching hierarchy ([tianpan.co](https://tianpan.co/blog/2026-04-12-caching-hierarchy-agentic-workloads-five-layers)).

#### B. Record & replay / trajectory reuse

**AgentRR ("Get Experience from Practice: LLM Agents with Record & Replay")**: Feng, …, Xia, Haibo Chen (SJTU). **Preprint**, May 2025.
- Records environment interactions and internal decisions, summarizes them into a structured "experience" (workflow plus constraints) with a **multi-level abstraction** balancing specificity and generality, and replays it on similar tasks. A **"check function" acts as a trust anchor** for completeness and safety during replay. Modes: user-recorded demos, large-small model collaboration, privacy-aware execution, and a shared experience repository. The abstract reports **no quantitative results** (position/system paper). — [arXiv 2505.17716](https://arxiv.org/abs/2505.17716)

**SWE-Replay: Efficient Test-Time Scaling for Software Engineering Agents**: Ding, L. Zhang (UIUC). **Preprint**, Jan 2026.
- Reuses archived trajectories from *earlier trials of the same task*, branching at critical intermediate steps chosen by "significance of repository exploration" instead of resampling from scratch. This is within-task reuse, not cross-query. SWE-Bench Verified: cost "up to 17.4%" lower, "maintaining or even improving performance by up to 3.8%". It also generalizes to SWE-Bench Pro and Multilingual. — [arXiv 2601.22129](https://arxiv.org/abs/2601.22129)

**AgentDiet ("Reducing Cost of LLM Agents with Trajectory Reduction")**: **Peer-reviewed: ACM FSE 2026** (PACMSE Vol. 3, FSE056).
- Not a cache. It prunes useless, redundant and expired information from the *live* trajectory using a cheaper reflection LLM. Input tokens −39.9% to −59.7%, cost −21.1% to −35.9%, performance −1.0% to +2.0% (parity). Models: Claude 4 Sonnet and Gemini 2.5 Pro. Benchmarks: SWE-bench Verified and Multi-SWE-bench Flash. — [arXiv 2509.23586](https://arxiv.org/pdf/2509.23586)

**Beyond Retrieval: Query-Conditioned Reuse of Long-Horizon Agent Trajectories (QCR)**: Li, Wang, Zhang et al. **Preprint**, 13 Aug 2026.
- Treats *post-retrieval reuse* as a separate bottleneck. Retrieved trajectories fail when users, entities, constraints or environment state change. QCR stores a reusable procedure, **bindings to recover, applicability conditions, and verification requirements**. On 2,391 targets across WebArena, WorkArena and AppWorld: 62.3% average success, which is +10.7 points over full-trajectory injection, with 48.9% fewer online tokens. Summary reranking selects a reusable memory for 94.8% of targets and comes within 1.8 points of an oracle selector. Full-trajectory injection degrades as traces grow longer or source-specific values change. — [arXiv 2608.12847](https://arxiv.org/abs/2608.12847)

#### C. Agent memory of workflows / exemplars / strategies (accuracy-oriented)

**Synapse: Trajectory-as-Exemplar Prompting with Memory for Computer Control**: Zheng, Wang, Wang, An. **Peer-reviewed: ICLR 2024**.
- Stores full successful trajectories as exemplars and retrieves them by similarity from memory. MiniWoB++: 99.2% average success across 64 tasks using demos from 48. Mind2Web: +56% relative step success rate over the prior SOTA prompting. The memory component gave +6% step SR in cross-task and cross-website settings. (arXiv v1 reported 98.5% on 63 tasks.) — [ICLR proceedings](https://proceedings.iclr.cc/paper_files/paper/2024/hash/52f050499cf82fa8efb588e263f6f3a7-Abstract-Conference.html), [arXiv 2306.07863](https://arxiv.org/pdf/2306.07863)

**ExpeL: LLM Agents Are Experiential Learners**: Zhao et al. **Peer-reviewed: AAAI 2024**.
- Gathers trial-and-error experiences on training tasks, extracts natural-language insights (ADD/UPVOTE/DOWNVOTE/EDIT), and recalls insights plus similar successful trajectories at inference. Insights help HotpotQA (the only retrieval-QA benchmark in this group), trajectories help ALFWorld, and WebShop needs both. — [arXiv 2308.10144](https://arxiv.org/pdf/2308.10144)

**Agent Workflow Memory (AWM)**: Z. Z. Wang, Mao, Fried, Neubig. **Peer-reviewed: ICML 2025**, PMLR 267:63897–63911.
- Induces reusable workflows (routines with abstracted values) from trajectories and adds them to memory, offline or online. +24.6% relative step SR on Mind2Web (cross-task) and +51.1% relative SR on WebArena, with fewer steps on successful WebArena tasks. Covers 1000+ tasks across 200+ domains. — [PMLR](https://proceedings.mlr.press/v267/wang25bx.html), [arXiv 2409.07429](https://arxiv.org/abs/2409.07429)

**LEGOMem: Modular Procedural Memory for Multi-agent LLM Systems for Workflow Automation**: Han, Couturier et al. (Microsoft). **Peer-reviewed as an AAMAS 2026 extended abstract**. The arXiv version is from Oct 2025.
- Distills successful trajectories into full-task memories (plan plus summarized trace), which go to the orchestrator, and subtask memories (agent behavior, tool use), which go to task agents. Stored in a vector DB. OfficeBench has 300 tasks (148 train/memory, 152 test). Absolute success gains were +12.61, +12.72 and +13.38 points for the GPT-4o, hybrid and GPT-4o-mini teams. It compares against adapted Synapse and AWM. These figures come from secondary summaries and should be verified. — [arXiv 2510.04851](https://arxiv.org/abs/2510.04851v1), [AAMAS 2026 PDF](https://ifaamas.org/Proceedings/aamas2026/pdfs/VLUA1303.pdf), [MSR page](https://www.microsoft.com/en-us/research/publication/legomem-modular-procedural-memory-for-multi-agent-llm-systems-for-workflow-automation/)

**ReasoningBank: Scaling Agent Self-Evolving with Reasoning Memory**: Ouyang, …, Pfister (Google). **Peer-reviewed: ICLR 2026**.
- Stores distilled *reasoning strategies* (title, one-line description, content) from self-judged successes **and failures**, not raw trajectories. Retrieval embeds the query with gemini-embedding-001 and uses cosine similarity, top-k=1 by default, injected into the system prompt. Benchmarks: WebArena, Mind2Web and SWE-Bench-Verified. Backbones: Gemini-2.5-flash/pro and Claude-3.7-sonnet. Up to 20% relative effectiveness gain and up to 16% fewer steps. WebArena SR +8.3, +7.2 and +4.6 points across the three backbones. SWE-Bench-Verified 34.2→38.8 (flash) and 54.0→57.4 (pro). MaTTS k=5 best-of-N on WebArena-Shopping goes 49.7→55.1. It outperforms Synapse (trajectories) and AWM (workflows). — [arXiv 2509.25140](https://arxiv.org/abs/2509.25140), [HTML v2](https://arxiv.org/html/2509.25140v2)

### Inferences
- **Matching spectrum:** exact keyword (APC), intent class plus parameter extraction plus similarity (AgentReuse), exact or parameter-substitution (TRIAGE), exact tool-history prefix (TVCache), dense embeddings (Synapse, ReasoningBank, LEGOMem), LLM summary reranking (QCR). APC's own ablation shows that loosening matching costs accuracy (85.5% → 77.0%). This supports ragtrail's conservative lexical-first MinHash/LSH design with optional SimHash.
- **Outcome-gated admission is common:** APC (successful runs only), AWM, Synapse and LEGOMem (successful trajectories), ReasoningBank (self-judged success and failure). ragtrail's "positive outcome signal" admission matches this practice.
- **Serving caches report parity or small losses. Memory methods report gains.** ragtrail's claims should be framed against the serving group (cost, latency, tool calls at parity) unless "hint" mode can be shown to improve accuracy, as AWM and ReasoningBank-style guidance does.
- **Invalidation is the weakest point of prior art.** Only Hierarchical Caching (graph dependency invalidation), TVCache (state-identical prefix), AgentRR (check function), QCR (applicability and verification conditions) and AgenticCache (LLM validator) address validity at all, and none do it by content hash of the underlying documents. ragtrail's per-node content-hash validation, tenant scoping and TTL appear to be novel in combination.
- **Never caching the answer** separates ragtrail from TRIAGE L1 (which reuses prior results), semantic response caches (GPTCache) and tool-result caches.

### Gaps
- Hierarchical Caching (MDPI MAKE 8(2):30): evaluation setup, hit rates and latency/cost numbers not retrieved (MDPI returned 403).
- TVCache, ToolCaching, AgenticCache, GenCache, SemReuse: numbers not read beyond snippets.
- TRIAGE: models and accuracy not visible on the abstract page.
- AgentRR: no quantitative evaluation found in the abstract. The full PDF was not read.
- LEGOMem figures come from secondary summaries, not the PDF.
- AgentReuse figures come from the abstract or snippet. Its benchmark composition was not read.

## Q2. Is there work that caches the retrieval path of an agentic RAG/search agent (documents read/cited) and validates it against current content?

### Takeaway
I found **no work that caches the cross-query retrieval path of a RAG agent (searches, doc ids opened, cited nodes) and validates it by content hash at read time**. The nearest items cache plan templates for document QA (APC on FinanceBench/QASPER/Open Deep Research), reuse cross-task *evidence* (MERMAIDS, not verified), cache retrieved content *within* a search episode (R1-Searcher++), or distill procedural experience for deep research (APEx, not read).

### Cited Findings
- APC evaluates on document-QA and search-agent workloads (FinanceBench, QASPER, Open Deep Research on GAIA), but caches only the plan template and does no document-level validation. — [HTML v2](https://arxiv.org/html/2506.14852v2)
- MERMAIDS (Apr 2026, venue unclear) adds structured evidence memory and a **cross-task evidence reuse cache** to agentic RAG for multi-hop QA. It reports that sequential queries hit more often than domain-shifting ones. This came from a search snippet, and its invalidation design was not verified. — [ResearchGate](https://www.researchgate.net/publication/404042403_MERMAIDS_Structured_Memory_and_Evidence_Reuse_for_Reducing_Multi-Hop_Retrieval_Hallucinations_in_Agentic_RAG)
- AgentIR / "Reasoning-Aware Retrieval for Deep Research Agents": in ablations, carrying forward prior *queries* helps, adding their reasoning helps more, and carrying forward the *retrieved documents* gives only modest gains because irrelevant docs propagate errors. This is within-episode reuse. — [arXiv 2603.04384](https://arxiv.org/pdf/2603.04384v3)
- R1-Searcher++ caches retrieved content to avoid repeated retrieval within a search process, not across user queries (per a search summary, not verified in the primary source).
- APEx: "Distillation of Agent Procedural Experience for Adaptive Deep Research Question Answering", Sep 2026. Title-level evidence only. — [arXiv 2609.02253](https://arxiv.org/pdf/2609.02253)
- ExpeL is the only classic memory paper with a retrieval-QA benchmark (HotpotQA), where distilled *insights* helped more than trajectories. — [arXiv 2308.10144](https://arxiv.org/pdf/2308.10144)
- QCR finds that reusing whole trajectories degrades when source-specific values change, and that target-bound support with verification requirements does better. This supports ragtrail returning node ids or current text instead of stale content. — [arXiv 2608.12847](https://arxiv.org/abs/2608.12847)
- Staleness risk: a secondary blog reports Databricks findings (Apr 2026) that agents reused stale results from earlier wrong runs with more confidence. Not verified at the primary source. — [Substack](https://thenuancedperspective.substack.com/p/designing-agentic-memory-in-2026)

### Inferences
- ragtrail's specific combination looks unclaimed in the literature found: a path-only record (never the answer), node-level content-hash validation at read time, prefetch/hint modes under a token budget, tenant scoping, and LSH key lookups without a vector DB. The closest conceptual neighbours are APC (cost/latency framing, keyword matching), QCR (applicability and verification on reuse), Hierarchical Caching (tool-level cache plus dependency invalidation) and MERMAIDS (cross-query evidence reuse in agentic RAG).
- AgentIR's finding that carrying forward raw documents adds little or propagates errors suggests evaluating ragtrail's "hint" mode against "prefetch" mode, since prefetch could import noise when a match is imperfect.

### Gaps
- MERMAIDS and APEx were not read in full. Either could partly overlap with ragtrail and should be checked first.
- No systematic SIGIR/CIKM 2026 proceedings sweep was done for "retrieval path cache" or "search session reuse". Classic IR query-log and result caching (search-engine result caches) was outside this pass.
