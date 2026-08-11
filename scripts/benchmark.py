#!/usr/bin/env python3
"""Aggregate reproducible quality/cost metrics from stored v6 research runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import fmean

from claim_ledger import load_ledger
from report_model import is_exempt_block, parse_frontmatter, scan_narrative_blocks, split_sources

PRIMARY_TYPES = {'official_docs','repo','paper','filing','regulator','court','advisory','dataset','primary'}


def _json(path: Path, default):
    try: return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError: return default


def score_run(run_dir: Path) -> dict[str, float | int | str]:
    run_dir=Path(run_dir)
    manifest=_json(run_dir/'report_manifest.json',{})
    registry=_json(run_dir/'source_registry.json',{'sources':[]})
    state=_json(run_dir/'state.json',{'budget':{}})
    access=_json(run_dir/'source_access.json',{'sources':{}})
    ledger=load_ledger(run_dir/'claims.jsonl') if (run_dir/'claims.jsonl').exists() else {'claims':[]}
    report_text=(run_dir/'report.md').read_text(encoding='utf-8') if (run_dir/'report.md').exists() else ''
    _,body=parse_frontmatter(report_text); narrative,_=split_sources(body)
    blocks=[b for b in scan_narrative_blocks(narrative) if not is_exempt_block(b)]
    citation_coverage=(sum(bool(b.source_ids) for b in blocks)/len(blocks)) if blocks else 1.0
    claim_coverage=(sum(bool(b.claim_ids) for b in blocks)/len(blocks)) if blocks else 1.0
    sources=registry.get('sources',[])
    primary_ratio=(sum(str(s.get('source_type','')).lower() in PRIMARY_TYPES for s in sources)/len(sources)) if sources else 0.0
    access_items=list(access.get('sources',{}).values())
    access_health=(sum(item.get('status')=='ok' for item in access_items)/len(access_items)) if access_items else 0.0
    budget=state.get('budget',{})
    utilizations=[]
    for counter,limit in [('query_calls','query_limit'),('fetch_calls','fetch_limit'),('investigator_calls','investigator_limit')]:
        if budget.get(limit): utilizations.append(float(budget.get(counter,0))/float(budget[limit]))
    budget_util=max(utilizations) if utilizations else 0.0
    unresolved_critical=sum(1 for c in ledger.get('claims',[]) if str(c.get('importance','')).lower()=='critical' and c.get('verification')!='supported')
    evaluation=manifest.get('evaluation',{}) if isinstance(manifest.get('evaluation',{}),dict) else {}
    result: dict[str,float|int|str]={
        'run': str(run_dir),
        'validated': 1.0 if manifest.get('status')=='validated' else 0.0,
        'semantic_pass': 1.0 if manifest.get('semantic_verification')=='passed' else 0.0,
        'structural_pass': 1.0 if manifest.get('structural_validation')=='passed' else 0.0,
        'citation_coverage': round(citation_coverage,6),
        'claim_marker_coverage': round(claim_coverage,6),
        'primary_source_ratio': round(primary_ratio,6),
        'source_access_health': round(access_health,6),
        'budget_utilization': round(budget_util,6),
        'unresolved_critical_claims': unresolved_critical,
    }
    for key in ('factual_precision','completeness','citation_precision'):
        if isinstance(evaluation.get(key),(int,float)): result[key]=float(evaluation[key])
    return result


def aggregate_runs(run_dirs: list[Path]) -> dict[str,float|int]:
    scores=[score_run(path) for path in run_dirs]
    if not scores: return {'runs':0}
    numeric_keys=sorted(set.intersection(*[{k for k,v in s.items() if isinstance(v,(int,float))} for s in scores]))
    result: dict[str,float|int]={'runs':len(scores)}
    for key in numeric_keys:
        result[key]=round(fmean(float(s[key]) for s in scores),6)
    return result


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('runs',nargs='+',type=Path); parser.add_argument('--json',action='store_true'); args=parser.parse_args(argv)
    result=aggregate_runs(args.runs)
    if args.json: print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
    else:
        for key,value in result.items(): print(f'{key}: {value}')
    return 0
if __name__=='__main__': raise SystemExit(main())
