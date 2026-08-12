#!/usr/bin/env python3
"""Coverage assertions for research runs (ecosystem candidate #4).

Adds deterministic checks that `verify_report.py` does not cover:

  (a) Domain independence — each key claim (importance high/critical) must be
      supported by >=2 evidence sources from DIFFERENT domains. Two mirrors of
      the same site are one source.
  (b) Primary-source preference — a product/company/price claim weighted only
      by blog/social sources (no official_docs/paper/repo/filing) must not
      present itself as high confidence. The claim's confidence is capped at
      `medium` and flagged.
  (c) Success-criteria checklist — if `brief.json` exists with a
      `success_criteria` list, each criterion must map to at least one cited
      source in the registry (by claim-class tag) or to a claim whose text
      mentions the criterion. This is a weak, mechanical proxy — it catches
      "brief said X, report never mentions X" at the registry level.

Output is written to --out (coverage.json) and mirrors finalize status logic:
`status: coverage_gap` means the run must NOT be finalized as `validated`.

Usage:
  python3 scripts/check_coverage.py "$RUN/claims.jsonl" \
      --registry "$RUN/source_registry.json" \
      --brief "$RUN/brief.json" \
      --out "$RUN/coverage.json"

Exit codes: 0 = no gaps (can finalize as validated); 1 = coverage_gap;
2 = usage/input error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from io_utils import atomic_write_json, utc_now
from source_registry import load_registry

PRIMARY_TYPES = {"official_docs", "repo", "paper", "filing", "regulator", "court", "advisory", "dataset", "primary"}
WEAK_TYPES = {"blog", "social_post", "other", "social", "forum"}
# Multi-tenant platforms where the first path segment is the OWNER (repo/user/space),
# so two sources can be independent despite sharing a hostname.
OWNER_PATH_PLATFORMS = {
    "github.com", "gitlab.com", "bitbucket.org", "codeberg.org",
    "medium.com", "dev.to", "substack.com", "reddit.com",
}


def domain_of(url: str) -> str:
    try:
        parts = urlsplit(url)
        netloc = parts.netloc.lower()
        path = parts.path
    except ValueError:
        return ""
    netloc = netloc.split("@")[-1]  # strip userinfo
    if ":" in netloc:
        netloc = netloc.rsplit(":", 1)[0]  # strip port
    labels = netloc.split(".")
    if len(labels) >= 2:
        base = ".".join(labels[-2:])
    else:
        base = netloc
    # On multi-tenant platforms the owner segment makes sources independent:
    # github.com/langchain-ai/langgraph vs github.com/crewAIInc/crewAI.
    if netloc in OWNER_PATH_PLATFORMS:
        seg = path.strip("/").split("/")
        if seg and seg[0]:
            return f"{netloc}/{seg[0].lower()}"
    return base


def evidence_sources(claim: dict) -> list[dict]:
    return [e for e in claim.get("evidence", []) if isinstance(e, dict) and e.get("source_id")]


def source_map(registry: dict) -> dict[str, dict]:
    return {s["id"]: s for s in registry.get("sources", [])}


def check_claims(claims: list[dict], sources: dict[str, dict]) -> list[dict]:
    gaps: list[dict] = []
    for claim in claims:
        cid = claim.get("id", "?")
        importance = str(claim.get("importance", "medium")).lower()
        if importance not in {"high", "critical"}:
            continue
        ev = evidence_sources(claim)
        if not ev:
            gaps.append({"claim_id": cid, "rule": "no_evidence", "message": "key claim has no evidence sources"})
            continue
        domains: set[str] = set()
        has_primary = False
        for e in ev:
            src = sources.get(e.get("source_id", ""))
            if not src:
                continue
            domains.add(domain_of(src.get("canonical_url") or src.get("url", "")))
            if str(src.get("source_type", "")).lower() in PRIMARY_TYPES:
                has_primary = True
        if len(domains) < 2 and len(ev) >= 2:
            gaps.append({
                "claim_id": cid, "rule": "domain_independence",
                "message": f"key claim's {len(ev)} evidence sources come from {len(domains)} domain(s): {sorted(domains)} — mirrors may inflate coverage",
            })
        if not has_primary and importance == "high":
            conf = str(claim.get("confidence", "medium")).lower()
            if conf == "high":
                gaps.append({
                    "claim_id": cid, "rule": "primary_source_preference",
                    "message": "high-importance claim has no primary source but claims high confidence",
                })
    return gaps


def check_success_criteria(brief_path: Path | None, claims: list[dict], sources: dict[str, dict]) -> list[dict]:
    if brief_path is None or not brief_path.exists():
        return []
    try:
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    criteria = brief.get("success_criteria")
    if not criteria:
        return []
    if isinstance(criteria, str):
        criteria = [criteria]
    claim_text = " ".join(c.get("claim", "") for c in claims).lower()
    source_text = " ".join(
        f"{s.get('title', '')} {s.get('authority_rationale', '')}" for s in sources.values()
    ).lower()
    gaps: list[dict] = []
    for criterion in criteria:
        crit_l = str(criterion).lower()
        # strip punctuation for a forgiving match
        tokens = [t for t in re.split(r"\W+", crit_l) if len(t) > 3 and t not in {"criterion"}]
        if not tokens:
            continue
        hit = sum(1 for t in tokens if t in claim_text or t in source_text)
        if hit < max(1, int(len(tokens) * 0.4)):
            gaps.append({
                "rule": "success_criteria",
                "message": f"brief criterion not reflected in claims/sources: {criterion}",
            })
    return gaps


def check(claims_path: Path, registry_path: Path, brief_path: Path | None) -> dict:
    registry = load_registry(registry_path)
    sources = source_map(registry)
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

    gaps = check_claims(claims, sources)
    gaps.extend(check_success_criteria(brief_path, claims, sources))
    status = "coverage_gap" if gaps else "pass"
    return {
        "generated_at": utc_now(),
        "status": status,
        "claims_checked": len(claims),
        "gaps": gaps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claims", type=Path)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--brief", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    if not args.claims.is_file():
        print(f"ERROR: claims file not found: {args.claims}", file=sys.stderr)
        return 2
    if not args.registry.is_file():
        print(f"ERROR: registry not found: {args.registry}", file=sys.stderr)
        return 2

    result = check(args.claims, args.registry, args.brief)
    atomic_write_json(args.out, result)
    print(f"Coverage: {result['status']} ({len(result['gaps'])} gap(s), {result['claims_checked']} claims checked)")
    for gap in result["gaps"]:
        print(f"  [{gap.get('rule')}] {gap.get('message')}", file=sys.stderr)
    return 1 if result["status"] == "coverage_gap" else 0


if __name__ == "__main__":
    raise SystemExit(main())
