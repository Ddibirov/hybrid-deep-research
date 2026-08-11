#!/usr/bin/env python3
"""Immutable source registry for research provenance."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from io_utils import atomic_write_json, digest_object, file_lock, normalize_url, sha256_text, utc_now

VERSION = 1

def registry_digest(data: dict) -> str:
    payload = {k: v for k, v in data.items() if k != 'registry_sha256'}
    return digest_object(payload)

def verify_registry_integrity(data: dict) -> bool:
    expected = data.get('registry_sha256')
    return bool(expected) and expected == registry_digest(data)



def init_registry(path: Path) -> dict:
    data = {'version': VERSION, 'frozen': False, 'created_at': utc_now(), 'sources': []}
    atomic_write_json(path, data)
    return data


def load_registry(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding='utf-8'))


def add_source(
    path: Path,
    *,
    title: str,
    url: str,
    source_type: str,
    canonical_url: str | None = None,
    date: str = 'unknown',
    claim_classes: list[str] | None = None,
    authority_rationale: str = '',
    provenance: dict | None = None,
    content: str = '',
    finding: str = '',
) -> dict:
    path = Path(path)
    with file_lock(path):
        data = load_registry(path)
        if data.get('frozen'):
            raise RuntimeError('source registry is frozen')
        target = normalize_url(canonical_url or url)
        for existing in data.get('sources', []):
            if normalize_url(existing.get('canonical_url') or existing['url']) == target:
                return existing
        source = {
            'id': f"S{len(data.get('sources', [])) + 1}",
            'title': title,
            'url': url,
            'canonical_url': canonical_url or url,
            'date': date,
            'source_type': source_type,
            'claim_classes': claim_classes or [],
            'authority_rationale': authority_rationale,
            'provenance': provenance or {},
            'retrieved_at': utc_now(),
            'content_sha256': sha256_text(content),
            'finding_sha256': sha256_text(finding),
        }
        data.setdefault('sources', []).append(source)
        atomic_write_json(path, data)
        return source


def freeze_registry(path: Path) -> dict:
    path = Path(path)
    with file_lock(path):
        data = load_registry(path)
        if data.get('frozen'):
            return data
        data['frozen'] = True
        data['frozen_at'] = utc_now()
        data['registry_sha256'] = registry_digest(data)
        atomic_write_json(path, data)
        return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p_init = sub.add_parser('init'); p_init.add_argument('path', type=Path)
    p_add = sub.add_parser('add'); p_add.add_argument('path', type=Path); p_add.add_argument('--title', required=True); p_add.add_argument('--url', required=True); p_add.add_argument('--source-type', required=True); p_add.add_argument('--date', default='unknown'); p_add.add_argument('--claim-class', action='append', default=[]); p_add.add_argument('--authority-rationale', default=''); p_add.add_argument('--content-file', type=Path); p_add.add_argument('--finding-file', type=Path)
    p_freeze = sub.add_parser('freeze'); p_freeze.add_argument('path', type=Path)
    p_status = sub.add_parser('status'); p_status.add_argument('path', type=Path)
    args = parser.parse_args(argv)
    if args.command == 'init': result = init_registry(args.path)
    elif args.command == 'add':
        content = ''
        if args.content_file:
            try:
                content = args.content_file.read_text(encoding='utf-8')
            except OSError:
                print(f"WARNING: content file {args.content_file} not found; stored empty", file=sys.stderr)
        finding = ''
        if args.finding_file:
            try:
                finding = args.finding_file.read_text(encoding='utf-8')
            except OSError:
                print(f"WARNING: finding file {args.finding_file} not found; stored empty", file=sys.stderr)
        result = add_source(args.path, title=args.title, url=args.url, source_type=args.source_type, date=args.date, claim_classes=args.claim_class, authority_rationale=args.authority_rationale, content=content, finding=finding)
    elif args.command == 'freeze': result = freeze_registry(args.path)
    else: result = load_registry(args.path)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
