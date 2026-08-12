# Hybrid Deep Research

A multi-round hybrid research pipeline for AI agents. Combines iterative deepening, parallel subagents, a director/investigator pattern, social signal collection (Reddit, X, Hacker News, YouTube, GitHub), pre-synthesis quality filtering, and deterministic URL verification.

## What It Does

Given a research question, the pipeline silently produces a cited research report. The user gives a request — gets a result. No intermediate output.

1. **Generates a structured brief** — auto-detects category (product / comparison / howto / factcheck / general), applies default depth (override with "quick research" / "deep dive")
2. **Decomposes** into subtopics × source matrix with per-query research goals (Director)
3. **Dispatches parallel investigators** — Web, Social, GitHub — each with focused queries and compression (200 words max per finding)
4. **Critic review** (exhaustive mode) — filters findings before synthesis: dead URLs, stale data, mislabeled credibility, internal contradictions removed
5. **Gap check + smart stop** — simplified CONTINUE/SYNTHESIZE decision, breadth halving per round
6. **Synthesizes** with source authority weighting (official docs > news > blogs > social posts), evolving report updated each round
7. **Verifies** — deterministic URL accessibility check (curl) + LLM fact-check + citation validation (max 3 retries)

## Architecture

```
User Input → Brief (auto category + depth) → Director → Investigators (parallel)
    → Gap Check → Critic (exhaustive only) → Director Review
    → (CONTINUE: Synthesist updates evolving report → loop)
    → (SYNTHESIZE: Synthesist final polish → Verifier → Report)
```

All roles share one model — the agent's default (`delegation.model`).

## Depth Modes

| Mode | Rounds | Subtopics | Critic | Verification | Use case |
|------|--------|-----------|--------|-------------|----------|
| **surface** | 1 | 3 | No | No | Quick overviews (~2 min) |
| **moderate** | 2 | 3-5 | No | 1 retry | Default for most questions (~10 min) |
| **exhaustive** | 4 | 5 | Yes | 3 retries | Complex multi-faceted questions (~30 min) |

Depth defaults to `moderate` — no guessing from question complexity. Override with "quick research" (surface) or "deep dive" (exhaustive).

## Key Features

- **Silent execution** — request → result, no intermediate output
- **Evolving report** — Synthesist updates draft each round (not build-from-scratch), uses synthesis window (last 10 findings) to control context
- **Goal-based extraction** — structured finding records: rational, evidence, summary, confidence, follow-up questions
- **Auto category detection** — product / comparison / howto / factcheck / general → format template
- **Breadth halving** — `ceil(breadth/2)` per round: start wide (4 queries), narrow deep (2 → 1)
- **Research goal carrier** — each query carries intent ("why this query, what we expect to find"), passed between rounds
- **Compression layer** — investigators compress findings to ≤200 words evidence before returning
- **Critic agent** (exhaustive mode) — pre-synthesis filtering: dead URLs, stale data, mislabeled credibility, contradictions removed
- **Source authority weighting** — `official_docs (1.0) > news (0.7) > analysis/repo (0.6) > blog (0.4) > social_post (0.3)`. On conflict, higher weight wins.
- **URL accessibility check** — Verifier curls every URL. 404/403 → `[URL_DEAD]`, timeout → `[URL_TIMEOUT]`
- **Reddit via cookies** — authenticated curl with `cookies.txt` (Reddit blocks unauthenticated JSON/RSS with 403 Cloudflare)
- **Rate limit handling** — `[SOURCE_ERROR: RATE_LIMIT]` markers, fallback to `site:` search
- **Agent failure recovery** — subagent crashes retried once, then `[AGENT_FAILED]`
- **Fallback report** — if Synthesist fails, raw findings published as `status: unverified_gaps`
- **Short report expansion** — if final report < 400 words, auto-expand with follow-up prompt
- **Dynamic time-boxing** — auto-detects "last 24 hours" for breaking news
- **Date grounding** — current date preamble prevents stale queries from training cutoff
- **Crash recovery** — state persists after each phase in `state.json`

## Installation

### As a Hermes Agent skill

Copy this directory to your Hermes skills folder:

```bash
cp -r hybrid-deep-research ~/.hermes/skills/research/
```

No model configuration needed — the skill uses `delegation.model` from the agent config.

### As a standalone reference

`SKILL.md` and `references/roles.md` contain complete role prompts adaptable to any multi-agent framework (LangGraph, CrewAI, AutoGen, etc.). The pipeline is agent-framework-agnostic — the core logic is in the prompts, not in code.

## Prerequisites

- An AI agent framework that supports:
  - **Parallel subagent dispatch** (e.g., Hermes `delegate_task`, LangGraph parallel branches)
  - **Web search** capability
  - **HTTP requests** via curl or equivalent (for GitHub API, HN Algolia API, Reddit JSON)
