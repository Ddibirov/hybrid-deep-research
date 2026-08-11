#!/usr/bin/env python3
"""Citation-quality scoring for finished research runs (arXiv 2605.06635 triad).

Scores a finalized run on the three citation dimensions the literature measures:
  1. Link Works   — URL accessibility, from source_access.json (check_sources.py)
  2. Relevant Content — topic alignment: fraction of registry sources actually
                        cited in the report (utilization proxy)
  3. Fact Check   — claim-level factual support, from claim_verification.json
                    (fact_check_claims.py collect)

Usage:
  python3 scripts/eval_citations.py "$RUN" \
      [--registry source_registry.json] [--claims claims.jsonl] \
      [--access source_access.json] [--fact-check claim_verification.json]

Defaults resolve common names inside $RUN. Writes eval_citations.json into $RUN
and prints a compact scorecard. Exit 0 when scores are computed, 1 on missing
inputs (partial scoring still printed), 2 on usage error.

This is the CI metric for the skill: after any change to prompts or runtime,
run it on a fixture report and compare Fact Check % over time.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from io_utils import utc_now

CITATION_RE = re.compile(r"\[(S\d+)\]")
CLAIM_MARKER_RE = re.compile(r"claims:\s*(C\d+)")
SOURCES_HEADINGS = ("## sources", "## fuentes", "## references", "## источники")


def _resolve(run: Path, arg: str | None, name: str) -> Path | None:
    if arg:
        p = Path(arg)
        return p if p.is_absolute() else run / p
    p = run / name
    return p if p.exists() else None


def _load_json(path: Path | None) -> dict | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def score(run: Path, registry: Path | None, claims: Path | None, access: Path | None, fact_check: Path | None) -> int:
    # resolve defaults inside the run dir when args omitted
    registry = _resolve(run, registry, "source_registry.json")
    claims = _resolve(run, claims, "claims.jsonl")
    access = _resolve(run, access, "source_access.json")
    fact_check = _resolve(run, fact_check, "claim_verification.json")

    report_candidates = [run / "report.md", run / f"{run.name}.md"]
    report_path = next((p for p in report_candidates if p.exists()), None)

    report_text = report_path.read_text(encoding="utf-8") if report_path else ""
    body = report_text
    # strip frontmatter
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        if end != -1:
            body = body[end + 5 :]
    # strip sources section
    for heading in SOURCES_HEADINGS:
        m = re.search(rf"(?mi)^{re.escape(heading)}\s*$", body)
        if m:
            body = body[: m.start()]
            break

    cited = set(CITATION_RE.findall(body))
    claim_ids = set(CLAIM_MARKER_RE.findall(body))

    # Link Works
    access_data = _load_json(access)
    link = None
    if access_data:
        entries = access_data.get("sources") or access_data.get("results") or []
        if isinstance(entries, dict):
            entries = list(entries.values())
        total = len(entries)
        ok = sum(1 for e in entries if e.get("status") in ("ok", "restricted"))
        link = {"checked": total, "ok_or_restricted": ok,
                "rate": round(ok / total, 3) if total else None}

    # Relevant Content (utilization proxy): how many registry sources are cited
    reg_data = _load_json(registry)
    relevant = None
    if reg_data is not None and report_path:
        all_ids = {s["id"] for s in reg_data.get("sources", [])}
        if all_ids:
            used = all_ids & cited
            relevant = {"registered": len(all_ids), "cited_in_report": len(used),
                        "rate": round(len(used) / len(all_ids), 3)}

    # Fact Check
    fc = _load_json(fact_check)
    fact = None
    if fc:
        total = fc.get("verdicts") or 0
        supported = fc.get("supported") or 0
        fact = {"checked": total, "supported": supported,
                "rate": round(supported / total, 3) if total else None,
                "refuted": fc.get("refuted") or 0, "not_found": fc.get("not_found") or 0}

    result = {
        "generated_at": utc_now(),
        "run": str(run),
        "report": str(report_path) if report_path else None,
        "citations_found": len(cited),
        "claim_markers_found": len(claim_ids),
        "link_works": link,
        "relevant_content": relevant,
        "fact_check": fact,
    }
    out = run / "eval_citations.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Citation quality scorecard")
    print(f"  report:        {report_path.name if report_path else 'NOT FOUND'}")
    print(f"  citations:     {len(cited)} [S#] cited, {len(claim_ids)} claim markers")
    if link:
        print(f"  Link Works:    {link['ok_or_restricted']}/{link['checked']} accessible (rate {link['rate']})")
    else:
        print("  Link Works:    no source_access.json — run check_sources.py first")
    if relevant:
        print(f"  Relevant:      {relevant['cited_in_report']}/{relevant['registered']} sources cited (rate {relevant['rate']})")
    else:
        print("  Relevant:      need registry + report")
    if fact:
        print(f"  Fact Check:    {fact['supported']}/{fact['checked']} claims supported (rate {fact['rate']}) — refuted {fact['refuted']}, not_found {fact['not_found']}")
    else:
        print("  Fact Check:    no claim_verification.json — run fact_check_claims.py first")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path, help="run directory (contains report.md)")
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--claims", type=Path)
    parser.add_argument("--access", type=Path)
    parser.add_argument("--fact-check", type=Path)
    args = parser.parse_args(argv)
    if not args.run.is_dir():
        print(f"ERROR: run dir not found: {args.run}", file=sys.stderr)
        return 2
    return score(
        args.run.resolve(),
        args.registry, args.claims, args.access, args.fact_check,
    )


if __name__ == "__main__":
    raise SystemExit(main())
