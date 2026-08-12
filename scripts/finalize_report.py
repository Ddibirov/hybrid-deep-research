#!/usr/bin/env python3
"""Finalize v6 reports; only this command may award status=validated."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from claim_ledger import load_ledger, verify_ledger_integrity
from io_utils import atomic_write_json, atomic_write_text, utc_now
from report_model import parse_frontmatter, parse_sources_section, split_sources
from source_registry import load_registry, verify_registry_integrity
from verify_report import validate

FRONTMATTER_ORDER = [
    'status','topic','rounds','sources_count','semantic_verification','structural_validation',
    'coverage','confidence','source_access','registry_sha256','claims_sha256','generated_at','finalized_at'
]


def _rewrite_frontmatter(path: Path, updates: dict[str, object]) -> None:
    text=path.read_text(encoding='utf-8'); current, body=parse_frontmatter(text)
    values={**current, **{k: str(v) for k,v in updates.items()}}
    lines=['---']
    used=set()
    for key in FRONTMATTER_ORDER:
        if key in values:
            lines.append(f'{key}: {values[key]}'); used.add(key)
    for key in sorted(set(values)-used): lines.append(f'{key}: {values[key]}')
    lines.extend(['---', body.lstrip('\n')])
    atomic_write_text(path,'\n'.join(lines).rstrip()+'\n')


def _coverage_and_confidence(claims: list[dict]) -> tuple[str,str]:
    coverage='complete'
    confidence='high'
    for claim in claims:
        importance=str(claim.get('importance','medium')).lower(); verification=str(claim.get('verification','unverified')).lower(); claim_conf=str(claim.get('confidence','medium')).lower()
        if verification not in {'supported','partially_supported'}:
            coverage='partial'
        if importance in {'high','critical'} and verification != 'supported':
            coverage='partial'; confidence='low'
        elif claim_conf == 'low' or verification == 'partially_supported':
            if confidence == 'high': confidence='medium'
    if not claims:
        coverage='partial'; confidence='low'
    return coverage,confidence


def _source_access_status(path: Path | None) -> str:
    if path is None or not path.exists(): return 'unavailable'
    data=json.loads(path.read_text(encoding='utf-8')); statuses=[item.get('status') for item in data.get('sources',{}).values()]
    if not statuses: return 'unavailable'
    return 'complete' if all(status=='ok' for status in statuses) else 'partial'


def finalize(report_path: Path, manifest_path: Path, registry_path: Path, claims_path: Path, *, semantic_verification: str, access_path: Path | None = None, escalations_path: Path | None = None, coverage_path: Path | None = None) -> dict:
    report_path=Path(report_path); manifest_path=Path(manifest_path); registry=load_registry(registry_path); ledger=load_ledger(claims_path)
    if not registry.get('frozen'): raise RuntimeError('source registry must be frozen before finalization')
    if not ledger['meta'].get('frozen'): raise RuntimeError('claim ledger must be frozen before finalization')
    if not verify_registry_integrity(registry): raise RuntimeError('source registry integrity check failed')
    if not verify_ledger_integrity(ledger): raise RuntimeError('claim ledger integrity check failed')

    _, body=parse_frontmatter(report_path.read_text(encoding='utf-8')); _, sources_text=split_sources(body); source_entries,_=parse_sources_section(sources_text)
    coverage,confidence=_coverage_and_confidence(ledger['claims']); access=_source_access_status(access_path)
    preflight={
        'status':'pending','sources_count':len(source_entries),'semantic_verification':semantic_verification,
        'structural_validation':'pending','coverage':coverage,'confidence':confidence,'source_access':access,
        'registry_sha256':registry.get('registry_sha256',''), 'claims_sha256':ledger['meta'].get('ledger_sha256','')
    }
    _rewrite_frontmatter(report_path,preflight)
    errors=validate(report_path,registry_path,claims_path,enforce_final_status=False)
    structural='passed' if not errors else 'failed'
    status='validated' if semantic_verification=='passed' and structural=='passed' and coverage=='complete' else 'unverified_gaps'

    # v4.8.0 escalation rule: a refuted claim surviving to the final report
    # forbids `validated` — the run must be needs_review (human decision).
    if escalations_path is not None and escalations_path.exists():
        try:
            esc=json.loads(escalations_path.read_text(encoding='utf-8'))
            if esc.get('status')=='needs_review':
                status='needs_review'
        except (OSError, json.JSONDecodeError):
            pass

    # v4.8.0 coverage rule: domain-independence / primary-source / success-criteria
    # gaps forbid `validated` — the run must be coverage_gap until fixed.
    if coverage_path is not None and coverage_path.exists():
        try:
            cov=json.loads(coverage_path.read_text(encoding='utf-8'))
            if cov.get('status')=='coverage_gap':
                status='coverage_gap'
        except (OSError, json.JSONDecodeError):
            pass

    manifest={}
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    manifest.update({
        **preflight,'status':status,'structural_validation':structural,'validator_errors':errors,
        'finalized_at':utc_now(),
    })
    atomic_write_json(manifest_path,manifest)
    _rewrite_frontmatter(report_path,{k:v for k,v in manifest.items() if k != 'validator_errors'})
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('report',type=Path); parser.add_argument('--manifest',required=True,type=Path); parser.add_argument('--registry',required=True,type=Path); parser.add_argument('--claims',required=True,type=Path); parser.add_argument('--semantic-verification',required=True,choices=['passed','failed','unavailable']); parser.add_argument('--access',type=Path); parser.add_argument('--escalations',type=Path); parser.add_argument('--coverage',type=Path)
    args=parser.parse_args(argv); result=finalize(args.report,args.manifest,args.registry,args.claims,semantic_verification=args.semantic_verification,access_path=args.access,escalations_path=args.escalations,coverage_path=args.coverage); print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)); return 0 if result['status']=='validated' else 1
if __name__=='__main__': raise SystemExit(main())
