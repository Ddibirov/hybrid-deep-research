# verify_report.py — citation/claim marker format (hard-won rules)

Learned the expensive way during the dogfood run 2026-08-10/11 (improvements research).
`verify_report.py` FAILs on any of the following; each cost several fix iterations.

## Sources section

- Header MUST be literally `## Sources` (English). A Russian header (`## Источники`) is not parsed.
- Entries: `[S#] Title — URL`, order MUST match the frozen `source_registry.json` (S numbers assigned by `source_registry.py add`). If registry and report disagree on S#↔URL, validation fails.
- `[S#]` markers used in the body come from this registry. Unknown S# → rejected.

## Claim markers

- Format: `<!-- claims: C3 -->`
- MUST sit at the END of a line that belongs to the block — inline at end of the line, not on a separate line. A marker on its own line is parsed as its own (empty) block and fails.
- Marker on a list item: append to the item line.
- Marker on a prose paragraph: append to the (single) paragraph line.

## Citation markers

- Every factual block needs BOTH:
  1. `[S#]` citation(s) inside the text (e.g. `[S8][S9]`)
  2. `<!-- claims: C# -->` marker
- A prose paragraph with a claim marker but NO `[S#]` → "uncited factual prose paragraph" fail.
- A prose paragraph with `[S#]` but no claim marker → "prose block missing claim marker" fail.
- The block's `[S#]` sources MUST overlap the cited claim's evidence sources. If the claim's evidence is only S1 but the paragraph cites S2-S5, it fails. Fix: widen claim evidence (`--source-id S2 --source-id S5`...) or narrow the paragraph's citations.

## claim/source mismatch — exact error and resolution (hit again 2026-08-11 live run)

Error: `claim/source mismatch near line N: C# is not supported by cited sources`.

Meaning: the block's cited `[S#]`s are NOT covered by the claim's evidence. Two cases:

1. **Claim's evidence is too narrow** (paragraph cites S2-S5, claim evidence only S1) → widen the claim's `--source-id` list.
2. **No existing claim covers those sources at all** (e.g. a list item citing S21/S22 with no matching claim) → either extend the nearest claim's evidence to include them, or add a NEW claim with exactly those sources and append its marker `<!-- claims: C# -->` to the block's line.

**The claim ledger has NO update command.** Widening evidence after `freeze` = re-init the ledger (wipes ALL claims) → re-add every claim with the widened `--source-id` lists → `freeze` again → `verify_report.py`. Re-adding only the changed claim is not enough — init empties the file. Cost: one full claims rewrite per mismatch, so get the evidence lists right the first time: every claim's `--source-id` set should cover all the `[S#]`s its blocks cite.

## Debugging verify failures fast (report_model.py)

The verify error gives line numbers but not block shape. Instead of guessing which line is what, inspect programmatically:

```python
import sys; sys.path.insert(0, "<skill>/scripts")
import report_model as rm
text = open("<run>/report.md").read()
_, body = rm.parse_frontmatter(text)
narrative, sources_text = rm.split_sources(body)
for b in rm.scan_narrative_blocks(narrative):
    if b.line in (22, 40):  # lines from the error
        print(b.line, b.kind, b.source_ids, b.claim_ids, b.text[:150])
```

Shows each block's kind (`prose`/`list`), cited source IDs, and claim marker IDs — tells you instantly whether the problem is a missing marker, an uncited block, or a claim/evidence mismatch. Verified in the 2026-08-11 live run: the error lines 33/49 were stale output; the real offenders were found via this dump.

## List items

- Each list item line gets its own marker. Long items (many `—` separated names) get missed by automated passes — always spot-check the longest items.
- Items with `[S#]` but no marker → fail.

## Registry/claim add — run via terminal, not execute_code

- `source_registry.py add` and `claim_ledger.py add` swallow exceptions inside `execute_code` (hermes_tools wrapper). The add silently does nothing; you discover the empty registry only at freeze/verify.
- Run adds via `terminal`, read the output (confirms `S#` assignment).
- `--finding-file` must exist or add fails.
- Claim evidence: use `--source-id` flags (reliable), not `--evidence-json` (gets wrapped/nested).

## Crash recovery for delegated director mode

- Director (orchestrator child) can die of context overflow mid-run; the parent gets no result.
- Its subagents often completed before the crash — their findings live in the delegation log/transcripts. Extract them.
- Finish the missing topics with direct parallel `web_search` from the parent; then run the normal chain: registry adds → claims → freeze → verify_report → check_sources → finalize.
- Do NOT re-delegate the whole run — cheaper to finish the 1-2 missing topics manually.
