#!/usr/bin/env python3
"""Deterministically classify current HTTP accessibility of frozen registry sources."""
from __future__ import annotations

import argparse
import json
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from io_utils import atomic_write_json, utc_now
from source_registry import load_registry, verify_registry_integrity

USER_AGENT = 'Mozilla/5.0 hybrid-deep-research-v6'


def _status(code: int) -> str:
    if 200 <= code < 400: return 'ok'
    if code in (401, 403): return 'restricted'
    if code in (404, 410): return 'dead'
    if code == 429: return 'rate_limited'
    if 500 <= code < 600: return 'transient_error'
    return 'http_error'


def _request(url: str, method: str, timeout: float) -> dict:
    request = Request(url, method=method, headers={'User-Agent': USER_AGENT, 'Accept': '*/*'})
    try:
        with urlopen(request, timeout=timeout) as response:
            code = int(response.getcode())
            return {'status': _status(code), 'http_code': code, 'final_url': response.geturl(), 'checked_at': utc_now(), 'method': method}
    except HTTPError as exc:
        code = int(exc.code)
        return {'status': _status(code), 'http_code': code, 'final_url': exc.geturl() or url, 'checked_at': utc_now(), 'method': method}
    except (URLError, TimeoutError, socket.timeout, OSError) as exc:
        return {'status': 'network_error', 'http_code': None, 'final_url': url, 'checked_at': utc_now(), 'method': method, 'error': str(exc)}


def classify_url(url: str, timeout: float = 10.0) -> dict:
    result = _request(url, 'HEAD', timeout)
    if result.get('http_code') in (405, 501):
        result = _request(url, 'GET', timeout)
    return result


def check_registry(registry_path: Path, output_path: Path, *, concurrency: int = 4, timeout: float = 10.0) -> dict:
    registry = load_registry(registry_path)
    if not registry.get('frozen'):
        raise RuntimeError('source registry must be frozen before access checks')
    if not verify_registry_integrity(registry):
        raise RuntimeError('source registry integrity check failed')
    sources = registry.get('sources', [])
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {pool.submit(classify_url, item['url'], timeout): item for item in sources}
        for future in as_completed(futures):
            item = futures[future]
            source_id = item['id']
            try:
                results[source_id] = future.result()
            except Exception as exc:  # defensive boundary around worker failures
                results[source_id] = {'status': 'network_error', 'http_code': None, 'final_url': item.get('url',''), 'checked_at': utc_now(), 'error': str(exc)}
    payload = {
        'version': 1,
        'registry_sha256': registry.get('registry_sha256'),
        'checked_at': utc_now(),
        'sources': results,
    }
    atomic_write_json(output_path, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('registry',type=Path); parser.add_argument('--output',type=Path); parser.add_argument('--concurrency',type=int,default=4); parser.add_argument('--timeout',type=float,default=10)
    args=parser.parse_args(argv); output=args.output or args.registry.with_name('source_access.json'); result=check_registry(args.registry,output,concurrency=args.concurrency,timeout=args.timeout); print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)); return 0
if __name__=='__main__': raise SystemExit(main())
