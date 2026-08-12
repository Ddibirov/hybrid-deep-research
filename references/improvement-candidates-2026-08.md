# Deep research improvement candidates — dogfood run 2026-08-10

Source: self-research run (`~/.hybrid-research/deep-research-improvements-20260810/report.md`),
collected from web + subagent findings. Verification of that report was interrupted at the final
`verify_report` step — treat numbers as directional, re-check before adopting. Themes for the
next improvement cycle of this skill.

## 1. Benchmarks (how quality is measured)

- DRB / DRB II — evaluation of research reports via expert rubrics; headline is report quality, not
  just tool-call counts.
- Live leaders (2026-08): Perplexity ~90.24% citation accuracy (highest); Gemini ~111 effective
  citations (most). #1 CellCog Max 55.78 on one leaderboard; OpenAI GPT-o3 DR 39.98.
- Lesson: measure citation accuracy separately from source count — a report with 100 URLs and bad
  attribution loses to one with 20 correct ones.

## 2. Frameworks / patterns worth stealing

- Branching / search tree (forking alternative lines instead of linear rounds).
- Agent memory across runs (persistent, graph-vector hybrid) — our `state.json` is the seed.
- Self-reflection loops inside the agent (critic on its own draft before emitting).
- Document-level granularity — treat a document as a unit, not snippets (maps to our `web_extract`).
- Async role communication instead of a rigid pipeline.

## 3. Adaptive compute (token budget)

- ASC (Adaptive Self-Consistency): vary #LLM calls by confidence signal (entropy, margin, agreement).
- TrACE: agreement across independent rollouts as a free adaptive-compute signal; same accuracy as
  SC-k8 with fewer calls.
- Seer Self-Consistency: pre-estimate budget per question (difficulty-aware), stop on answer-window
  convergence; up to ~6.8× token savings at same accuracy.
- Adaptive Thinking (ICLR 2026): self-consistency as complexity proxy beats entropy metrics.
- Our Director Review / "no new data 2 rounds" is a primitive adaptive-stop — formalize in Phase 5.

## 4. Verification / hallucination control

- Strict citation contract (each fact → passage ID; no evidence → abstain) roughly halves
  hallucinations. We check after generation; the fix is abstention AT synthesis time.
- "What would you verify manually" — human-useful filter for what deserves checking.

## 5. Social layer (what users actually want)

- Cost/limits are the #1 pain; source transparency is the #1 trust criterion.
- Reddit thread feedback on our skill post (r/hermesagent 1vkftx8):
  - "Pure prompts only? Gotta check it out" — interest in the no-code story.
  - User-described iterative process: goal → shallow scans → fake-hypothesis falsification →
    probability ratings; their own role is bullshit detector + report-shape guide; 95% on GLM 5.1/5.2.
  - The bullshit-detector / falsification round is the feature people say is missing in tools.
