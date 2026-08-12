#!/usr/bin/env python3
"""Structured human escalation for unresolved research claims.

Machine-readable escalation file (escalations.json) replacing prose-only
blocks. Built from the fact-check verdicts + the frozen claim ledger.

A claim becomes an escalation when it reaches the final stage with an
unresolved problem:
  - refuted  — source contradicts the claim
  - not_found — evidence does not address the claim
  - numeric mismatch — claimed number does not appear in the source
  - low confidence (no escalation by itself, but recorded for the manual
    review block in the report)

The deterministic rule (v4.8.0): if any `refuted` claim survives to the final
report, the run MUST be `status: needs_review` — `validated` is forbidden.
`finalize_report.py` enforces this by reading escalations.json.

Usage:
  python3 scripts/escalations.py "$RUN/claims.jsonl" \
      --registry "$RUN/source_registry.json" \
      --fact-check "$RUN/claim_verification.json" \
      --out "$RUN/escalations.json"

Exit codes: 0 = written (may contain escalations); 2 = usage/input error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from io_utils import atomic_write_json, utc_now
from source_registry import load_registry

ACTIONS = ("re-anchor", "drop", "keep-with-caveat")


def _load_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build(
    claims_path: Path,
    registry_path: Path,
    fact_check_path: Path | None,
) -> dict:
    registry = load_registry(registry_path)
    sources = {s["id"]: s for s in registry.get("sources", [])}

    claims: list[dict] = []
    for line in Path(claims_path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "_meta" not in item and item.get("id"):
            claims.append(item)
    by_id = {c["id"]: c for c in claims}

    verdicts: dict[str, dict] = {}
    if fact_check_path is not None and fact_check_path.exists():
        fc = _load_json(fact_check_path) or {}
        verdicts = fc.get("verdicts_detail") or {}

    escalations: list[dict] = []
    for cid, claim in by_id.items():
        verdict = verdicts.get(cid) or {}
        v = verdict.get("verdict")
        nc = verdict.get("numeric_check") or {}
        reasons: list[str] = []
        if v == "refuted":
            reasons.append("refuted")
        if v == "not_found":
            reasons.append("not_found")
        if nc.get("match") == "mismatch":
            reasons.append("numeric_mismatch")
        if str(claim.get("confidence", "medium")).lower() == "low":
            reasons.append("low_confidence")
        if not reasons:
            continue

        # recommended action
        action = "keep-with-caveat"
        if "refuted" in reasons or "numeric_mismatch" in reasons:
            action = "re-anchor"
        conflicting = []
        for e in claim.get("evidence", []):
            sid = e.get("source_id") if isinstance(e, dict) else None
            if sid and sid in sources:
                conflicting.append(sid)

        escalations.append({
            "claim_id": cid,
            "verdict": v or "unknown",
            "reasons": reasons,
            "conflicting_sources": conflicting,
            "recommended_action": action,
            "recommended_actions": [a for a in ACTIONS if a != action] or ACTIONS,
            "claim": claim.get("claim", "")[:300],
        })

    has_refuted = any("refuted" in e["reasons"] or "numeric_mismatch" in e["reasons"] for e in escalations)
    status = "needs_review" if has_refuted else ("review_recommended" if escalations else "clean")
    return {
        "generated_at": utc_now(),
        "status": status,
        "escalations": escalations,
        "rule": "refuted or numeric-mismatch claim in final report ⇒ status: needs_review; validated forbidden (enforced by finalize_report.py)",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claims", type=Path)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--fact-check", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    if not args.claims.is_file():
        print(f"ERROR: claims file not found: {args.claims}", file=sys.stderr)
        return 2
    if not args.registry.is_file():
        print(f"ERROR: registry not found: {args.registry}", file=sys.stderr)
        return 2

    result = build(args.claims, args.registry, args.fact_check)
    atomic_write_json(args.out, result)
    print(f"Escalations: {result['status']} — {len(result['escalations'])} claim(s) need attention → {args.out}")
    for e in result["escalations"]:
        print(f"  {e['claim_id']}: {', '.join(e['reasons'])} → {e['recommended_action']} (sources: {e['conflicting_sources']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
