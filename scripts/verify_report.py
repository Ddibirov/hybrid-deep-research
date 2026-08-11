#!/usr/bin/env python3
"""Deterministic structural validation for Hybrid Deep Research reports."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from report_model import URL_RE, is_exempt_block, parse_frontmatter, parse_sources_section, scan_narrative_blocks, split_sources


def normalize_url(url: str) -> str:
    url = url.rstrip(".,;:")
    parts = urlsplit(url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/") or "/", parts.query, ""))


def load_registry(path: Path) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    sources = data.get("sources")
    if not isinstance(sources, list):
        raise ValueError("registry must contain a 'sources' list")
    registry: dict[str, dict] = {}
    for item in sources:
        source_id = item.get("id")
        url = item.get("url")
        if not isinstance(source_id, str) or not re.fullmatch(r"S\d+", source_id):
            raise ValueError(f"invalid registry source id: {source_id!r}")
        if source_id in registry:
            raise ValueError(f"duplicate registry source id: {source_id}")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise ValueError(f"registry source {source_id} has invalid URL")
        registry[source_id] = item
    return registry


def load_claims(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    claims: dict[str, dict] = {}
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        item = json.loads(line)
        if '_meta' in item:
            continue
        claim_id = item.get("id")
        if not isinstance(claim_id, str) or not re.fullmatch(r"C\d+", claim_id):
            raise ValueError(f"invalid claim id at line {line_no}: {claim_id!r}")
        if claim_id in claims:
            raise ValueError(f"duplicate claim id: {claim_id}")
        claims[claim_id] = item
    return claims


def validate(report_path: Path, registry_path: Path, claims_path: Path | None = None, *, enforce_final_status: bool = True) -> list[str]:
    errors: list[str] = []
    text = report_path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    narrative, sources_text = split_sources(body)

    try:
        registry = load_registry(registry_path)
        claims = load_claims(claims_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        return [f"artifact error: {exc}"]

    source_entries, source_errors = parse_sources_section(sources_text)
    errors.extend(source_errors)
    if not source_entries:
        errors.append("no parseable source entries under a Sources/Fuentes heading")

    unknown_entries = sorted(set(source_entries) - registry.keys())
    if unknown_entries:
        errors.append("source entries absent from registry: " + ", ".join(unknown_entries))
    for source_id, report_url in source_entries.items():
        if source_id in registry and normalize_url(report_url) != normalize_url(registry[source_id]["url"]):
            errors.append(f"source URL mismatch for {source_id}: report={report_url!r}, registry={registry[source_id]['url']!r}")

    cited_ids: set[str] = set()
    used_claim_ids: set[str] = set()
    for block in scan_narrative_blocks(narrative):
        cited_ids.update(block.source_ids)
        used_claim_ids.update(block.claim_ids)
        if is_exempt_block(block):
            continue
        if not block.source_ids:
            errors.append((f"uncited factual prose paragraph near line {block.line}" if block.kind == "prose" else f"{block.kind} block near line {block.line} is missing source citation"))
        if claims_path is not None and not block.claim_ids:
            errors.append(f"{block.kind} block near line {block.line} is missing claim marker")
        unknown_claims = sorted(set(block.claim_ids) - claims.keys()) if claims_path is not None else []
        if unknown_claims:
            errors.append("unknown claim IDs near line %d: %s" % (block.line, ", ".join(unknown_claims)))
        for claim_id in block.claim_ids:
            claim = claims.get(claim_id)
            if not claim:
                continue
            evidence_sources = {
                evidence.get("source_id")
                for evidence in claim.get("evidence", [])
                if isinstance(evidence, dict) and evidence.get("source_id")
            }
            unknown_evidence = sorted(evidence_sources - registry.keys())
            if unknown_evidence:
                errors.append(f"claim {claim_id} evidence references unknown source IDs: {', '.join(unknown_evidence)}")
            if block.source_ids and not (set(block.source_ids) & evidence_sources):
                errors.append(f"claim/source mismatch near line {block.line}: {claim_id} is not supported by cited sources")

    unknown_citations = sorted(cited_ids - registry.keys())
    if unknown_citations:
        errors.append("unknown citation IDs in narrative: " + ", ".join(unknown_citations))
    missing_entries = sorted(cited_ids - source_entries.keys())
    if missing_entries:
        errors.append("cited IDs missing from Sources section: " + ", ".join(missing_entries))

    declared = frontmatter.get("sources_count")
    if declared is None:
        errors.append("frontmatter is missing sources_count")
    else:
        try:
            declared_count = int(declared)
        except ValueError:
            errors.append(f"sources_count is not an integer: {declared!r}")
        else:
            if declared_count != len(source_entries):
                errors.append(f"sources_count mismatch: frontmatter={declared_count}, published={len(source_entries)}")

    narrative_urls = sorted(set(URL_RE.findall(narrative)))
    if narrative_urls:
        errors.append("raw URLs found outside Sources section: " + ", ".join(narrative_urls))

    if enforce_final_status and frontmatter.get("status") in {"confirmed", "validated"}:
        semantic = frontmatter.get("semantic_verification", frontmatter.get("verification"))
        structural = frontmatter.get("structural_validation", frontmatter.get("deterministic_validation"))
        if semantic != "passed":
            errors.append("final status requires semantic verification 'passed'")
        if structural != "passed":
            errors.append(("status is confirmed but deterministic_validation is not 'passed'" if frontmatter.get("status") == "confirmed" else "final status requires structural validation 'passed'"))

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--claims", type=Path)
    args = parser.parse_args(argv)
    errors = validate(args.report, args.registry, args.claims)
    if errors:
        print("VALIDATION: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("VALIDATION: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
