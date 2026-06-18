---
name: hybrid-deep-research
description: >-
  Multi-round hybrid research pipeline. Combines iterative deepening,
  parallel subagents, director/investigator pattern, social signal collection
  (Reddit, X, HN, YouTube, GitHub), and verification with retry.
  Use when user asks for "deep research", "research report", "investigate X",
  "what's happening with Y", "comprehensive analysis of Z", or any question
  requiring 5+ sources synthesized into a structured report with citations.
version: 4.0.1
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

**Silent execution.** The user gives a research request and receives the final report. Nothing in between.

- Do NOT show intermediate phases, progress updates, logs, or statistics
- Do NOT ask for brief approval unless the user explicitly wants it — use the question to auto-detect scope and proceed
- Do NOT output "Phase 1:...", "Phase 2:...", "Using model:...", "Round 1...", "Findings:...", "Gap Check:...", "Director Decision:..." or any pipeline internals
- DO save the report to `.hybrid-research/{slug}/{slug}.md`
- DO send the report content to the user as the final message
- If the research fails (search unavailable, all investigators crash), send a brief error message — not pipeline diagnostics

The user sees: request → result. That's it.

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
    ║  ┌──────┘           │                          ║
    ║  │ 6. SYNTHESIST    │                          ║
    ║  │  (evolving mode) │                          ║
    ║  │  Update draft    │                          ║
    ║  └───────┬──────────┘                          ║
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

## Model Configuration

**All roles in a run use one model** (set via `delegation.model` in your agent config).

See `references/models.md` for model recommendations by tier.
See `references/odysseus-analysis.md` for analysis of the Odysseus deep research engine.
See `references/improvement-roadmap-v2.md` for improvement roadmap (meta-research + repo analysis, 11 actionable items).
See `references/repo-analysis-dzhng.md`, `references/repo-analysis-gpt-researcher.md`, `references/repo-analysis-langchain.md` for detailed architectural analysis of reference implementations.
See `references/test-run-2026-06-18.md` for first pipeline test run analysis — pitfalls and lessons learned.

**To compare models:** run the same research question as separate runs with different models. Save each report, then compare.

## Config

Copy `config.example.json` to `config.json` and adjust for your environment:

```json
{
  "active_profile": "balanced",
  "profiles": {
    "quality": { "model": "your-strong-model", "provider": "your-provider" },
    "balanced": { "model": "your-default-model", "provider": "your-provider" },
    "fast": { "model": "your-fast-model", "provider": "your-provider" }
  }
}
```

`config.json` is local — do not commit it. `config.example.json` is the template.

## Procedure

### Phase 0: Model Check

Read `delegation.model` from agent config. Display: "Using model: {model} (provider: {provider})".

If no model configured, prompt user to pick a profile from `config.json` and set it.

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

Prompt Master auto-detects depth from question complexity. User can override in brief approval (if enabled) or by saying "quick research" / "deep dive".

**If user mentions "what people say" / "reaction" / "opinion"** → emphasize social sources (Reddit, X, HN).
**If user mentions "official" / "announcement" / "release"** → emphasize web + GitHub.
**If user mentions "trend" / "happening" / "recent"** → set time-box to 30 days + social sources.

### Phase 1b: Brief Approval (Human-in-the-Loop)

**This step is OFF by default.** Only ask for approval if the user explicitly says "let me see the plan first" or the question is highly ambiguous. Default: proceed silently from question to report.

Present the brief to the user (including detected category and output format). User confirms (Y) or adjusts:
- "Don't search Reddit, only GitHub"
- "Add Polymarket for prediction markets"
- "Narrow to last 7 days"
- "Skip social, focus on official docs"
- "Make it a comparison" or "Just give me a summary" (overrides detected category)

If user confirms → proceed to Director. If user adjusts → regenerate brief with adjustments, then proceed.

