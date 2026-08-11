"""Shared deterministic IO helpers."""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def canonical_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest_object(data: object) -> str:
    return sha256_text(canonical_json(data))


def atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, data: object) -> None:
    atomic_write_text(Path(path), json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def normalize_url(url: str) -> str:
    url = url.rstrip('.,;:')
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path.rstrip('/') or '/'
    return urlunsplit((scheme, netloc, path, parts.query, ''))

from contextlib import contextmanager
import time

@contextmanager
def file_lock(path: Path, *, timeout: float = 10.0, stale_after: float = 60.0):
    """Portable advisory lock using atomic O_EXCL lock-file creation."""
    path = Path(path)
    lock_path = path.with_name(path.name + '.lock')
    deadline = time.monotonic() + timeout
    while True:
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.write(fd, f'{os.getpid()} {time.time()}\n'.encode('ascii'))
            os.close(fd)
            break
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > stale_after:
                    lock_path.unlink(missing_ok=True)
                    continue
            except FileNotFoundError:
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f'timed out waiting for lock: {lock_path}')
            time.sleep(0.005)
    try:
        yield
    finally:
        lock_path.unlink(missing_ok=True)
