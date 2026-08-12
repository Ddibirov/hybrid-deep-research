---
name: hybrid-deep-research
description: >-
  Use when user needs comprehensive multi-source research, deep analysis, or structured report synthesis from web + social sources.
  Multi-round hybrid research pipeline. Combines iterative deepening,
  parallel subagents, director/investigator pattern, social signal collection
  (Reddit, X, HN, YouTube, GitHub), and verification with retry.
  Use when user asks for "deep research", "research report", "investigate X",
  "what's happening with Y", "comprehensive analysis of Z", or any question
  requiring 5+ sources synthesized into a structured report with citations.
version: 4.8.0
author: Ddibirov
license: MIT
metadata:
  hermes:
    tags: [research, deep-research, multi-agent, parallel, social, hybrid]
    related_skills: [deep-research, omh-deep-research, last30days, prompt-master]
---

# Hybrid Deep Research

Multi-round research pipeline. All roles run on one model (set via `delegation.model` in config, or your agent framework's equivalent). Social + web sources, verification with retry.

## When to Use

- Research question needs 5+ sources synthesized into structured report
- Topic spans both traditional web AND social media discussion
- User wants "what people are actually saying" (social signals)
- Deep investigation requiring iterative refinement
- Comparative analysis needing verified facts

**When NOT to Use:**
- Quick factual lookup (one web_search suffices)
- Known-answer questions
- Real-time price/feed data only

## Execution Mode

**Silent execution.** The user gives a research request and receives the final report. Nothing in between. This is non-negotiable — the user explicitly corrected this behavior.

- Do NOT show intermediate phases, progress updates, logs, or statistics
- Do NOT ask for brief approval unless the user explicitly wants it — use the question to auto-detect scope and proceed
- Do NOT output "Phase 1:...", "Phase 2:...", "Using model:...". "Round 1...", "Findings:...", "Gap Check:...", "Director Decision:..." or any pipeline internals
- Do NOT show todo lists, gap analysis, director decisions, or verification results to the user
- DO save the report to `.hybrid-research/{slug}/{slug}.md`
- DO send the report content to the user as the final message
- If the research fails (search unavailable, all investigators crash), send a brief error message — not pipeline diagnostics

The user sees: request → result. That's it.

## Runtime scripts (v6, from the reliability fork)

`scripts/` contains a deterministic runtime layer copied from the carlosmartinezfyd fork (v6.0.0, 2026-08-10): source registry, claim ledger, research state/budgets, HTTP checker, report validator, finalizer, claim-marker helper, semantic fact-check, citation scoring, deterministic dedup, coverage assertions, structured escalations, benchmark runner (89+ unit tests in `tests/`). These enforce invariants that LLM prompts cannot be trusted to enforce (URL fabrication, citation integrity, status self-certification).

**Maintenance rule (session-tested 2026-08-12):** every new runtime script ships with tests — new script → new test file in `tests/`, new behavior → new test class in the existing file. Run the whole suite before trusting a change: `cd <skill_dir> && python3 -m pytest tests/ -q`. The v4.8.0 round confirmed the suite earns its cost: it caught a `penalty` UnboundLocalError in benchmark.py (rubric division when `total_fc == 0` — guard the factor) and a check_coverage false positive (domain-independence flagged claims with ONE source as mirror inflation — the check must require ≥2 sources before demanding different domains).

**Decision (Сэр, 2026-08-10): quality beats the "no code" marketing fit. Runtime layer is accepted.** Integrate registry+ledger+finalizer as the core: the orchestrator (main session) maintains the journals after each round — subagents return findings and never mutate shared files. Full analysis, per-script inventory, and adopt decision: `references/fork-v6-runtime.md`.
Exact marker/citation format that `verify_report.py` demands (hard-won, costly to rediscover): `references/verify-report-citation-format.md`.
Improvement candidates from the 2026-08 dogfood run (benchmarks, adaptive compute, verification, social): `references/improvement-candidates-2026-08.md`. Adopted into v4.4.0 (2026-08-11): abstention rule (Phase 6), falsification round (Phase 5.5), adaptive stop (Director trigger 5). Do not re-propose these as new ideas.
Evidence base from the 2026-08-11 web research round (arXiv "Cited but Not Verified", DeepResearchBench/DRACO/DEER, Zep CoVE, Anthropic engineering): `references/research-evidence-2026-08.md`. Adopted into v4.6.0: Phase 7.5 semantic fact-check, per-round verification gate, low-confidence escalation, eval_citations triad. Do not re-propose these as new ideas.
Ecosystem snapshot 2026-08-11 (MCP servers, open frameworks, Odysseus rename to `odysseus-dev`, skills standard) + 7 improvement candidates — **ALL ADOPTED into v4.8.0 (2026-08-12)**: repair round (Phase 7.6), DRACO rubric scoring (`rubric_*` in benchmark), deterministic dedup (`dedup_claims.py`), coverage assertions (`check_coverage.py`), per-subtopic saturation (`research_state.subtopic_saturated`), structured escalations (`escalations.py` + `needs_review` rule in finalize), verbatim numeric check (`numeric_check` in fact_check_claims + `numeric_precision` metric). Do not re-propose these as new ideas: `references/ecosystem-2026-08.md`.
Competitor found 2026-08-12: **SenseNova sn-deep-research** (OpenSenseNova/SenseNova-Skills, SenseTime, 4.9k★ MIT, active) — 9 agents (scout/plan/research/review/report-planner/report-writer/report-stitcher/supplement-planner/perspective), 3 modes (quick/normal/heavy), **source_cache content-hash snapshots** (`url_sha256/content_sha256.md` + `contains_direct_quote` mechanical verbatim-quote check — directly implements our queued "verbatim numeric check" candidate), ~3.7k lines of schema validators (validate_evidence/outline/plan), live progress WebUI, language anchoring. NO falsification round, NO freeze gate, NO benchmark runner. Full comparison + repo inspection recipe: `references/sensenova-sn-deep-research.md`.

## Architecture

All roles share the same model. `delegate_task` does not support per-call model override.

```
USER INPUT
    ↓
┌──────────────────────────┐
│ 1. PROMPT MASTER         │  All roles = delegation.model
│    Brief generation      │  Intent → category → brief
│    + category detection  │
└────────────┬─────────────┘
             ↓
┌──────────────────────────┐
│ 1b. BRIEF APPROVAL       │  Human-in-the-loop:
│    (optional)            │  confirm/adjust scope + category
└────────────┬─────────────┘
             ↓
┌──────────────────────────┐
│ 2. DIRECTOR              │  Same model
│    Decompose + route     │  Brief → subtopics × source matrix
└────────────┬─────────────┘
             ↓
    ╔═══════════════════════════════════════════════╗
    ║            ROUND LOOP (1-N rounds)             ║
    ║                                                ║
    ║  ┌──────────────────────────────────────────┐  ║
    ║  │ 3. INVESTIGATORS (parallel, same model)  │  ║
    ║  │ ┌──────────┐ ┌──────────┐ ┌──────────┐  │  ║
    ║  │ │  Web     │ │  Social  │ │  GitHub  │  │  ║
    ║  │ │ Research │ │ Research │ │ Research │  │  ║
    ║  │ └──────────┘ └──────────┘ └──────────┘  │  ║
    ║  └────────────┬─────────────────────────────┘  ║
    ║               ↓                                ║
    ║  ┌──────────────────────────┐                  ║
    ║  │ 4. GAP CHECK             │                  ║
    ║  └────────────┬─────────────┘                  ║
    ║               ↓                                ║
    ║  ┌──────────────────────────┐                  ║
    ║  │ 4.5 CRITIC REVIEW        │  (exhaustive     ║
    ║  │  (findings quality check)│   mode only)     ║
    ║  └────────────┬─────────────┘                  ║
    ║               ↓                                ║
    ║  ┌──────────────────────────┐                  ║
    ║  │ 5. DIRECTOR REVIEW       │                  ║
    ║  │  (simplified decision)   │                  ║
    ║  └──────┬───────────┬───────┘                  ║
    ║         │           │                          ║
    ║    CONTINUE    SYNTHESIZE                       ║
    ║         │           │                          ║
    ║         │           ↓                          ║
    ║         │   ┌──────────────────────┐           ║
    ║         │   │ 5.5 FALSIFICATION    │           ║
    ║         │   │ (try to break key    │           ║
    ║         │   │  claims, all modes)  │           ║
    ║         │   └──────────┬───────────┘           ║
    ║  ┌──────┘              │                       ║
    ║  │ 6. SYNTHESIST       ↓                       ║
    ║  │  (evolving mode)    │                       ║
    ║  │  Update draft       │                       ║
    ║  └───────┬─────────────┘                       ║
    ║          ↓                                     ║
    ║       (loop)                                   ║
    ╚══════════╧═════════════════════════════════════╝
              ↓
  ┌──────────────────────────┐
  │ 6. SYNTHESIST (polish)   │
  │  Final structured report │
  │  (or fallback if failed) │
  └────────────┬─────────────┘
               ↓
  ┌──────────────────────────┐
  │ 7. VERIFIER              │
  │  Fact-check + retry      │  PASS → done / FAIL → retry (max 3)
  │  + fallback passthrough  │
  └────────────┬─────────────┘
               ↓
          FINAL REPORT
```

## Model

**All roles in a run use one model** — the agent's default (`delegation.model` in your agent config). No profile or per-role model selection.

## Config

No config file required. The pipeline runs entirely on `delegation.model` from the agent config.

## Deterministic Runtime (scripts/)

LLMs make semantic decisions; the runtime scripts enforce invariants. Available in `scripts/` (stdlib-only Python 3.10+):

- `source_registry.py` — immutable source registry: every URL used in the report must be registered here first. After `freeze`, no mutations allowed. This makes URL fabrication impossible.
- `claim_ledger.py` — immutable claim ledger: each report-worthy statement is recorded with its evidence source IDs, verification status, and confidence.
- `check_sources.py` — deterministic HTTP accessibility check: 2xx/3xx `ok`, 401/403 `restricted` (not dead!), 404/410 `dead`, 429 `rate_limited`, 5xx `transient_error`, network `network_error`.
- `verify_report.py` — structural validation: every factual block must cite `[S#]` from the registry; rejects unknown source IDs and uncited factual blocks.
- `finalize_report.py` — writes `status: validated` only after semantic + structural checks pass. A draft cannot self-certify.
- `annotate_report.py` — auto-inserts claim markers (`<!-- claims: C# -->`) on blocks whose cited `[S#]`s match a claim's evidence. Dry-run by default; `--apply` writes. Safety: parse functions operate on the report body WITHOUT frontmatter — never apply their offsets to the full file (indices shift by frontmatter length); strip frontmatter, edit body, rebuild file.
- `fact_check_claims.py` — Phase 7.5: generates per-claim judge tasks + collects verdicts (supported/refuted/not_found) + verbatim numeric check (`numeric_check` in verdict, `numeric_precision` aggregate).
- `eval_citations.py` — citation-quality triad scoring: link works / relevant / fact check (+ numeric precision).
- `dedup_claims.py` — deterministic claim dedup BEFORE Gap Check: identical normalized text, same numbers + overlapping source sets, heavy source-set overlap on high-importance claims. Mechanical ~80%; paraphrases left to LLM Gap Check.
- `check_coverage.py` — coverage assertions: key claims need ≥2 evidence sources from DIFFERENT domains (mirror detection); high-importance claim without a primary source must not claim high confidence; success-criteria checklist from brief. `status: coverage_gap` blocks `validated`.
- `escalations.py` — structured human escalation: machine-readable `escalations.json` (claim_id, verdict, conflicting sources, recommended action). Rule: a claim that is `refuted` OR has `numeric_mismatch` surviving to the final report ⇒ `status: needs_review`, `validated` forbidden (enforced by finalize_report).
- `run_benchmark.py` — benchmark runner: `prepare` brief from `evals/questions.json`, `score` run vs baseline (+ DRACO `rubric_*` metrics + numeric precision), `baseline` table. See README "Benchmarking" for commands. Benchmark runs are deterministic-only by default (the LLM fact-check judges from Phase 7.5 are not executed) — expect `rubric_factual_accuracy: 0.0` and finalize `status: unverified_gaps` in the score; that asserts the deterministic chain, not a failure. Confirmed on the 2026-08-12 LangGraph-vs-CrewAI run: structural passed, citation_coverage 1.0, source_access 0.88, rubric_total 0.43, status unverified_gaps.
- `research_state.py` — global budgets, adaptive stopping, and per-subtopic saturation (`subtopic_saturated`, `mark_saturated`). Usage: `init <path> --mode <surface|moderate|exhaustive>` to seed budgets, `consume <path> <role> --amount N` to track per-role spend (e.g. `consume investigator --amount 3` after an investigator batch), `mark_saturated <path> <subtopic>`.

Run directory layout:

```bash
RUN=".hybrid-research/{slug}"
mkdir -p "$RUN/raw_findings"
python3 scripts/source_registry.py init "$RUN/source_registry.json"
python3 scripts/claim_ledger.py init "$RUN/claims.jsonl"
```

If Python is unavailable, fall back to prompt-level enforcement (manual URL check in Phase 7) and mark the report `unverified_gaps`.

## Procedure

### Phase 0: Model Check

Read `delegation.model` from agent config. Use it for all roles. Do NOT display the model to the user — it's internal.

### Phase 1: Prompt Master (brief generation + category detection)

**Date grounding:** Before generating the brief, determine the current date. Add a date preamble to all downstream prompts: "Today's date is {Month DD, YYYY}. When a search query needs a year or refers to 'latest'/'current'/'this year', use {YYYY} — never a year inferred from training data."

Read user input. First, classify the question into one category:

- **product**: "best X", "top X", "which X to buy", product/service recommendations
- **comparison**: "X vs Y", "comparing X and Y", "difference between X and Y"
- **howto**: "how to X", "guide for X", "setting up X", "configuring X"
- **factcheck**: "is it true that X", "does X really work", "verifying claim about X"
- **general**: anything else (default)

Set OUTPUT FORMAT based on category:
- **product** → ranked list with pros/cons + quick-compare table + verdict
- **comparison** → comparison table + per-option sections + best-for verdicts
- **howto** → quick guide + prerequisites + detailed steps + common mistakes
- **factcheck** → claim → evidence for/against → verdict → nuance & caveats
- **general** → executive summary → findings → sources (default report format)

Generate structured research brief:

```
RESEARCH BRIEF
═══════════════
Topic: {topic}
Date context: {current date — used to ground all queries in the correct time period}
Category: {detected category}
Output format: {derived from category, or user-specified}
Scope: {specific aspects to investigate}
Time-box: {last 30 days / last year / all time / specific date range}
Depth: {surface / moderate / exhaustive}
Sources: {web, reddit, x, hn, youtube, github — select relevant}
Success criteria: {what a complete answer looks like}
Constraints: {language, regions, excluded sources, specific requirements}
```

**Depth modes map to pipeline parameters:**
- **surface**: 1 round, 3 subtopics max, no verification, no critic. ~2 min. For quick overviews.
- **moderate**: 2 rounds, 3-5 subtopics, verification (1 retry max), no critic. ~10 min. Default for most questions.
- **exhaustive**: 4 rounds, 5 subtopics, verification (3 retries), critic agent. ~30 min. For complex multi-faceted questions.

**Depth selection:** Default is `moderate`. Never auto-detect depth from question complexity. Overrides:
- "quick research" / "quick scan" / "overview" → **surface**
- "deep dive" / "in-depth" / "thorough" → **exhaustive**
- Explicit request ("use surface mode") → that mode
- Otherwise → stay with the default

**If user mentions "what people say" / "reaction" / "opinion"** → emphasize social sources (Reddit, X, HN).
**If user mentions "official" / "announcement" / "release"** → emphasize web + GitHub.
**If user mentions "trend" / "happening" / "recent"** → set time-box to 30 days + social sources.

### Phase 1b: Brief Approval (Human-in-the-Loop — OFF by default)

**Skip this phase unless the user explicitly says "let me see the plan first".**
Proceed silently from question to report. If the user does ask, present the brief and let them adjust scope/sources/category, then proceed to Director.

### Phase 2: Director (decomposition)

Read the brief. Decompose into subtopics × source matrix:

```json
{
  "subtopics": [
    {
      "name": "subtopic 1",
      "queries": {
        "web": [
          {"query": "query 1", "research_goal": "why this query, what we expect to find"},
          {"query": "query 2", "research_goal": "why this query, what we expect to find"}
        ],
        "reddit": [
          {"query": "query 1", "research_goal": "why this query, what we expect to find"},
          {"query": "query 2", "research_goal": "why this query, what we expect to find"}
        ],
        "x": [
          {"query": "query 1", "research_goal": "why this query, what we expect to find"}
        ],
        "hn": [
          {"query": "query 1", "research_goal": "why this query, what we expect to find"}
        ],
        "github": [
          {"query": "query 1", "research_goal": "why this query, what we expect to find"}
        ],
        "youtube": [
          {"query": "query 1", "research_goal": "why this query, what we expect to find"}
        ]
      }
    }
  ],
  "source_priority": ["web", "reddit", "github"],
  "breadth": 4,
  "depth": 3,
  "max_rounds": "{based on depth: surface=1, moderate=2, exhaustive=4}",
  "stopping_criteria": "all key aspects covered with 2+ sources each"
}
```

**Rules:**
- 3-5 subtopics max
- Each subtopic gets 2-4 source-specific queries
- Not all sources needed for all subtopics (Director decides relevance)
- Max 4 rounds total (hard limit — prevents runaway loops)

**Adaptive query strategy:**
- Round 1: 4 broad exploratory queries per subtopic (cast wide net)
- Round 2+: `ceil(breadth/2)` targeted gap-filling queries per subtopic (breadth halving)
- Director adjusts query instructions per round, not just content

**Date grounding:** Director includes the current date in query generation prompts so investigators generate queries with the correct year.

**Breadth/depth parameters:**
- `breadth`: queries per subtopic per round (default: 4 for round 1)
- `depth`: max deep-dive rounds per subtopic (default: based on depth mode — surface=1, moderate=2, exhaustive=4)
- **Breadth halving:** Each subsequent round, breadth = `ceil(breadth / 2)`. Round 1: 4 queries. Round 2: 2. Round 3: 1. This prevents combinatorial explosion while maintaining diversity.
- Director can set per-subtopic depth: "subtopic 1 → depth=3 (important), subtopic 2 → depth=1 (surface scan)"

**Research goal as context carrier:** Each query carries a `research_goal` — why it's being asked and what to do with results. Investigators receive this context. In Round 2+, follow-up queries are built from previous round's `research_goal + follow_up_questions`.

### Phase 3: Investigators (parallel execution)

Dispatch parallel subagents via `delegate_task`. Each investigator gets ONLY their subtopic + source type.

Detailed role prompts in `references/roles.md`.

**Execution rules:**
- **Max 3 investigators per batch.** If Director created 5 subtopics, they run in batches: first 3, then 2. Each subtopic = 1 investigator agent.
- Each investigator returns structured finding records (see references/roles.md for format). Each record has: rational, evidence, summary, URL, date, source type, credibility, confidence level.
- Investigators receive `research_goal` per query. Findings should reference the goal: 'This finding addresses the goal of {research_goal}'.
- **Compression before return:** Investigators must compress findings before returning. Each finding record should contain ONLY:
  - Rational: 1 sentence
  - Evidence: key quotes/numbers only (max 200 words per finding)
  - Summary: 1-2 sentences
  - URL, date, source type, credibility, confidence
  - Follow-up questions (if applicable)
  Drop everything else. No raw page content. No navigation text. No boilerplate. If a finding's evidence exceeds 200 words, compress to key data points only. This prevents context overflow in Synthesist.
- Web queries: use `web_search` tool
- Social queries: Reddit requires authenticated curl with cookies.txt (Reddit blocks unauthenticated JSON/RSS with 403 Cloudflare). Use `curl --cookie cookies.txt` for Reddit JSON API (cookies.txt exported from Chrome — see your agent framework's cookie export method). If cookies are unavailable, mark Reddit as `[LACK_OF_DATA]` — do NOT fall back to `site:` search (returns irrelevant results for niche topics, lets the LLM fake coverage). See `references/roles.md` for details.
- GitHub queries: use GitHub API via `curl`
- All investigators must cite URLs and dates
- **Register sources after each round:** The orchestrator (parent agent) registers every unique URL from investigator findings into the source registry. Never skip this — the registry is the single source of truth for the report's citations:
  ```bash
  python3 scripts/source_registry.py add "$RUN/source_registry.json" \
    --title "..." --url "..." --source-type "web|reddit|hn|github|youtube" \
    --date "YYYY-MM-DD|unknown" --finding-file "raw_findings/{subtopic}.md"
  ```
  The command assigns a stable `S#` and deduplicates canonical URLs.
- **Register claims:** Convert report-worthy statements into the claim ledger with evidence links:
  ```bash
  python3 scripts/claim_ledger.py add "$RUN/claims.jsonl" \
    --claim "..." --importance high --confidence medium \
    --verification supported \
    --evidence-json '{"source_id":"S1","support":"direct","excerpt":"..."}'
  ```
  A factual claim with no evidence source stays `unverified`; do not write it as established fact later.
- **Rate limit handling:** If any HTTP request returns 429 or 5xx, immediately mark that query as `[SOURCE_ERROR: RATE_LIMIT]` or `[SOURCE_ERROR: SERVER_DOWN]` and move on. Do NOT retry. Do NOT treat a failed request as "no data found."
- **Fallback for blocked APIs:** If GitHub API returns 401/403/429, fall back to `web_search(query="{query} site:github.com")`. Mark the source as `[FALLBACK: web_search]` in findings. Reddit has NO fallback: if the authenticated path fails, mark `[LACK_OF_DATA]` — never fake coverage with `site:reddit.com` search.
- **Agent failure recovery:** If a subagent crashes, times out, or returns no usable output:
  1. Retry once with the same goal
  2. If retry fails → mark subtopic as `[AGENT_FAILED: {subtopic}]` in Gap Check
  3. Director decides: re-assign to a different investigator in the next round, or exclude with `[LACK_OF_DATA: {subtopic}]`
  4. Do NOT silently skip — always log the failure

### Phase 4: Gap Check

Read all investigator findings. Identify gaps:

```
GAPS ANALYSIS
═════════════
Covered subtopics: [list]
Missing subtopics: [list]
Subtopics with weak coverage (<2 sources): [list]
Missing source types for covered subtopics: [list]
Stale data (older than time-box): [list] — REJECT these findings, do not pass to Synthesist
Contradictions between sources: [list]
Rate-limited sources: [list] — do NOT re-query in the same round
Zero-result subtopics: [list] — if 2+ consecutive searches returned nothing, EXCLUDE from further rounds
Agent failures: [list] — subtopics where investigator crashed
Semantic duplicates: [list] — findings that say the same thing from different URLs
```

**Semantic dedup rule (all modes):** The registry dedupes URLs, not content. Two findings from different URLs can carry the same claim (same numbers, same conclusion, often syndicated news or mirror posts). In Gap Check, identify content-level duplicates and mark all but the strongest as `[DUP: S#]`:
- Keep the finding with the highest authority weight (official_docs > news > blog > social)
- If equal weight, keep the most recent
- Mark the rest `[DUP: kept S#]` — they stay in the registry (they are real sources) but do NOT pass to Synthesist as independent evidence
- Deduped findings must NOT count toward the "2+ sources" coverage criterion — two mirrors of the same article are one source
Reason: duplicates inflate source counts, double-weight a claim in synthesis, and can mask a genuinely thin coverage as "2+ sources".

**Deterministic dedup first (all modes, v4.8.0):** BEFORE the LLM gap analysis, run the mechanical pass — it catches ~80% of content duplicates (identical normalized text, same numbers + overlapping source sets, heavy source-set overlap on high-importance claims) with zero LLM cost:
```bash
python3 scripts/dedup_claims.py "$RUN/claims.jsonl" \
  --registry "$RUN/source_registry.json" \
  --out "$RUN/dedup.json"
```
Feed `dedup.json`'s `kept_ids`/`duplicates` into the Gap Check: dropped claims are marked `[DUP: kept C#]`, they stay in the ledger (real evidence) but do NOT pass to Synthesist as independent. Only paraphrases that share no numbers are left to the LLM dedup step above.

*Decision is made by Director Review (Phase 5). This phase only collects and structures gap data.*

### Phase 4.5: Critic Review (exhaustive mode only)

Skip this phase in surface or moderate mode.

Critic reviews all investigator findings BEFORE synthesis. This is a deterministic + LLM hybrid check:

```
CRITIC REVIEW
═════════════
For each finding:
- URL present? → If missing: [CRITIC_FAIL: no URL]
- URL accessible? → curl check (same as Phase 7 URL check). If 404: [CRITIC_FAIL: dead URL]
- Date in timeframe? → If stale: [CRITIC_FAIL: stale data, reject]
- Credibility tag justified? → If "official_docs" but URL is a blog: [CRITIC_WARN: mislabeled credibility]
- Rational contradicts evidence? → If yes: [CRITIC_FAIL: internal contradiction]
- Confidence tag reasonable? → If "high" but single source opinion: [CRITIC_WARN: inflated confidence]
- Citation supports claim? → Read the cited page/snippet. If the URL is reachable but its content does NOT actually support the claim it backs: [CRITIC_FAIL: citation-content mismatch] — the claim is dropped or re-anchored to a source that really supports it. This is different from a dead URL: the page exists, the link just doesn't prove the sentence. (exhaustive mode only)
```

**Actions:**
- CRITIC_FAIL → finding is REMOVED from findings pool. Log removal.
- CRITIC_WARN → finding stays, but Synthesist is notified to treat with caution
- All others → finding passes to synthesis

**Critic does NOT generate new queries or content.** It only filters and flags.

### Phase 5: Director Review

Director curates all findings + gap analysis:

```
DIRECTOR DECISION
═════════════════
Round: {N} of {max_rounds}
Decision: {CONTINUE / SYNTHESIZE}
Reason: {one sentence}
Refined queries: [only if CONTINUE]
```

**CONTINUE triggers:**
- Critical gaps remain
- Conflicting claims need more evidence
- Social signals suggest important developments not yet in web findings
- <2 sources for key aspects

**SYNTHESIZE triggers (priority order — first match wins):**
1. **Max rounds reached** — surface=1, moderate=2, exhaustive=4 rounds completed → SYNTHESIZE unconditionally
2. **No new data for 2 consecutive rounds** → SYNTHESIZE (further rounds won't help)
3. **All key aspects covered with 2+ sources** → SYNTHESIZE if ≥2 rounds completed
4. **Persistent rate limits** blocking critical subtopics → SYNTHESIZE, note in Uncertainties
5. **Adaptive stop (when `research_state.py` is available)** → SYNTHESIZE early if the last N findings converge: ≥3 consecutive findings for the same key aspect agree on substance (same conclusion, overlapping sources), even if rounds remain. The runtime script tracks convergence; Director reads its state. This is the formalized version of trigger 2 — instead of waiting for "no new data," stop as soon as evidence is consistent.
6. **Per-subtopic saturation (v4.8.0, when `research_state.py` is available)** → a subtopic is saturated when it has ≥3 high-credibility sources on ALL its key aspects. Saturated subtopics are SKIPPED in the next round (they don't force CONTINUE and don't get re-queried), while other subtopics continue. The runtime script exposes `subtopic_saturated(state, subtopic, high_cred_sources, aspects_covered, aspects_total)` and `mark_saturated(state, subtopic)`. Complements global adaptive stop (trigger 5) — one exhausted subtopic should not force the whole run to stop, and one saturated subtopic should not force it to continue.

**CONTINUE triggers (only if no SYNTHESIZE trigger matched):**
- Critical subtopic has <2 sources
- Key contradiction unresolved
- Social signals suggest major development not in web findings
- Round 1-2 with clear gaps remaining (minimum exploration not done)
- Findings diverge: 2+ findings for a key aspect disagree on substance → keep researching (adaptive stop must NOT fire on disagreement)

**Priority rule:** SYNTHESIZE triggers 1-2 override Smart stop. Never loop past max_rounds. Adaptive stop (trigger 5) fires only on convergence, never on divergence — disagreeing evidence is a CONTINUE signal, not a stop signal.

### Phase 5.5: Falsification Round (all modes)

Before final synthesis, run ONE targeted round on the report's key claims. Purpose: try to break the conclusion, not confirm it.

**Procedure:**
1. Take the top 3-5 key claims from the evolving report (highest importance).
2. For each, dispatch ONE focused investigator with the explicit goal: *"Find evidence that contradicts or weakens this claim. If none exists, say so explicitly. Do NOT search for supporting evidence."*
3. Investigator registers any contradicting sources into the source registry (same `source_registry.py add` flow). A counter-source that is not a real URL does not count — the registry enforces this.
4. Director review of falsification results:
   - **No contradicting evidence found** → proceed to synthesis unchanged. Note in the report: "Falsification attempted: no counter-evidence found."
   - **Weak contradiction** (lower authority weight than the supporting sources) → proceed, add the counter-claim to "Contradictions & Uncertainties" with both sides cited.
   - **Strong contradiction** (comparable/higher authority, directly conflicts) → do NOT finalize as-is. Either resolve in a follow-up round (CONTINUE) or present both sides prominently with the conflict called out. Never silently drop a strong counter-claim.

**Cost control:** Falsification round is 1 round max, 3-5 investigators max, runs only on final synthesis (not per-round evolving mode). If it hits rate limits or agent failures, note `[FALSIFICATION_SKIPPED: reason]` in Uncertainties and proceed.

**Why:** This is the cheapest reliable defense against confident-but-wrong reports. Verifying URLs (Phase 7) checks that sources exist; falsification checks that the *conclusion* survives contact with counter-evidence.

### Phase 6: Synthesis

Synthesist operates in two modes:

**Per-round synthesis (evolving mode):** After each round's Director Review, if CONTINUE, Synthesist takes `evolving_report` (from state.json) + this round's new findings → updated draft. Uses only the last `synthesis_window` (default 10) findings to control context — earlier findings are already integrated into the draft. Saves updated draft back to state.json.

**Per-round verification gate (all modes, each round):** Before saving the evolving draft, Synthesist answers three gate questions and appends them to `state.json` under `round_gates`:
1. Which claims introduced THIS round have no supporting evidence in the registry? (→ drop or mark Unverified)
2. Which new findings contradict earlier-round findings? (→ surface both sides, never silently pick one)
3. Which claims became LESS confident this round? (→ downgrade confidence tag)
Rationale: a wrong intermediate conclusion propagates through later rounds (cascading errors). Checking only at the end (Phase 7) catches the final report but not the decisions it was built on. This gate is cheap — three questions, no new research — and prevents the error from compounding.

**Evolving report format.** The evolving draft must use this stable structure so Synthesist in FINAL mode can polish it without restructuring:

\```
# {Topic} — Research Report (Round {N}/{max_rounds})

## Current Findings
{bullet-point synthesis of what's known so far, with inline citations [N]}

## Open Questions
{questions this round's findings didn't answer}

## Next Round Targets
{if Director said CONTINUE — what to investigate next}
\```

Synthesist in EVOLVING mode MUST preserve this structure across rounds. Only add content, don't restructure. The FINAL mode Synthesist will convert this to the final report format in the next section.

**Final synthesis (polish mode):** When Director says SYNTHESIZE, Synthesist takes the `evolving_report` + any remaining findings → produces the final polished report with full structure, citations, category format.

**Synthesist works only from frozen evidence (runtime mode):** When the source registry and claim ledger exist, the Synthesist receives ONLY: the brief, vetted findings, the frozen `source_registry.json`, the frozen `claims.jsonl`, and known gaps/contradictions. Hard rules:
- Never invent or repair a URL. Raw URLs appear only in the Sources section.
- Never create an `S#` absent from the frozen registry.
- Every factual block (prose, list items, numbered steps, blockquote, table data rows) cites `[S#]` that actually supports the referenced claim.
- Leave `status: pending` in draft frontmatter — the finalizer decides the final status.
- The runtime layer (registry, ledger, verify, finalize) is REQUIRED — the pipeline never runs on prompt-level fallbacks. If the registry/ledger are absent, the run is incomplete: stop and re-run the deterministic layer, do not substitute hand-rolled citation checks.

**Abstention rule (all modes):** If a claim in the brief has NO supporting evidence in the findings/registry — do NOT write it as fact. Write it explicitly as unverified: "Не подтверждено: {claim}" or "Unverified: {claim}" in the Contradictions & Uncertainties section. A report that states "no data found" honestly beats a report that invents a citation. Never fill an evidence gap with a plausible-sounding source — that is fabrication, and `verify_report.py` rejects uncited blocks anyway.

**Confidence calibration (all modes):** For each Key Finding paragraph, mark the confidence of the central claim inline: `[confidence: high]`, `[confidence: medium]`, or `[confidence: low]` at the end of the paragraph (inside the claim marker or as plain text). Rules:
- `high` — 2+ independent sources agree, or 1 official/primary source
- `medium` — 1-2 sources, some conflicting, or single-source claims from credible outlets
- `low` — single source, speculation, or contradictory evidence; MUST also appear in Contradictions & Uncertainties
- In the Executive Summary, confidence comes from the strongest claim: if any key finding is `low`, say so ("часть выводов основана на единственном источнике").

**Low-confidence escalation (human-in-the-loop, all modes):** If the FINAL report contains any `[confidence: low]` finding, add a "## Требует ручной проверки" / "## Requires Manual Verification" block right after the Executive Summary listing exactly which claims are low-confidence and why. The reader must not mistake a single-source or contradicted claim for established fact. This is the cheap HITL fallback: no extra research, just a visible gate. If a claim is both `low` AND `refuted` by the fact-check layer (Phase 7.5), it must appear here with both flags.

**Short report expansion:** If the final polished report is under 400 words, Synthesist must expand it with a follow-up pass:
- Send the short report back to Synthesist with: "This report is too brief ({word_count} words). Expand it significantly: add detailed paragraphs for each section (not just bullet points), include specific data and comparisons from the evidence, explain context and significance, use ## headings and ### subheadings. Target at least 800 words."
- If the expanded version is longer than the original, use it.
- This check runs only on the FINAL report, not on per-round evolving drafts.

**Adapt the report structure to the Output format from the brief (or detected category):**

| Output format | Structure |
|--------------|-----------|
| **product** | Ranked list with pros/cons per option, quick-compare table, verdict |
| **comparison** | Side-by-side tables, pros/cons lists, best-for verdicts |
| **howto** | Quick guide summary, prerequisites, numbered steps, common mistakes |
| **factcheck** | Claim → evidence for/against → verdict → nuance & caveats |
| **analysis** | Narrative sections with evidence, argument → counter-argument |
| **report** | Executive summary → findings → sources (default) |
| **summary** | Brief overview, 5-10 sentences, no deep structure |

**Source authority weighting:** When sources conflict, higher authority wins. Weight matrix:
- `official_docs`: 1.0 (primary sources, official documentation, press releases)
- `news`: 0.7 (established news outlets)
- `analysis`: 0.6 (expert analysis, research papers)
- `repo`: 0.6 (official repository, code)
- `blog`: 0.4 (personal blogs, commentary)
- `social_post`: 0.3 (Reddit, HN, X posts)
- `other`: 0.3

When the Synthesist encounters conflicting claims:
1. Compare source weights
2. Higher weight claim is presented as primary: "According to {source} [N], ..."
3. Lower weight claim is presented as contradicting: "...however, {lower_source} [M] claims ..."
4. If weights are equal, present both and note the contradiction in "Contradictions & Uncertainties"

**Recency tiebreak in conflicts (all modes):** Authority weight is not the whole story — a stale official page can contradict a fresh news report. When sources conflict:
- If the higher-weight source is OLDER than the lower-weight one by a meaningful margin (outside the time-box, or >6 months for fast-moving topics like pricing/limits/availability), present the newer claim as the current state and note the older one as "по состоянию на {год}" / "as of {year}".
- Never silently drop the newer claim because it has lower authority — date the old claim, keep both.
- Example: "Perplexity's pricing page [S18] says $20/month (as of 2024), but the 2026 Reddit thread [S9] reports the quota was cut — the older page reflects the pre-cut state."

Default template (report format):

```
# {Topic} — Research Report

## Executive Summary
{2-3 sentences: key findings + conclusion}

## Key Findings
{Organized by subtopic, with inline citations}

## Social Pulse
{What people are actually saying — Reddit, X, HN highlights}
{Engagement-weighted: most discussed > most upvoted > most recent}

## Technical Details
{GitHub repos, releases, code trends if applicable}

## Contradictions & Uncertainties
{Where sources disagree, what's unconfirmed}

## Sources
[1] Title — URL (date, source type, credibility tag)
[2] ...
```

**Citation rules:**
- Every claim must have ≥1 citation in format `[N]`
- All sources (web + social) share one numbered list `[1]`, `[2]`, `[3]`...
- Source type is noted in the Sources section: `[1] Title — URL (date, Reddit, 2.3k upvotes)`
- Engagement metrics included when available for social sources
- Date of source always included
- **Use `<details><summary>` blocks** for verbose sections (raw data, full quote lists, secondary findings) to keep the report scannable. Main narrative stays flat; supporting evidence goes in collapsible blocks.

**Fallback report:** If Synthesist fails (crash, timeout, empty output) and there are findings, compile a fallback report: list all findings with their URLs, dates, and summaries. Mark report with `status: unverified_gaps` in frontmatter. Do NOT return "No information could be gathered" if findings exist.

### Phase 7: Verification

Verifier checks the report against findings:

**Deterministic checks (runtime scripts) — preferred when Python is available:**

1. **Freeze provenance** (after final synthesis, before verification):
   ```bash
   python3 scripts/source_registry.py freeze "$RUN/source_registry.json"
   python3 scripts/claim_ledger.py freeze "$RUN/claims.jsonl"
   ```
   After freeze, mutations must fail. Do not edit these files manually.

2. **Structural validation** — every factual block (prose, list items, numbered steps, blockquote, table data rows) must cite `[S#]` present in the frozen registry:
   ```bash
   python3 scripts/verify_report.py "$RUN/report.md" \
     --registry "$RUN/source_registry.json" \
     --claims "$RUN/claims.jsonl"
   ```

3. **HTTP accessibility check** — deterministic classification of every registered URL:
   ```bash
   python3 scripts/check_sources.py "$RUN/source_registry.json" \
     --output "$RUN/source_access.json"
   ```
   Classification: 2xx/3xx `ok`, 401/403 `restricted` (NOT dead — Cloudflare 403 means the page exists), 404/410 `dead`, 429 `rate_limited`, 5xx `transient_error`, network errors `network_error`.

4. **Deterministic finalization** — writes `status: validated` only when all checks pass; a draft cannot self-certify:
   ```bash
   python3 scripts/finalize_report.py "$RUN/report.md" \
     --manifest "$RUN/report_manifest.json" \
     --registry "$RUN/source_registry.json" \
     --claims "$RUN/claims.jsonl" \
     --access "$RUN/source_access.json" \
         --semantic-verification passed \
         --escalations "$RUN/escalations.json" \
         --coverage "$RUN/coverage.json"
        ```
        `--escalations` enforces the v4.8.0 rule: a `needs_review` escalations file (refuted claim survived) forces `status: needs_review` — `validated` is impossible. `--coverage` (v4.8.0, required after Phase 7.7) enforces the same for `coverage_gap` — without the flag finalize never sees the coverage status and would wrongly report `validated`/`unverified_gaps`. Both flags were mandatory in the 2026-08-12 benchmark run.

**Explicit failure signals (do not silence them):**
- `source_registry.py add` on a missing `--finding-file` prints a WARNING and stores empty (no silent crash). If `RuntimeError: source registry is frozen` appears — you froze before registering; re-init the registry.
- `claim_ledger.py add` requires `--claim-class`; if finalize says `claim ledger must be frozen` — you added claims after freezing; re-init, add, freeze.
- `verify_report.py` FAIL lines list exactly which blocks lack citations/claim markers. Fix them (or run `annotate_report.py --apply`), don't re-freeze over them.
- `annotate_report.py` is the claim-marker helper: `python3 scripts/annotate_report.py "$RUN/report.md" --claims "$RUN/claims.jsonl" --apply` auto-inserts `<!-- claims: C# -->` markers on any block whose cited `[S#]` sources match a claim's evidence. Dry-run by default; pass `--apply` to write.

**Verification is the deterministic layer, not prompt-level URL checks:** `check_sources.py` (live HTTP), `verify_report.py` (citations attached to claims), `finalize_report.py` (gate). Prompt-level fallbacks are not a mode — a run without the deterministic layer is incomplete and never marked `validated`.

```
VERIFICATION
═════════════
Factual accuracy: {PASS / FAIL}
  - {specific claims checked}
Citation validity: {PASS / FAIL}
  - {URLs accessible, dates match}
Source diversity: {PASS / FAIL}
  - {subtopics covered, source types present}
Recency: {PASS / FAIL}
  - {data within time-box}
```

**PASS → finalize report, save to file.**
**FAIL → return to Synthesist with specific corrections (max 3 retries).**

**Fallback report handling:** If the report is a fallback (status is `unverified_gaps` in frontmatter or marked FALLBACK_REPORT), skip normal verification — the report is raw findings. Note in the report that synthesis failed and findings are unprocessed.

### Phase 7.5: Semantic Fact-Check (arXiv "Cited but Not Verified")

`verify_report.py` proves citations EXIST and are attached to claims. It cannot prove the cited source SUPPORTS the claim — frontier models keep links alive in 94%+ of cases while factual accuracy sits at 39-77%. This layer closes that gap. **Mandatory when the run has >30 registered sources** (information overload degrades factual accuracy — arXiv ablation shows ~42% drop from 2→150 tool calls); optional otherwise.

1. **Generate per-claim fact-check tasks:**
   ```bash
   python3 scripts/fact_check_claims.py prepare \
     --claims "$RUN/claims.jsonl" \
     --registry "$RUN/source_registry.json" \
     --out "$RUN/fact_check/"
   ```
   Creates `fact_check/tasks/C{id}.json` per claim (claim text + evidence URLs) and `fact_check/manifest.json`.

2. **Judge each claim (LLM-as-a-judge):** For each task, fetch the evidence URL content (web_extract or curl), then write a verdict file `fact_check/verdicts/C{id}.json`:
   ```json
   {
     "claim_id": "C1",
     "verdict": "supported | refuted | not_found",
     "rationale": "1-3 sentences; for refuted, quote what the source actually says",
     "evidence_source_id": "S9",
     "checked_at": "ISO-8601"
   }
   ```
   Verdict rules: `supported` = page directly states/implies the claim; `refuted` = page contradicts it; `not_found` = page exists but doesn't address it (or unreadable). A generic page about the topic is NOT `supported`.

3. **Collect and gate:**
   ```bash
   python3 scripts/fact_check_claims.py collect \
     --claims "$RUN/claims.jsonl" \
     --verdicts "$RUN/fact_check/verdicts/" \
     --out "$RUN/claim_verification.json"
   ```
   Exit 0 only when every claim is `supported`. On `refuted`/`not_found`/missing verdicts → the claim moves to Contradictions & Uncertainties (refuted: both sides cited; not_found: claim downgraded to `medium`/`low` or marked Unverified). Do NOT silently keep a refuted claim in the Key Findings as established fact.

**Fact-check fatigue guard:** If >8 claims need judging, run judges in parallel batches (3-5 per batch, same as investigators). Judge output is a verdict file, not a new finding — no registry mutation.

### Phase 7.6: Repair Round (verification as test-time scaling, v4.8.0)

`fact_check_claims.py collect` gates on refuted/not_found verdicts — but simply moving a claim to Uncertainties wastes the information the judge just produced. Repair gives each failed claim ONE targeted pass before finalize (arXiv 2603.28376: errors in intermediate steps propagate downstream; verification beats more retrieval).

**Trigger:** any `refuted` / `not_found` / `numeric mismatch` claim in `claim_verification.json`.

**Budget:** ≤5 claims, ≤3 queries per claim, 1 round only. If more than 5 claims failed, repair the highest-importance ones (critical > high) and escalate the rest.

**Procedure (per failed claim, orchestrator does this — no new investigators):**
1. Read the judge's rationale (it says what the source actually says / what's missing).
2. **re-anchor:** the claim may be correct but anchored to the wrong source (common for `not_found`). Search ≤3 queries for a source that actually supports it, register it (`source_registry.py add` — requires re-init if registry was frozen; add it BEFORE freeze in the normal flow), update the claim's evidence.
3. **drop:** if no supporting source exists after ≤3 queries, the claim is dropped from Key Findings and moved to "Contradictions & Uncertainties" as unverified — never silently kept.
4. **keep-with-caveat:** if a contradicting source is equal-authority, keep both sides with the conflict called out (same as falsification weak-contradiction path).

**After repair:** re-run `fact_check_claims.py prepare` for the repaired claims only, judge them again, re-collect. A repaired claim that still fails → escalation (below).

**Escalation (structured, v4.8.0):** instead of a prose-only block, write the machine-readable `escalations.json`:
```bash
python3 scripts/escalations.py "$RUN/claims.jsonl" \
  --registry "$RUN/source_registry.json" \
  --fact-check "$RUN/claim_verification.json" \
  --out "$RUN/escalations.json"
```
Contains per claim: `claim_id`, `verdict`, `reasons` (refuted/not_found/numeric_mismatch/low_confidence), `conflicting_sources`, `recommended_action` (re-anchor/drop/keep-with-caveat). **Deterministic rule (session-tested 2026-08-12):** if a `refuted` claim — OR a `numeric_mismatch` (the source carries a DIFFERENT number than the claim — a hallucinated figure, same refuted class) — survives to the final report (repair didn't help), the run MUST be `status: needs_review` — `validated` is forbidden. `finalize_report.py --escalations` enforces this. Preserves silent mode: no mid-run interrupts; the human reviews the finished report plus `escalations.json`.

### Phase 7.7: Coverage Assertions (v4.8.0)

Before finalize, verify the report's claims meet coverage invariants (this is what `status: coverage_gap` means):
```bash
python3 scripts/check_coverage.py "$RUN/claims.jsonl" \
  --registry "$RUN/source_registry.json" \
  --brief "$RUN/brief.json" \
  --out "$RUN/coverage.json"
```
- **Domain independence:** every key claim (importance high/critical) with ≥2 evidence sources needs those sources from ≥2 DIFFERENT domains — two mirrors of one site are one source (mirrors inflate "2+ sources").
- **Primary-source preference:** a high-importance claim backed only by blog/social (no official_docs/paper/repo/filing) must NOT claim high confidence.
- **Success-criteria checklist:** if `brief.json` has `success_criteria`, each must map to claims/sources.
Any gap ⇒ `status: coverage_gap` — the report must not be finalized as `validated` until fixed (add missing sources, split mirrors, or drop the claim). Pass the result to finalize: `finalize_report.py ... --coverage "$RUN/coverage.json"` — without the flag finalize never sees the gap.

**Fixing `primary_source_preference` (session-tested 2026-08-12):** the fix is to widen the claim's evidence with a primary source (official_docs/paper/repo `--source-id`), NOT to downgrade its confidence tag. Re-init the ledger → re-add ALL claims with the added `--source-id` → re-freeze (the ledger has no update command). In the LangGraph-vs-CrewAI run the architecture claim backed only by two blogs (S13/S16) failed; adding official fault-tolerance docs (S11) to its evidence made coverage pass with `[confidence: high]` intact.

## State Management

Track research state for crash recovery. Save to `.hybrid-research/{slug}/state.json` in the current working directory after each phase:

```json
{
  "slug": "topic-YYYYMMDD-xxxx",
  "phase": "brief|decompose|search|gap_check|director_review|synthesize|verify",
  "round": 1,
  "max_rounds": 4,
  "completed_subtopics": [],
  "findings_files": ["raw_findings/subtopic-1.md", "raw_findings/subtopic-2.md"],
  "agent_failures": [],
  "evolving_report": "",  // draft report updated each round
  "synthesis_window": 10, // only last N findings passed to evolving mode
  "synthesis_attempts": 0,
  "round_gates": [],       // per-round verification gate answers (Phase 6)
  "started_at": "ISO-8601",
  "director_decisions": []
}
```

**State is optional** for simple runs (1 round, 3 subtopics — only the report needs saving). **Mandatory** for multi-round scenarios or crash-recovery.

**Memory across runs (optional, reuse):** Before starting a new run on a topic you have researched before, check `~/.hybrid-research/*/` for a prior run with the same/similar slug (grep the topic line in old `state.json` or report frontmatter). If found:
1. Load the old `source_registry.json` — reuse still-valid sources instead of re-fetching (skip re-search for already-covered subtopics).
2. Pass the old report's "Contradictions & Uncertainties" into the new brief as known gaps: "resolve or re-verify: {list}".
3. Save the new run's registry to the same `~/.hybrid-research/` area so the next run can reuse it too.
This is a light-weight version of agent memory: no vector store, just file-level reuse. It prevents re-researching settled facts and carries open questions forward.

**Recovery procedure:** If resuming after a crash:
1. Read `state.json` — check `phase` and `round`
2. Load all `findings_files` from `raw_findings/`
3. Resume from the last completed phase
4. Skip already-completed subtopics

## Output

Final report saved to `.hybrid-research/{slug}/{slug}.md` with YAML frontmatter:

```yaml
---
status: confirmed | unverified_gaps
topic: {topic}
slug: {slug}
rounds: {N}
sources_count: {N}
social_signals: {N}
verification: passed | failed | unverified_gaps
generated_at: ISO-8601
---
```

Raw findings saved to `.hybrid-research/{slug}/raw_findings/{subtopic}.md`.

## Pitfalls

- **Don't skip Prompt Master.** Director gets confused by vague user input. Always brief first.
- **Max 3 investigators per batch.** If Director created 5 subtopics, run in batches of 3, then 2.
- **Handle 429 rate limits explicitly.** Return `[SOURCE_ERROR: RATE_LIMIT]` and stop. Never retry in the same round. Reddit has no fallback — mark `[LACK_OF_DATA]` rather than faking coverage.
- **Don't trust social engagement alone.** Viral ≠ accurate. Cross-validate with web sources.
- **Hard limit: 4 rounds (exhaustive mode).** Surface=1, moderate=2, exhaustive=4. Director respects depth mode. If not enough after max rounds, report what you have with gaps noted.
- **Verification is mandatory.** 3 retries max. After 3 FAILs → publish with `status: unverified_gaps`.
- **Prune before Synthesis.** Investigators must return structured records (rational, evidence, summary) — not raw prose. Low-quality findings (boilerplate, cookie banners, copyright notices) must be discarded at extraction time.
- **All roles share one model** (`delegation.model`). There is no per-role model separation.
- **Agent failures happen.** Subagents can crash, timeout, or return garbage. Always retry once, then log `[AGENT_FAILED]` and let Director decide.
- **Web extract limit.** Investigators MUST NOT call web_extract more than 3 times per round. After 3 extractions — work with search snippets only. Excessive web_extract calls cause subagent timeouts (600s limit). In the test run, one investigator timed out after 13 API calls — the retry with 0 web_extract calls completed in 61 seconds.
- **web_extract is the #1 timeout cause.** Investigators that call web_extract on every search result will timeout at 600s. Limit to 2-3 web_extract calls per investigator. If an investigator times out, retry with a LIGHTWEIGHT variant: "DO NOT use web_extract. Only use web_search and curl. Summarize from search result snippets only." This completes in ~60s vs 600s timeout.
- **Reddit blocks unauthenticated access.** Use cookies.txt with curl for Reddit JSON API. If cookies are unavailable, mark Reddit as `[LACK_OF_DATA]` — do NOT fall back to `site:` search (returns irrelevant results for niche topics and lets the LLM fake coverage).
- **Information overload degrades factual accuracy.** arXiv 2605.06635: Fact Check accuracy drops ~42% as tool calls scale 2→150 — more retrieval makes synthesis WORSE while link/relevance metrics stay stable. Breadth halving + adaptive stop already limit this; when a run exceeds 30 sources, Phase 7.5 semantic fact-check is MANDATORY, not optional. Never equate "more sources" with "more accurate report".
- **Cascading errors beat end-of-turn fixes.** A wrong intermediate conclusion in Round 1 propagates through all later rounds. Run the per-round verification gate (Phase 6) every round — three questions, no new research — and don't rely only on Phase 7 to catch problems.
- **Synthesis subagents fabricate URLs.** When generating the final report, the Synthesist may produce plausible-but-wrong GitHub URLs (wrong org name, wrong repo name). Fix: run with the source registry (`scripts/source_registry.py`) — every URL must be registered before synthesis, and `verify_report.py` rejects any `[S#]` not in the frozen registry. Common fabrications: `github.com/Tongyi-Research/DeepResearch` (correct: `Alibaba-NLP/DeepResearch`), `github.com/pewdiepie/odysseus` (correct: `odysseus-dev/odysseus` — repo was RENAMED from `pewdiepie-archdaemon/odysseus` in Aug 2026; the old owner URL now returns 301, so treat it as stale, not dead).
- **Absolute "only X" claims are falsifiable — write them as combinations.** In the 2026-08 ecosystem run, "мы единственные, у кого есть фальсификация" got PARTIALLY REFUTED: individual components (urlhealth, RefChecker, Paperpile, Gemini self-critique) exist elsewhere; the claim survived only as "единственные по КОМПЛЕКСУ (фальсификация + immutable registry + ledger + finalize)". Synthesist guidance: when the differentiator is a pipeline, state it as the combined set ("only X has {A+B+C}"), not as sole ownership of a single component. The falsification round (Phase 5.5) is designed to hunt exactly these absolute claims — expect hits, phrase defensively.
- **Synthesist can fail.** If it does, don't discard findings — compile them into a fallback report with `status: unverified_gaps`. Raw data is better than no data.
- **Short reports happen.** If the final report is under 400 words, auto-expand with a follow-up prompt — don't accept a thin report.
- **verify_report.py is ruthless about marker placement.** Claim markers `<!-- claims: C# -->` must be at the END of a block's lines — never on separate lines (a marker-only line is treated as a block of its own and fails). Every factual prose paragraph needs BOTH `[S#]` citations AND a claim marker; a prose paragraph without `[S#]` fails as "uncited factual prose" even if it has a marker. List items get markers per-item; a long list item the formatting pass missed breaks validation. The block's `[S#]` sources must overlap the cited claim's evidence sources — `verify_report` cross-checks. Sources header must be exactly `## Sources` (English), entries `[S#] Title — URL` in registry order. Full rules: `references/verify-report-citation-format.md`.
- **Repairing markers after annotate (session-tested 2026-08-11):** `annotate_report.py --apply` can glue a claim from a DIFFERENT section onto bullet lists (C9 stamped where C18/C19/C20 belonged). `verify_report.py` catches it as "claim/source mismatch near line N" — but the flagged line may be BLANK; the offending block starts at the nearest preceding non-empty line. Deterministic fix — remap by evidence: for each block parse its `[S\d+]`s, find the claim whose evidence list contains one of them, rewrite the `<!-- claims: C# -->` marker; re-run verify until PASS. Also: if sources were re-registered mid-run (re-init after a swap/typo), audit the `## Sources` header list ONE-TO-ONE against `source_registry.json` — stale `S#`s surviving in the body now point at NEW entities (S29/S30 swapped arxiv ↔ blog.google in the 2026-08 tools run); fix IDs in BOTH the body citations and the Sources list.
- **verify 'line N' failures can point at Contradictions bullets — find them with scan_narrative_blocks.** In the 2026-08-12 benchmark run, `verify_report.py` FAIL lines ('list block near line 61/62') pointed at Contradictions & Uncertainties bullets (single-source notes like `uvik` token-overhead, LangDrained) that carried NO `[S#]` and NO claim marker — not at the section you were just editing. Don't guess which block: dump `report_model.scan_narrative_blocks(narrative)` and print every block where `not b.claim_ids or not b.source_ids` (line numbers are body-relative — add frontmatter length for file offsets). Fix each line by appending `[S#]` AND `<!-- claims: C# -->`. When you hand-stamp a marker onto such a bullet, the cited `[S#]` MUST be inside that claim's evidence — otherwise verify fails 'claim/source mismatch near line N'. The right fix for a mismatch is widening the claim's evidence (re-init → re-add ALL claims with the added `--source-id` → re-freeze; same as the no-update-command rule), NOT swapping the marker to whatever claim happens to cite that source. Session-tested 2026-08-12: C5 gained S17 in evidence to cover the token-overhead bullet.
- **annotate re-runs can EAT the `## Sources` header.** On a re-run after text edits, `annotate_report.py --apply` glues the `## Sources` line onto the previous block's claim marker (`<!-- claims: C# -->## Sources` on one line), so the header fails `^##` regex and the parser sees `sources: 0` — the entire source list becomes orphan lines. Session-tested 2026-08-12: fix is manual — split the glued line back into `<!-- claims: C# -->` and a standalone `## Sources` line, then re-run verify. Symptom to watch: verify passes structure but reports `sources: 0`; check the line right before what should be the first `[S#]` entry.
- **Add registry/claims via terminal, not execute_code.** `source_registry.py add` and `claim_ledger.py add` fail SILENTLY inside execute_code (exceptions swallowed) — registry stays empty and you only notice at freeze. Run adds through terminal, verify output; `--finding-file` paths must exist or the add fails. `--source-id` (not `--evidence-json`) is the reliable way to link claim evidence. **Batch registration (20+ sources in one terminal call):** define a shell helper `add() { python3 scripts/source_registry.py add "$RUN/source_registry.json" --title "$2" --url "$1" --source-type "$3" --date "$4" --claim-class "$5" --finding-file /tmp/fc-empty.md; }` — one shared empty placeholder satisfies `--finding-file` for every entry (the file only has to exist), so a whole investigator batch registers without per-source finding files. Verify with `python3 -c "import json; print(len(json.load(open('.../source_registry.json'))['sources']))"`. Session-tested 2026-08-12: 24 sources seeded this way in one pass.
- **delegate_task summaries are truncated — read the cache files.** In-context consolidated results trim findings (`[SUMMARY TRUNCATED] ... Showing X chars of Y`); the FULL text is saved per task at `/home/demogam/.hermes/cache/delegation/subagent-summary-{task}-{timestamp}.txt` (live transcripts under `live/`). Before writing claims: (1) harvest URLs across all summaries with a regex one-liner — `re.findall(r'https?://[^\s)\"<>]+', data)` over the `subagent-summary-*.txt` glob — to seed the source registry (investigators report URLs inline in findings, not as a separate list); (2) read the full summaries for evidence details before converting findings to claims, since the in-context digest omits the middle. Writing claims from the digest alone loses evidence specifics. Session-tested 2026-08-12 on a 3-investigator fan-out (24 URLs harvested, 10 claims written from full text).
- **Delegated director can die of context overflow.** If the nested director crashes, recover its subagents' completed work from the run log/transcripts instead of re-delegating — often 2/3 investigators already returned. Finish remaining topics manually (parallel web_search), then run the normal registry/verify/finalize chain.
- **Re-freeze after recreating claims.** If the validation chain was interrupted and you re-create/re-add `claims.jsonl` (or the registry) after an earlier `freeze`, you MUST `freeze` again before `finalize_report.py` — finalize checks frozen state, and a recreated unfrozen ledger fails it even when `verify_report.py` passed. Safe resume order after interruption: freeze registry → freeze claims → verify_report → check_sources → finalize. **The claim ledger has NO update command** — widening a claim's evidence after freeze means re-init (wipes all claims) → re-add EVERY claim → re-freeze. Get `--source-id` lists complete the first time: each claim's evidence must cover all `[S#]`s its blocks cite, or you'll pay a full claims rewrite per mismatch. Details + report_model.py debug recipe: `references/verify-report-citation-format.md`.
- **Markdown paragraph = one block.** In `report_model.py`, consecutive non-blank lines form a SINGLE narrative block; a citation anywhere in the paragraph covers the whole block. So corrupting only ONE `[S#]` in a two-line paragraph does NOT drop `citation_coverage` — the surviving citation still covers the block. When writing tests that simulate a citation drop (or debugging why a coverage test passes), remove citations from the whole paragraph, not one line, and check block boundaries with `report_model.py` block scan first.
- **Parser offsets are body-relative, not file-relative.** `scan_narrative_blocks` and friends run on the report body WITHOUT YAML frontmatter; if you apply their returned indices to the full file text, everything shifts by the frontmatter length (in one real bug: 18 lines) and edits land in the wrong place. Always: strip frontmatter → operate on body → rebuild file with frontmatter reattached. Also: a standalone `## Sources` header is dropped if you rebuild by "everything after the last heading" — find the header explicitly.
- **Version claims: verify via the package JSON API, never the rendered HTML page.** In the 2026-08-12 LangGraph run, the fact-check judge returned `refuted` on C1 ("langgraph 1.2.11") because the PyPI HTML page's file list showed 1.2.10. Two traps: (1) PyPI's `releases` dict sorts LEXICOGRAPHICALLY (`'1.2.10' > '1.2.9'` as strings), so the rendered page's "latest files" can display a lower version; (2) the HTML page lags the JSON endpoint. Deterministic fix: `curl -s https://pypi.org/pypi/<pkg>/json` → `info.version` (field is authoritative; verify the version exists in `releases` with `upload_time`). For ANY claim about an artifact's current version, instruct judges to check the machine JSON endpoint, not the HTML page. Orchestrator rule: when a judge returns `refuted` on a version claim, re-verify against the JSON API FIRST — if it confirms the claim, rewrite the verdict to `supported` with the deterministic evidence in `rationale`, and do NOT burn a judge round on it. This is a legitimate repair (Repair Round step 2) without re-dispatching. Session-tested 2026-08-12: C1 refuted → PyPI JSON confirmed 1.2.11 (upload 2026-08-11T14:00:35Z) → verdict rewritten, claim kept.\n- **Composite claims: one evidence source per fact group, or the judge returns `not_found`.** A claim bundling several independent facts (stars + forks + PyPI downloads + company count + dates) and anchored to ONE source will get `not_found`/partial from the fact-check judge, because no single page carries all of it. Session-tested 2026-08-12: C2 (GitHub stars/forks/MIT from repo page + PyPI downloads + ~400 companies) and C7 (LangGraph backward-compat from the blog + CrewAI release cadence from changelog) both got `not_found` — the judge confirmed only the part the cited page actually covers. Fix: when writing claims, either split composite facts into separate claims OR attach one evidence `--source-id` per fact group covering that exact fact (repo page for stars/forks, PyPI JSON for downloads, changelog for cadence). If the judge still flags it, that's the Repair Round re-anchor trigger — add the missing sources, not a rewrite.
- **Domain extraction collapses subdomains — design fixtures for it.** `io_utils.domain_of` takes the last 2 labels, so `a.example.com` and `b.example.com` both become `example.com`. That's CORRECT for `check_coverage.py` domain-independence (two subdomains of one registrable domain ARE one source family — e.g. mirror/blog subdomains). But it means unit fixtures must use genuinely different registrable domains (`example.com` vs `other.org`), not `a.example.com` vs `b.example.com` — the latter silently passes/fails the wrong way and looks like a script bug. Session-tested 2026-08-12: 6 check_coverage tests failed because fixtures used subdomains; fix was in the TESTS, not the script.

## Edge Cases

- **Zero results for a subtopic:** If 2 consecutive searches for a subtopic return 0 results, Director MUST exclude it from the matrix and log the reason in Gap Check as `[LACK_OF_DATA: {subtopic}]`. Do NOT keep reformulating — move on.
- **Dynamic time-boxing:** If the user's question refers to a specific recent event (launch, release, announcement), auto-detect and narrow the time-box to "last 24 hours" or "last 7 days" instead of defaulting to "last 30 days". Set this in the Prompt Master brief.
- **Enforce time-box in queries.** When a time-box is active, Investigators MUST filter results by date. Use `after:YYYY-MM-DD` in web queries, `time_range=month` for SearXNG/Reddit, `numericFilters=created_at_i>` for HN Algolia. Stale data older than time-box is REJECTED in Gap Check — do not pass it to Synthesist.
- **Verification failure after 3 retries:** If Verifier rejects the report 3 times, publish as-is with `status: unverified_gaps` in the YAML frontmatter. Add the verifier's final reason to the "Contradictions & Uncertainties" section. Do NOT loop forever.

## Appendix: Alternative Modes

### Delegated Director Mode

Use this when the user explicitly says the parent orchestrator must **not research personally** and wants subagents to find evidence and report back.

1. Dispatch one child with `role='orchestrator'` as research director.
2. Give it a self-contained brief: current date, exact local files (if any), authoritative sources, research dimensions, output schema, save path, and prohibited writes.
3. Require the director to spawn at least three independent investigators with non-overlapping domains, then perform gap-check, synthesis, and citation verification itself.
4. The parent must not call web, browser, or terminal tools for research while the delegated run is active. It only routes the mission and later verifies the returned artifact and cited URLs before presenting conclusions.
5. For audits of live configuration or context files, investigators may read exact files but must not edit them. Research and implementation approval are separate stages.
6. Return recommendations by independent domain or file rather than collapsing them into one mega-pipeline when the user wants to evaluate proposals separately.

Prefer this over several flat child calls when the parent must remain available for dialogue and the research needs iterative rounds. The nested director owns investigator batching, retries, and synthesis; the parent receives one evidence package.
