#!/usr/bin/env python3
"""Auto-annotate report blocks with claim markers (Phase 6 helper).

The verify_report validator requires every factual block to carry a
`<!-- claims: C# -->` marker whose claim's evidence sources intersect the
block's cited [S#] sources. Doing that by hand is error-prone; this script
does it deterministically:

  python3 scripts/annotate_report.py report.md \
      --registry source_registry.json --claims claims.jsonl \
      [--apply] [--dry-run]

Default is --dry-run (print what would change). Use --apply to rewrite the
file. Blocks that already have a marker are left untouched; blocks whose
cited sources match no claim get a [UNANNOTATED] note in the dry-run output
so the orchestrator can fix them (add the missing claim or citation).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_model import (  # noqa: E402
    CLAIM_MARKER_RE,
    LIST_RE,
    QUOTE_RE,
    STEP_RE,
    TABLE_DELIM_RE,
    find_sources_heading,
    parse_frontmatter,
    scan_narrative_blocks,
    split_sources,
)

CITATION_RE = re.compile(r"\[(S\d+)\]")


def load_claim_evidence(claims_path: Path) -> dict[str, set[str]]:
    """Map claim id -> set of evidence source ids."""
    result: dict[str, set[str]] = {}
    if not claims_path:
        return result
    for line in claims_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or "_meta" in line:
            continue
        item = json.loads(line)
        cid = item.get("id")
        if not cid:
            continue
        sources = {
            e.get("source_id")
            for e in item.get("evidence", [])
            if isinstance(e, dict) and e.get("source_id")
        }
        result[cid] = sources
    return result


def pick_marker(block_sources: set[str], claim_evidence: dict[str, set[str]]) -> str | None:
    """Pick the claim whose evidence overlaps the block's sources the most."""
    best_cid, best_overlap = None, 0
    for cid, evidence in claim_evidence.items():
        overlap = len(block_sources & evidence)
        if overlap > best_overlap:
            best_cid, best_overlap = cid, overlap
    return best_cid


def annotate(markdown: str, claim_evidence: dict[str, set[str]]) -> tuple[list[str], str]:
    """Return (warnings, rewritten_full_markdown). Rewrites only blocks lacking a marker."""
    frontmatter, body = parse_frontmatter(markdown)
    # find the Sources heading; narrative = everything before it (heading preserved
    # by splitting at match.start()), sources = heading + rest
    match = find_sources_heading(body)
    if match:
        narrative = body[: match.start()]
        sources_text = body[match.start() :]
    else:
        narrative = body
        sources_text = ""
    narrative_lines = narrative.splitlines()

    # collect blocks needing markers: (0-based index in narrative_lines, source_ids)
    targets: list[tuple[int, set[str]]] = []
    for block in scan_narrative_blocks(narrative):
        if block.claim_ids:  # already annotated
            continue
        if not block.source_ids:  # uncited block — verify would fail anyway
            continue
        targets.append((block.line - 1, set(block.source_ids)))

    # apply in reverse so line indices stay valid
    warnings: list[str] = []
    for idx, srcs in sorted(targets, reverse=True):
        marker = pick_marker(srcs, claim_evidence)
        if marker is None:
            warnings.append(f"line {idx + 1}: no claim matches sources {sorted(srcs)}")
            continue
        line = narrative_lines[idx]
        if CLAIM_MARKER_RE.search(line):
            continue
        narrative_lines[idx] = line.rstrip() + f" <!-- claims: {marker} -->"

    rewritten_narrative = "\n".join(narrative_lines)
    rewritten_body = rewritten_narrative + sources_text
    if frontmatter:
        rewritten = "---\n" + frontmatter_text(markdown) + "---\n" + rewritten_body
    else:
        rewritten = rewritten_body
    return warnings, rewritten


def frontmatter_text(markdown: str) -> str:
    """Return the raw frontmatter block (without the surrounding ---)."""
    if not markdown.startswith("---\n"):
        return ""
    end = markdown.find("\n---\n", 4)
    if end == -1:
        return ""
    return markdown[4:end] + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--registry", type=Path, help="unused; kept for interface symmetry")
    parser.add_argument("--claims", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="rewrite the file (default: dry-run)")
    args = parser.parse_args(argv)

    claim_evidence = load_claim_evidence(args.claims)
    if not claim_evidence:
        print("WARNING: no claims loaded; nothing to annotate", file=sys.stderr)
        return 1

    markdown = args.report.read_text(encoding="utf-8")
    warnings, rewritten = annotate(markdown, claim_evidence)

    for w in warnings:
        print("WARNING:", w)
    if args.apply:
        args.report.write_text(rewritten, encoding="utf-8")
        print(f"Applied: {args.report}")
    else:
        changes = sum(1 for a, b in zip(markdown.splitlines(), rewritten.splitlines()) if a != b)
        print(f"Dry-run: {changes} lines would change")
    return 1 if warnings else 0


if __name__ == "__main__":
    raise SystemExit(main())
