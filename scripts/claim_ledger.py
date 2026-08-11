#!/usr/bin/env python3
"""Immutable JSONL claim ledger linking report claims to evidence."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from io_utils import atomic_write_text, digest_object, file_lock, utc_now

VERSION = 1

def ledger_digest(data: dict) -> str:
    return digest_object({'version': data['meta'].get('version', VERSION), 'claims': data['claims']})

def verify_ledger_integrity(data: dict) -> bool:
    expected = data['meta'].get('ledger_sha256')
    return bool(expected) and expected == ledger_digest(data)



def _serialize(meta: dict, claims: list[dict]) -> str:
    lines = [json.dumps({'_meta': meta}, ensure_ascii=False, sort_keys=True)]
    lines.extend(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in claims)
    return '\n'.join(lines) + '\n'


def init_ledger(path: Path) -> dict:
    meta = {'version': VERSION, 'frozen': False, 'created_at': utc_now()}
    atomic_write_text(Path(path), _serialize(meta, []))
    return {'meta': meta, 'claims': []}


def load_ledger(path: Path) -> dict:
    meta: dict = {'version': VERSION, 'frozen': False}
    claims: list[dict] = []
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if '_meta' in item:
            meta = item['_meta']
        else:
            claims.append(item)
    return {'meta': meta, 'claims': claims}


def add_claim(
    path: Path,
    *,
    claim: str,
    claim_class: str,
    importance: str,
    evidence: list[dict],
    confidence: str,
    verification: str,
    contradicting_evidence: list[dict] | None = None,
) -> dict:
    path = Path(path)
    with file_lock(path):
        data = load_ledger(path)
        if data['meta'].get('frozen'):
            raise RuntimeError('claim ledger is frozen')
        item = {
            'id': f"C{len(data['claims']) + 1}",
            'claim': claim,
            'claim_class': claim_class,
            'importance': importance,
            'evidence': evidence,
            'contradicting_evidence': contradicting_evidence or [],
            'confidence': confidence,
            'verification': verification,
        }
        data['claims'].append(item)
        atomic_write_text(path, _serialize(data['meta'], data['claims']))
        return item


def update_claim(path: Path, claim_id: str, **updates) -> dict:
    path = Path(path)
    allowed = {'claim','claim_class','importance','evidence','contradicting_evidence','confidence','verification'}
    unknown = set(updates) - allowed
    if unknown:
        raise ValueError(f"unsupported claim fields: {sorted(unknown)}")
    with file_lock(path):
        data = load_ledger(path)
        if data['meta'].get('frozen'):
            raise RuntimeError('claim ledger is frozen')
        for item in data['claims']:
            if item.get('id') == claim_id:
                item.update(updates)
                atomic_write_text(path, _serialize(data['meta'], data['claims']))
                return item
        raise KeyError(claim_id)

def freeze_ledger(path: Path) -> dict:
    path = Path(path)
    with file_lock(path):
        data = load_ledger(path)
        if data['meta'].get('frozen'):
            return data
        data['meta']['frozen'] = True
        data['meta']['frozen_at'] = utc_now()
        data['meta']['ledger_sha256'] = ledger_digest(data)
        atomic_write_text(path, _serialize(data['meta'], data['claims']))
        return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p_init = sub.add_parser('init'); p_init.add_argument('path', type=Path)
    p_add = sub.add_parser('add'); p_add.add_argument('path', type=Path); p_add.add_argument('--claim', required=True); p_add.add_argument('--claim-class', required=True); p_add.add_argument('--importance', choices=['low','medium','high','critical'], required=True); p_add.add_argument('--source-id', action='append', default=[]); p_add.add_argument('--confidence', choices=['low','medium','high'], default='medium'); p_add.add_argument('--verification', default='unverified'); p_add.add_argument('--evidence-json', action='append', default=[]); p_add.add_argument('--contradiction-json', action='append', default=[])
    p_update = sub.add_parser('update'); p_update.add_argument('path', type=Path); p_update.add_argument('claim_id'); p_update.add_argument('--verification'); p_update.add_argument('--confidence'); p_update.add_argument('--importance')
    p_freeze = sub.add_parser('freeze'); p_freeze.add_argument('path', type=Path)
    p_status = sub.add_parser('status'); p_status.add_argument('path', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'init': result = init_ledger(args.path)
    elif args.command == 'add':
        evidence=[{'source_id': sid, 'support': 'direct'} for sid in args.source_id] + [json.loads(item) for item in args.evidence_json]
        contradictions=[json.loads(item) for item in args.contradiction_json]
        result = add_claim(args.path, claim=args.claim, claim_class=args.claim_class, importance=args.importance, evidence=evidence, confidence=args.confidence, verification=args.verification, contradicting_evidence=contradictions)
    elif args.command == 'update':
        updates={k:v for k,v in {'verification':args.verification,'confidence':args.confidence,'importance':args.importance}.items() if v is not None}
        result=update_claim(args.path,args.claim_id,**updates)
    elif args.command == 'freeze': result = freeze_ledger(args.path)
    else: result = load_ledger(args.path)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
