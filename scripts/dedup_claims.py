#!/usr/bin/env python3
"""Deterministic claim deduplication for research runs.

The registry dedupes URLs, not content. Two claims from different URLs can
carry the same fact (same numbers, same conclusion — often syndicated news or
mirror posts). This script mechanically catches ~80% of those duplicates
BEFORE the LLM does anything:

  - same normalized claim text (lowercase, punctuation stripped)
  - same extracted numbers (prices, stats, dates) AND overlapping evidence
    source sets — the "same number from the same sources" signal
  - high source-set overlap (>=2 of 3 evidence sources shared) for
    high-importance claims

Paraphrase-level duplicates that share no numbers are left to the LLM dedup
step (Gap Check); this script only flags mechanical duplicates.

Usage:
  python3 scripts/dedup_claims.py "$RUN/claims.jsonl" \
      --registry "$RUN/source_registry.json" \
      --out "$RUN/dedup.json"

Exit codes: 0 = run ok (duplicates may still be found — that is not a failure);
2 = usage/input error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from io_utils import atomic_write_json, utc_now
from source_registry import load_registry

NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")
_PUNCT_RE = re.compile(r"[^\w\s%$€£-]")
_WS_RE = re.compile(r"\s+")


def extract_numbers(text: str) -> set[str]:
    """Return normalized numeric tokens (e.g. '28,929' -> '28929'; '28.9k' -> '28.9')."""
    tokens: set[str] = set()
    for match in NUMBER_RE.finditer(text):
        raw = match.group(0)
        tokens.add(raw.replace(",", "").replace(" ", ""))
    for match in re.finditer(r"\d+(?:[.,]\d+)?\s?[kKmMмМ]%?", text):
        tokens.add(match.group(0).lower().replace(" ", ""))
    return tokens


def normalize_text(text: str) -> str:
    return _WS_RE.sub(" ", _PUNCT_RE.sub(" ", text.lower())).strip()


def source_set(claim: dict) -> set[str]:
    return {e.get("source_id") for e in claim.get("evidence", []) if isinstance(e, dict) and e.get("source_id")}


def authority_weight(claim: dict, registry: dict) -> float:
    """Sum of registry authority weights of a claim's evidence sources."""
    types = {s["id"]: s.get("source_type", "").lower() for s in registry.get("sources", [])}
    weights = {
        "official_docs": 1.0, "news": 0.7, "analysis": 0.6, "paper": 0.7,
        "repo": 0.6, "filing": 1.0, "regulator": 1.0, "court": 1.0,
        "blog": 0.4, "social_post": 0.3, "other": 0.3, "primary": 1.0,
    }
    total = 0.0
    for sid in source_set(claim):
        total += weights.get(types.get(sid, "other"), 0.3)
    return total


def is_duplicate(a: dict, b: dict, registry: dict, min_source_overlap: int = 2) -> tuple[bool, str]:
    """Mechanical duplicate test between two claims. Returns (is_dup, reason)."""
    na, nb = normalize_text(a.get("claim", "")), normalize_text(b.get("claim", ""))
    sa, sb = source_set(a), source_set(b)
    if not sa or not sb:
        return False, "missing evidence"

    # 1. identical normalized text
    if na and na == nb:
        return True, "identical normalized claim text"

    nums_a, nums_b = extract_numbers(a.get("claim", "")), extract_numbers(b.get("claim", ""))
    shared_nums = nums_a & nums_b
    shared_sources = sa & sb
    overlap_ratio = len(shared_sources) / max(1, min(len(sa), len(sb)))

    # 2. same numbers + overlapping sources (syndicated news / same stat)
    if shared_nums and overlap_ratio >= 0.5:
        return True, f"same numbers {sorted(shared_nums)[:5]} + source overlap {overlap_ratio:.0%}"

    # 3. heavy source-set overlap on a high-importance claim (mirror coverage)
    imp = str(a.get("importance", "medium")).lower()
    if imp in {"high", "critical"} and len(shared_sources) >= min_source_overlap and overlap_ratio >= 0.66:
        return True, f"high-importance claim sharing {len(shared_sources)} evidence sources"

    return False, "no mechanical overlap"


def dedup(claims_path: Path, registry_path: Path) -> dict:
    registry = load_registry(registry_path)
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

    dups: list[dict] = []
    kept_ids = {c["id"] for c in claims}
    for i, a in enumerate(claims):
        if a["id"] not in kept_ids:
            continue
        for b in claims[i + 1 :]:
            if b["id"] not in kept_ids:
                continue
            is_dup, reason = is_duplicate(a, b, registry)
            if not is_dup:
                continue
            # keep the stronger claim, drop the other
            wa, wb = authority_weight(a, registry), authority_weight(b, registry)
            if wb > wa:
                kept, dropped = b, a
            elif wa > wb:
                kept, dropped = a, b
            else:
                # equal weight: keep the more recent claim (higher C number = later)
                kept, dropped = (b, a) if b["id"] > a["id"] else (a, b)
            dups.append({
                "kept": kept["id"], "dropped": dropped["id"],
                "reason": reason,
                "kept_weight": round(wa, 3) if kept is a else round(wb, 3),
                "dropped_weight": round(wb, 3) if kept is a else round(wa, 3),
            })
            kept_ids.discard(dropped["id"])

    result = {
        "generated_at": utc_now(),
        "claims_checked": len(claims),
        "duplicates_found": len(dups),
        "duplicates": dups,
        "kept_ids": sorted(kept_ids),
        "note": "Paraphrase-level duplicates (no shared numbers) are NOT flagged here — handled by LLM Gap Check.",
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("claims", type=Path)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    if not args.claims.is_file():
        print(f"ERROR: claims file not found: {args.claims}", file=sys.stderr)
        return 2
    if not args.registry.is_file():
        print(f"ERROR: registry not found: {args.registry}", file=sys.stderr)
        return 2

    result = dedup(args.claims, args.registry)
    atomic_write_json(args.out, result)
    print(f"Dedup: {result['duplicates_found']} duplicates of {result['claims_checked']} claims → {args.out}")
    for dup in result["duplicates"]:
        print(f"  {dup['dropped']} DUP of {dup['kept']} — {dup['reason']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
