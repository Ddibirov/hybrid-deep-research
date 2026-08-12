# Deep research ecosystem snapshot — 2026-08-11 (dogsled run, 3 investigators + 2 falsifiers)

Source: self-research run (`~/.hybrid-research/dr-tools-skills-2026/`), 20 registered sources.
Question: "tools/skills/plugins for deep research ecosystem — what to use, what to steal".
Stars/activity = GitHub API as of 2026-08-11 (not marketing pages). Treat as directional —
re-check before re-citing.

## MCP search servers (budget verdict for an agent like ours)

| Tool | Stars | Free tier | Verdict |
|---|---|---|---|
| Tavily MCP | 2.3k | 1000 cr/mo | ✅ best price/quality; research mode (multi-step plan); bought by Nebius Feb 2026 — price risk |
| Exa MCP | 4.9k | 1000 req/mo | ✅ best retrieval (~81% vs Tavily ~71% in one bench), 50-75% fewer tokens via query-dependent highlights; usage billing — cap it |
| Firecrawl MCP | 7.2k | 1000 cr/mo | 🟡 best web parsing to LLM-markdown; needed only under crawl load; credits don't roll over |
| Brave Search MCP | 1.4k | free tier REMOVED 2026-02-12 | ❌ $5/mo credit, search only (no extract) |
| Small "deep research MCP" (octagon 93★ etc.) | <250 | — | ❌ junk tail; prefer search MCP + framework, not a 200★ all-in-one |

## Frameworks / open-source agents (for benchmarking ourselves)

- **OpenManus** 57.9k★ (push 02.2026 — slowed) — universal agent engine, NOT research-focused; raw; skip for DR.
- **gpt-researcher** 28.9k★ (push 07.2026) — most mature (since 2023); own MCP server; 7-role team.
- **Tongyi DeepResearch (Alibaba-NLP)** 19.8k★ — base that Odysseus adapts; strong alternative to MiroFlow.
- **dzhng/deep-research** 19.5k★ — <500 LoC reference implementation of the pattern (breadth/depth loop). Where it all started.
- **langchain-ai/open_deep_research** 12.6k★, push 2026-08-10 (most active in category) — LangGraph reference; #6 Deep Research Bench; no Docker/CI/rate-limit/JSON logs — build infra yourself.
- **local-deep-researcher** (langchain-ai) 9.3k★ — Ollama/fully-local; the zero-API- key option for RU/VPN contexts.
- **MiroFlow** (MiroMindAI) 3.1k★ + MiroThinker 8.4k★ — top of 2026 open benchmarks (GAIA 82.4% vs OpenAI DR 67.4%); demands GPT-5/Claude-class models + heavy tokens.
- **Khoj** 36.5k★ — self-hosted "second brain" with DR; product with UI, not a pipeline.
- Dying/dead (stars ≠ maintenance): DeepSearcher (zilliz, push 11.2025 ~9 mo silence), nano-graphrag (01.2026), Stanford STORM (09.2025).
- Ru-specific open-source DR agents: none found [LACK_OF_DATA]; RU pattern = local-deep-researcher + keyless search (Hound).

## Skills / plugins (why our shape is right)

- **Agent Skills standard** (Anthropic, Oct 2025; spec agentskills.io 2025-12-18): SKILL.md runs in Claude Code, Codex, Copilot, Gemini CLI, Hermes (~40 products). Marketplace exploded 2,179 → 40,285 skills in 20 days (Jan-Feb 2026); quality/security unverified (arXiv 2602.08004).
- Research skills exist for Claude/Hermes (tavily-search, tavily-deep-research, NVIDIA AI-Q). We already ship: hybrid-deep-research, structured-research, web-search, grounded-citations, evidence-based-replies.
- Conclusion: skills are the cheapest cross-vendor distribution unit; deterministic runtime inside a skill (our registry/ledger) is still a differentiator — no open framework pairs an LLM pipeline with frozen provenance.

## Odysseus (PewDiePie) — deep-dive update vs `references/odysseus-analysis.md`

