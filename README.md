# Hybrid Deep Research

A multi-round hybrid research pipeline for AI agents. Combines iterative deepening, parallel subagents, a director/investigator pattern, social signal collection (Reddit, X, Hacker News, YouTube, GitHub), pre-synthesis quality filtering, and deterministic URL verification.

## What It Does

Given a research question, the pipeline silently produces a cited research report. The user gives a request — gets a result. No intermediate output.

1. **Generates a structured brief** — auto-detects category (product / comparison / howto / factcheck / general), sets depth mode (surface / moderate / exhaustive)
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

All roles share one model. See `references/models.md` for recommendations.

## Depth Modes

| Mode | Rounds | Subtopics | Critic | Verification | Use case |
|------|--------|-----------|--------|-------------|----------|
| **surface** | 1 | 3 | No | No | Quick overviews (~2 min) |
| **moderate** | 2 | 3-5 | No | 1 retry | Default for most questions (~10 min) |
| **exhaustive** | 4 | 5 | Yes | 3 retries | Complex multi-faceted questions (~30 min) |

Prompt Master auto-detects depth from question complexity. User can override.

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

Then configure your model:

```bash
# Option 1: Set delegation.model in Hermes config
hermes config set delegation.model 'your-model-id'

# Option 2: Use config.json profiles
cp config.example.json config.json
# Edit config.json with your model and provider
```

### As a standalone reference

`SKILL.md` and `references/roles.md` contain complete role prompts adaptable to any multi-agent framework (LangGraph, CrewAI, AutoGen, etc.). The pipeline is agent-framework-agnostic — the core logic is in the prompts, not in code.

## Prerequisites

- An AI agent framework that supports:
  - **Parallel subagent dispatch** (e.g., Hermes `delegate_task`, LangGraph parallel branches)
  - **Web search** capability
  - **HTTP requests** via curl or equivalent (for GitHub API, HN Algolia API, Reddit JSON)
- A search backend (e.g., SearXNG, or any web search API)
- Optional but recommended for Reddit: authenticated access via [rdt-cli](https://github.com/htsummersky/rdt-cli) + `browser-cookie3` (reads Chrome cookies automatically, no manual export needed). Without it, Reddit falls back to `site:` search which returns poor results for niche topics.
- Optional: X/Twitter CLI, YouTube transcript tool (falls back to `site:` search)

## Configuration

1. Copy `config.example.json` to `config.json`
2. Set your model profiles (quality / balanced / fast)
3. Set `active_profile` to your default

`config.json` is gitignored — keep your local config private.

## Usage

Ask your agent to research something:

```
Research the current state of local LLM inference frameworks —
what people are using, what's new in the last 30 days, and what
the community thinks about performance vs ease of use.
```

The agent will:
1. Auto-detect category and depth
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
├── config.example.json         # Template config (copy to config.json)
├── .gitignore
├── references/
│   ├── roles.md                # Detailed role prompts for all 8 roles
│   ├── models.md               # Model recommendations by tier and provider
│   ├── improvement-roadmap.md  # v1 improvement history
│   └── improvement-roadmap-v2.md  # v2 roadmap with repo analysis
└── examples/
    └── sample-report.md        # Example output
```

## Output

Reports saved to `.hybrid-research/{slug}/`:

- `{slug}.md` — Final report with YAML frontmatter (status, topic, rounds, sources count, verification result)
- `raw_findings/` — Per-subtopic investigator findings
- `state.json` — Pipeline state for crash recovery (multi-round runs)

## Limitations

- All roles share one model (no per-role model override in `delegate_task`). To compare models, run separate research sessions.
- Reddit requires `cookies.txt` for reliable access. Without cookies, falls back to `site:` search (limited results for niche topics).
- GitHub API rate limits: 60 req/hour without token, 5000 with token.
- Social platform APIs may require authentication or have rate limits.

## License

MIT — see [LICENSE](LICENSE)