**Skip this step** if user explicitly says "just research it" or the question is unambiguous.

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
- Social queries: Reddit requires authenticated curl with cookies.txt (Reddit blocks unauthenticated JSON/RSS with 403 Cloudflare). Use `curl --cookie cookies.txt` for Reddit JSON API (cookies.txt exported from Chrome — see your agent framework's cookie export method). Fall back to `web_search` with `site:` operator if cookies unavailable. See `references/roles.md` for details.
- GitHub queries: use GitHub API via `curl`
- All investigators must cite URLs and dates
- **Rate limit handling:** If any HTTP request returns 429 or 5xx, immediately mark that query as `[SOURCE_ERROR: RATE_LIMIT]` or `[SOURCE_ERROR: SERVER_DOWN]` and move on. Do NOT retry. Do NOT treat a failed request as "no data found."
- **Fallback for blocked APIs:** If GitHub API returns 401/403/429, fall back to `web_search(query="{query} site:github.com")`. If Reddit/search backend returns 429, fall back to `web_search(query="{query} site:reddit.com")`. Mark the source as `[FALLBACK: web_search]` in findings.
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
```

**If 0 gaps → proceed to synthesis.**
**If gaps (and rate-limited/zero-result sources are not the only gaps) → Director reformulates queries for next round.**

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

**SYNTHESIZE triggers:**
- All key aspects covered with 2+ sources
- Social + web findings aligned
- 4 rounds reached (or depth-based max: surface=1, moderate=2, exhaustive=4)
- Two consecutive rounds with no new data
- Persistent rate limits blocking critical subtopics (note in Uncertainties section)
- **Zero-results subtopic excluded** (see "Edge Cases" below)

**Evolving report update:** If Decision is CONTINUE, before looping back, run Synthesist in evolving mode:
- Take `evolving_report` from state.json + this round's new findings
- Synthesist produces updated draft report
- Save updated draft back to state.json as `evolving_report`
- The report grows organically round by round

**Smart stop rule:** If round_num is well below max_rounds (e.g. round 1-2), prefer CONTINUE unless the report is already exhaustive. This prevents premature stopping early in the process.

### Phase 6: Synthesis

Synthesist operates in two modes:

**Per-round synthesis (evolving mode):** After each round's Director Review, if CONTINUE, Synthesist takes `evolving_report` (from state.json) + this round's new findings → updated draft. Uses only the last `synthesis_window` (default 10) findings to control context — earlier findings are already integrated into the draft. Saves updated draft back to state.json.

**Final synthesis (polish mode):** When Director says SYNTHESIZE, Synthesist takes the `evolving_report` + any remaining findings → produces the final polished report with full structure, citations, category format.

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

**URL accessibility check (deterministic):** Before LLM-based verification, curl every URL from the Sources section:
- `curl -s -o /dev/null -w "%{http_code}" {url}` (timeout 10s per URL)
- 200 → OK
- 404/403/5xx → mark as `[URL_DEAD: {status_code}]` in the report's Sources section
- Redirect (301/302) → follow redirect, note final URL
- Timeout → mark as `[URL_TIMEOUT]`
- Dead URLs do NOT auto-fail verification, but the report must note them

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
  "started_at": "ISO-8601",
  "director_decisions": []
}
```

**State is optional** for simple runs (1 round, 3 subtopics — only the report needs saving). **Mandatory** for multi-round scenarios or crash-recovery.

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
- **Handle 429 rate limits explicitly.** Return `[SOURCE_ERROR: RATE_LIMIT]` and stop. Never retry in the same round. Use fallback to `web_search` with `site:` operator.
- **Don't trust social engagement alone.** Viral ≠ accurate. Cross-validate with web sources.
- **Hard limit: 4 rounds (exhaustive mode).** Surface=1, moderate=2, exhaustive=4. Director respects depth mode. If not enough after max rounds, report what you have with gaps noted.
- **Verification is mandatory.** 3 retries max. After 3 FAILs → publish with `status: unverified_gaps`.
- **Prune before Synthesis.** Investigators must return structured records (rational, evidence, summary) — not raw prose. Low-quality findings (boilerplate, cookie banners, copyright notices) must be discarded at extraction time.
- **All roles share one model.** There is no per-role model separation. To compare models, run separate research sessions.
- **Agent failures happen.** Subagents can crash, timeout, or return garbage. Always retry once, then log `[AGENT_FAILED]` and let Director decide.
- **Web extract limit.** Investigators MUST NOT call web_extract more than 3 times per round. After 3 extractions — work with search snippets only. Excessive web_extract calls cause subagent timeouts (600s limit). In the test run, one investigator timed out after 13 API calls — the retry with 0 web_extract calls completed in 61 seconds.
- **web_extract is the #1 timeout cause.** Investigators that call web_extract on every search result will timeout at 600s. Limit to 2-3 web_extract calls per investigator. If an investigator times out, retry with a LIGHTWEIGHT variant: "DO NOT use web_extract. Only use web_search and curl. Summarize from search result snippets only." This completes in ~60s vs 600s timeout.
- **Reddit blocks unauthenticated access.** `web_search("{query} site:reddit.com")` returns irrelevant results for niche topics. Use cookies.txt with curl for Reddit JSON API. If cookies are unavailable, mark Reddit as `[LACK_OF_DATA]` — do not rely on site: search for Reddit.
- **Synthesis subagents fabricate URLs.** When generating the final report, the Synthesist may produce plausible-but-wrong GitHub URLs (wrong org name, wrong repo name). The Verifier MUST cross-check every URL against the actual findings. Common fabrications: `github.com/Tongyi-Research/DeepResearch` (correct: `Alibaba-NLP/DeepResearch`), `github.com/pewdiepie/odysseus` (correct: `pewdiepie-archdaemon/odysseus`).
- **Synthesist can fail.** If it does, don't discard findings — compile them into a fallback report with `status: unverified_gaps`. Raw data is better than no data.
- **Short reports happen.** If the final report is under 400 words, auto-expand with a follow-up prompt — don't accept a thin report.

## Edge Cases

- **Zero results for a subtopic:** If 2 consecutive searches for a subtopic return 0 results, Director MUST exclude it from the matrix and log the reason in Gap Check as `[LACK_OF_DATA: {subtopic}]`. Do NOT keep reformulating — move on.
- **Dynamic time-boxing:** If the user's question refers to a specific recent event (launch, release, announcement), auto-detect and narrow the time-box to "last 24 hours" or "last 7 days" instead of defaulting to "last 30 days". Set this in the Prompt Master brief.
- **Enforce time-box in queries.** When a time-box is active, Investigators MUST filter results by date. Use `after:YYYY-MM-DD` in web queries, `time_range=month` for SearXNG/Reddit, `numericFilters=created_at_i>` for HN Algolia. Stale data older than time-box is REJECTED in Gap Check — do not pass it to Synthesist.
- **Verification failure after 3 retries:** If Verifier rejects the report 3 times, publish as-is with `status: unverified_gaps` in the YAML frontmatter. Add the verifier's final reason to the "Contradictions & Uncertainties" section. Do NOT loop forever.