- A search backend (e.g., SearXNG, or any web search API)
- Optional but recommended for Reddit: authenticated access via [rdt-cli](https://github.com/htsummersky/rdt-cli) + `browser-cookie3` (reads Chrome cookies automatically, no manual export needed). Without it, Reddit sources are marked `[LACK_OF_DATA]` — there is intentionally no `site:reddit.com` fallback, since it returns irrelevant results for niche topics and lets the model fake coverage.
- Optional: X/Twitter CLI, YouTube transcript tool (falls back to `site:` search)

## Configuration

No configuration required. All roles run on `delegation.model` from the agent config.

## Usage

Ask your agent to research something:

```
Research the current state of local LLM inference frameworks —
what people are using, what's new in the last 30 days, and what
the community thinks about performance vs ease of use.
```

The agent will:
1. Auto-detect category, apply default depth
2. Run parallel investigators (silent — no intermediate output)
3. Critic-filter findings (exhaustive mode)
4. Synthesize with source authority weighting
5. Verify URLs and citations
6. Save the report to `.hybrid-research/{slug}/{slug}.md`

## File Structure

```
hybrid-deep-research/
├── SKILL.md                    # Main skill — pipeline procedure
├── README.md                   # This file
├── LICENSE                     # MIT
├── .gitignore
├── scripts/                      # Deterministic runtime (stdlib Python)
│   ├── source_registry.py        # Frozen source registry — URL fabrication impossible
│   ├── claim_ledger.py           # Claim ledger with evidence links
│   ├── check_sources.py          # HTTP accessibility classification
│   ├── verify_report.py          # Structural validation of the report
│   ├── finalize_report.py        # Writes status: validated only after checks pass
│   ├── annotate_report.py        # Auto-inserts claim markers (<!-- claims: C# -->)
│   ├── fact_check_claims.py      # Semantic fact-check tasks + verdicts + verbatim numeric check
│   ├── eval_citations.py         # Citation-quality scoring: link works / relevant / fact check
│   ├── dedup_claims.py           # Deterministic claim dedup (same numbers, source overlap)
│   ├── check_coverage.py         # Coverage assertions: domain independence + primary preference
│   ├── escalations.py            # Structured human escalation (refuted ⇒ needs_review)
│   ├── run_benchmark.py          # Benchmark runner: briefs from evals + baseline tracking
│   ├── research_state.py         # Global budgets + adaptive stop + per-subtopic saturation
│   └── ...                       # io_utils, report_model, benchmark
├── tests/                        # 135 unit/integration tests
├── fixtures/                     # Valid EN/ES end-to-end fixtures
├── evals/                        # Benchmark questions
├── references/
│   ├── roles.md                # Detailed role prompts for all 8 roles
│   ├── improvement-roadmap.md  # v1 improvement history
│   └── improvement-roadmap-v2.md  # v2 roadmap with repo analysis
└── examples/
    └── sample-report.md        # Example output
```

LLMs make semantic decisions; `scripts/` enforce invariants. Run `python3 -m pytest tests/` to verify. The pipeline degrades gracefully: without Python it falls back to prompt-level URL checks and marks the report `unverified_gaps`.

## Benchmarking

Track whether the skill actually improves over time — not just "tests pass":

```bash
# create a run brief from an evals question
python3 scripts/run_benchmark.py prepare --question software-01 --out .hybrid-research/bench-software-01
# run the research pipeline on that brief (agent work), then score it:
python3 scripts/run_benchmark.py score --runs .hybrid-research/bench-software-01 \
    --baseline .hybrid-research/benchmark-results.json
# view the baseline table
python3 scripts/run_benchmark.py baseline --baseline .hybrid-research/benchmark-results.json
```

`score` combines `benchmark.py` quality metrics (validation, citation coverage, primary-source ratio, access health, budget utilization) with `eval_citations.py` triad scores (link works / relevant / fact check) and the **DRACO-style rubric** (`rubric_*` metrics): factual accuracy ≈50% weight + negative penalties for refuted/not_found claims, numeric mismatches, and unresolved critical claims. Appends to the baseline, and exits 1 if any metric degraded vs the previous run of the same id. See `evals/questions.json` for available benchmark questions.

## Output

Reports saved to `.hybrid-research/{slug}/`:

- `{slug}.md` — Final report with YAML frontmatter (status, topic, rounds, sources count, verification result)
- `raw_findings/` — Per-subtopic investigator findings
- `state.json` — Pipeline state for crash recovery (multi-round runs)

## Limitations

- All roles share one model (`delegation.model`) — no per-role model override in `delegate_task`.
- Reddit requires `cookies.txt` (or rdt-cli) for reliable access. Without it, Reddit sources are marked `[LACK_OF_DATA]` — no `site:` fallback.
- GitHub API rate limits: 60 req/hour without token, 5000 with token.
- Social platform APIs may require authentication or have rate limits.

## License

MIT — see [LICENSE](LICENSE)
