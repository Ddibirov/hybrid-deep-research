# Deep research evidence base — web research round 2026-08-11 (v4.6.0)

Source: web research ("Поищи в инете еще как можно улучшить", 2026-08-11).
8+ sources consulted; 5 findings adopted into v4.6.0. Do not re-propose these
as new ideas — they are implemented. Re-check numbers before re-citing.

## Sources consulted

- arXiv 2605.06635 — "Cited but Not Verified" (factual accuracy vs link survival)
- ICLR 2026 paper(s) — adaptive compute / self-consistency (also covered in
  `improvement-candidates-2026-08.md` §3)
- Anthropic engineering — deep research agent guidance
- DeepResearchBench / DRACO / DEER — research-agent evaluation suites
- Zep CoVE — claims-vs-sources verification approach
- niteagent — agent architecture notes

## Headline evidence (the numbers that drove v4.6.0)

- **Link survival ≠ factual accuracy.** Frontier models keep cited links alive in
  ~94%+ of cases while factual accuracy sits at ~39-77%. Verifying a URL exists
  (Phase 7 `verify_report.py`) does NOT verify the source supports the claim.
  → Phase 7.5 Semantic Fact-Check (`fact_check_claims.py`).
- **Information overload degrades synthesis.** arXiv ablation: Fact Check accuracy
  drops ~42% as tool calls scale 2→150, while link/relevance metrics stay stable.
  More retrieval makes the report WORSE, not better. → >30 sources ⇒ Phase 7.5
  mandatory; never equate source count with accuracy.
- **Cascading errors beat end-of-turn fixes.** A wrong intermediate conclusion in
  Round 1 propagates through all later rounds; end-checking (Phase 7) catches the
  final report but not the decisions it was built on. → per-round verification gate.

## Adopted in v4.6.0

1. Phase 7.5 Semantic Fact-Check — `scripts/fact_check_claims.py`
   (prepare → LLM judge verdicts `supported|refuted|not_found` → collect, exit 0
   only when all supported). Mandatory >30 sources.
2. Per-round verification gate — Phase 6, 3 questions per round, answers into
   `state.json.round_gates`.
3. Information-overload pitfall — ">30 sources ⇒ fact-check mandatory", "more
   sources ≠ more accurate".
4. Low-confidence escalation — "## Требует ручной проверки" block after Executive
   Summary for every `[confidence: low]` claim; `low`+`refuted` → both flags.
5. Citation-quality scoring — `scripts/eval_citations.py`: arXiv triad
   Link Works / Relevant / Fact Check. Live-run baseline: Link 30/32 (0.938),
   Relevant 0.938, Fact Check 4/6 (0.667).

## Validation

- 84 unit tests (`tests/`, 6 new for fact-check + eval-citations).
- Both new scripts exercised on a live run with real registry/claims data.
