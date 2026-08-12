#!/usr/bin/env python3
"""Semantic fact-check layer for research claims (arXiv 2605.06635 "Cited but Not Verified").

verify_report.py proves citations EXIST and are structurally attached to claims.
It cannot prove the cited source actually SUPPORTS the claim — frontier models
keep links alive in 94%+ of cases while factual accuracy sits at 39-77%.

This script closes that gap with a two-step workflow:

  Step 1 — prepare: generate per-claim fact-check task files:
    python3 scripts/fact_check_claims.py prepare \
        --claims "$RUN/claims.jsonl" \
        --registry "$RUN/source_registry.json" \
        --out "$RUN/fact_check/"

    Creates $OUT/tasks/C{id}.json for every claim that has evidence sources,
    plus $OUT/manifest.json listing the URLs whose content the judge must fetch.

  Step 2 — judge (orchestrator/subagent work, LLM-as-a-judge):
    For each task, fetch the evidence URL content, then answer with a verdict:
      supported   — the page content directly supports the claim
      refuted     — the page content contradicts the claim
      not_found   — the page does not address the claim at all
    Write verdicts as $OUT/verdicts/C{id}.json (schema below).

  Step 3 — collect: aggregate verdicts into a machine-checkable summary:
    python3 scripts/fact_check_claims.py collect \
        --claims "$RUN/claims.jsonl" \
        --verdicts "$RUN/fact_check/verdicts/" \
        --out "$RUN/claim_verification.json"

    Exit codes: 0 = all claims supported; 1 = at least one refuted/not_found
    or a task missing its verdict; 2 = usage error.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from io_utils import atomic_write_json, utc_now
from source_registry import load_registry

SUPPORTED = "supported"
REFUTED = "refuted"
NOT_FOUND = "not_found"
VERDICTS = {SUPPORTED, REFUTED, NOT_FOUND}
NUMERIC_MATCHES = {"match", "mismatch", "none"}

JUDGE_PROMPT = """You are a fact-check judge. Decide whether the cited source actually supports the claim.

CLAIM: {claim}

SOURCE URL: {url}
SOURCE TITLE: {title}

RULES:
- supported: the page content directly states or clearly implies the claim
- refuted: the page content states something that contradicts the claim
- not_found: the page exists but does not address the claim (or is a search page, login wall, or unrelated content)
- A generic page about the topic is NOT enough: the claim must be findable in THIS source.
- If you could not read the page (blocked, timeout, paywall), answer not_found with rationale "unable to read source".

NUMERIC CHECK (verbatim, strict):
The claim may contain numbers (prices, dates, percentages, statistics, versions). The
source MUST carry THE SAME number for the claim to be `supported`. A page that talks
about the topic but gives a different figure, or no figure at all, is NOT `supported`
for that claim — it is `not_found` (if no number) or `refuted` (if a different number).
List every number you found in the source next to the number claimed.