- **RENAMED**: `pewdiepie-archdaemon/odysseus` → `odysseus-dev/odysseus` (GitHub API 301; old URL works via redirect). 85,186★ (was 72.9k), AGPL-3.0, Python, created 2026-05-31, push 2026-08-11 (hyperactive), default branch `dev`.
- Confirmed NOT multiagent: single LLM loop `DeepResearcher` (src/deep_research.py, 929 lines) = Tongyi IterResearch adaptation (ACKNOWLEDGMENTS.md). Roles via prompts: planner (JSON sub_questions/key_topics/success_criteria), query generator (4→3), extractor (JSON rational/evidence/summary), synthesizer (evolving report), stopper (YES/NO).
- Search chain w/ fallback: SearXNG (default, self-hosted, keyless) → Brave / DDG / Google PSE / Tavily; `_FALLBACK_ORDER=["duckduckgo"]`.
- Source handling: inline `[text](url)` citations + `### Sources` section parsed to list; URL dedup; `is_low_quality()` filter; category factcheck = Evidence For/Against + Verdict. **No separate fact-check/verifier agent.**
- Weakness: `synthesis_window=10` — mid-run findings beyond the last 10 are lost (long runs); single LLM does all roles = no isolation.
- Strengths: production-grade orchestration (background task registry, 1800s wall-clock default, probe before run, fallback reports), strong security tests (XSS, path confinement, owner scope), ~30 research test files.
- Homepage: odysseus-dev.github.io/odysseus. Announced by PewDiePie "MY trillion $Dollar Project is finally OUT!" — HN 245 pts ~67 days prior.

## Row-level takeaway vs our v4.7

We already lead the open ecosystem on: falsification round (Phase 5.5), deterministic provenance (registry/ledger/freeze/finalize), citation quality scoring, semantic fact-check. Nobody public (OpenAI/Gemini/Perplexity/OpenManus) ships a verifier-style falsification + runtime-governance combo. Laggards vs 2026 practice: verification as final gate (not test-time scaling loop), no rubric-based scoring in the benchmark, dedup left to LLM, unstructured human escalation, no verbatim numeric check.

## NEW improvement candidates (2026-08-11 dogsled round — **ALL ADOPTED in v4.8.0, 2026-08-12**)

Priority pairs (effort→effect):
1. ✅ **Repair Round (Phase 7.6)** — each refuted/not_found claim from Phase 7.5 gets ONE targeted repair pass (≤3 queries, re-register, re-anchor or drop) before finalize; budget ≤5 claims. Verification as test-time scaling, not just a gate. (arXiv 2603.28376 — errors propagate downstream; 8B w/ verification beats 30B agents at 600 tool calls.)
2. ✅ **DRACO-style rubric scoring in `run_benchmark.py`** — `rubric_*` metrics: factual accuracy ≈50% weight + NEGATIVE criteria for hallucination (refuted ×0.35, not_found ×0.20, numeric mismatch ×0.25, unresolved critical ×0.30 per claim), breadth/depth, presentation, primary-source citation; regression gate covers rubric metrics. We can publish what OpenAI/Gemini won't: reproducible internal metric.
3. ✅ **Deterministic dedup (`dedup_claims.py`)** — mechanical ~80% of duplicates (identical normalized text, same numbers + overlapping source sets, heavy source-set overlap on high-importance claims) via normalization + source-set intersection → `[DUP]` before Gap Check; LLM dedup only for paraphrases.
4. ✅ **`check_coverage.py` assertions in finalize** — per key claim: (a) ≥2 sources from DIFFERENT domains (registry knows domain; mirrors flagged); (b) primary-source preference — product/company claim weighted 0.4-0.3 (blog/social) w/o official_docs ⇒ confidence ≤ medium; (c) success-criteria checklist from brief. Fail ⇒ `status: coverage_gap`, not validated.
5. ✅ **Per-subtopic adaptive depth** — `research_state.subtopic_saturated` (≥3 high-cred sources on all key aspects → skip next round) + `mark_saturated`. Complements global adaptive stop.
6. ✅ **Structured human escalation (`escalations.py`)** — machine-readable (claim_id, verdict, conflicting S#, recommended re-anchor/drop/keep-with-caveat) instead of prose block; deterministic rule: refuted or numeric-mismatch claim reaching final ⇒ `status: needs_review` mandatory, `validated` forbidden (enforced by `finalize_report.py --escalations`). Preserves silent mode (no mid-run interrupts).
7. ✅ **Verbatim numeric verification in `fact_check_claims.py`** — judge checks the source carries THE SAME number/date/price as the claim (`numeric_check` in verdict: match|mismatch|none; `claimed_numbers` extracted mechanically in prepare); metric `numeric_precision` in collect + eval_citations. Prices/dates/stats = most expensive hallucination class (citation accuracy is worst task even w/ extended thinking: 14.7%→9.3% error after improvement).