Verdict MUST be exactly one of: supported | refuted | not_found
Answer field `numeric_check` with: {{"match": "match|mismatch|none", "claimed": ["numbers in the claim"], "found": ["numbers actually present in the source"]}}
"""


def load_claims(claims_path: Path) -> list[dict]:
    text = Path(claims_path).read_text(encoding="utf-8")
    # JSONL first (the native claim ledger format)
    claims = []
    is_jsonl = False
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "_meta" in item:
            continue
        claims.append(item)
        is_jsonl = True
    if is_jsonl and claims:
        return claims
    # fallback: single JSON array/dict
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return claims
    if isinstance(data, dict):
        return data.get("claims", [])
    return data if isinstance(data, list) else claims


def _evidence_source_ids(claim: dict) -> list[str]:
    return [e.get("source_id") for e in claim.get("evidence", []) if isinstance(e, dict) and e.get("source_id")]


def _claimed_numbers(claim: dict) -> list[str]:
    """Mechanical extraction of numbers from the claim text (verbatim check anchor)."""
    import re as _re
    text = claim.get("claim", "") or ""
    found: list[str] = []
    for match in _re.finditer(r"\d+(?:[.,]\d+)?", text):
        found.append(match.group(0).replace(",", ""))
    return found


def prepare(claims_path: Path, registry_path: Path, out: Path) -> int:
    claims = load_claims(claims_path)
    registry = load_registry(registry_path)
    sources = {s["id"]: s for s in registry.get("sources", [])}
    tasks_dir = out / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)

    tasks: list[dict] = []
    for claim in claims:
        cid = claim.get("id")
        if not cid:
            continue
        source_ids = _evidence_source_ids(claim)
        if not source_ids:
            continue
        task = {
            "claim_id": cid,
            "claim": claim.get("claim", ""),
            "confidence": claim.get("confidence", "unknown"),
            "importance": claim.get("importance", "unknown"),
            "claimed_numbers": _claimed_numbers(claim),
            "evidence_sources": [],
            "generated_at": utc_now(),
            "judge_prompt": JUDGE_PROMPT.format(
                claim=claim.get("claim", ""),
                url="",
                title="",
            ).strip(),
        }
        for sid in source_ids:
            src = sources.get(sid)
            if not src:
                continue
            task["evidence_sources"].append({
                "source_id": sid,
                "url": src.get("canonical_url") or src.get("url", ""),
                "title": src.get("title", ""),
            })
        if not task["evidence_sources"]:
            continue
        tasks.append(task)
        atomic_write_json(tasks_dir / f"{cid}.json", task)

    manifest = {
        "generated_at": utc_now(),
        "task_count": len(tasks),
        "urls": sorted({u["url"] for t in tasks for u in t["evidence_sources"]}),
        "output_dir": str(out),
        "verdict_schema": {
            "claim_id": "str — matches task claim_id",
            "verdict": "supported | refuted | not_found",
            "rationale": "str — 1-3 sentences; for refuted, quote what the source actually says",
            "evidence_source_id": "str — which evidence source the verdict applies to",
            "numeric_check": "dict — {match: match|mismatch|none, claimed: [numbers in claim], found: [numbers in source]}",
            "checked_at": "ISO-8601",
        },
    }
    atomic_write_json(out / "manifest.json", manifest)
    print(f"Fact-check tasks: {len(tasks)} claims → {tasks_dir}/")
    print(f"URLs to fetch: {len(manifest['urls'])}")
    return 0


def collect(claims_path: Path, verdicts_dir: Path, out: Path) -> int:
    claims = load_claims(claims_path)
    tasks = {c.get("id"): c for c in claims if c.get("id")}
    verdicts_dir = Path(verdicts_dir)
    if not verdicts_dir.is_dir():
        print(f"ERROR: verdicts dir not found: {verdicts_dir}", file=sys.stderr)
        return 2

    results: dict[str, dict] = {}
    problems: list[str] = []
    verdict_files = sorted(verdicts_dir.glob("C*.json"))
    for vf in verdict_files:
        try:
            verdict = json.loads(vf.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{vf.name}: invalid JSON ({exc})")
            continue
        cid = verdict.get("claim_id")
        v = verdict.get("verdict")
        if cid not in tasks:
            problems.append(f"{vf.name}: unknown claim_id {cid}")
            continue
        if v not in VERDICTS:
            problems.append(f"{vf.name}: invalid verdict {v!r}")
            continue
        nc = verdict.get("numeric_check")
        if nc is not None:
            if not isinstance(nc, dict) or nc.get("match") not in NUMERIC_MATCHES:
                problems.append(f"{vf.name}: invalid numeric_check {nc!r}")
                continue
        results[cid] = verdict

    summary = {
        "generated_at": utc_now(),
        "total_claims_with_evidence": len(tasks),
        "verdicts": len(results),
        "supported": sum(1 for r in results.values() if r.get("verdict") == SUPPORTED),
        "refuted": sum(1 for r in results.values() if r.get("verdict") == REFUTED),
        "not_found": sum(1 for r in results.values() if r.get("verdict") == NOT_FOUND),
        "numeric_precision": _numeric_precision(results, tasks),
        "missing_verdicts": [cid for cid in tasks if cid not in results],
        "problems": problems,
        "verdicts_detail": results,
    }
    atomic_write_json(out, summary)

    print(f"Fact-check summary: {summary['supported']} supported / "
          f"{summary['refuted']} refuted / {summary['not_found']} not_found "
          f"({summary['verdicts']}/{summary['total_claims_with_evidence']} verdicts)")
    np_ = summary["numeric_precision"]
    print(f"  numeric_precision: {np_['exact']}/{np_['claims_with_numbers']} claims with numbers "
          f"match their source (rate {np_['rate']})")
    if summary["missing_verdicts"]:
        print(f"MISSING verdicts: {summary['missing_verdicts']}", file=sys.stderr)
    for cid, verdict in results.items():
        if verdict.get("verdict") != SUPPORTED:
            print(f"  {cid}: {verdict.get('verdict')} — {verdict.get('rationale', '')[:120]}", file=sys.stderr)

    return 1 if (summary["refuted"] or summary["not_found"] or summary["missing_verdicts"] or problems) else 0


def _numeric_precision(results: dict[str, dict], tasks: dict[str, dict]) -> dict:
    """Verbatim numeric check: of the claims whose text carries numbers, how many
    verdicts confirm the SAME number appears in the source (numeric_check.match)."""
    claims_with_numbers = 0
    exact = 0
    for cid, task in tasks.items():
        if task.get("claimed_numbers"):
            claims_with_numbers += 1
    for cid, verdict in results.items():
        nc = verdict.get("numeric_check")
        if not isinstance(nc, dict):
            continue
        if nc.get("match") == "match":
            exact += 1
    return {
        "claims_with_numbers": claims_with_numbers,
        "exact": exact,
        "rate": round(exact / claims_with_numbers, 3) if claims_with_numbers else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_prep = sub.add_parser("prepare")
    p_prep.add_argument("--claims", type=Path, required=True)
    p_prep.add_argument("--registry", type=Path, required=True)
    p_prep.add_argument("--out", type=Path, required=True)

    p_col = sub.add_parser("collect")
    p_col.add_argument("--claims", type=Path, required=True)
    p_col.add_argument("--verdicts", type=Path, required=True)
    p_col.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "prepare":
        return prepare(args.claims, args.registry, args.out)
    return collect(args.claims, args.verdicts, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
