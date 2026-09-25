#!/usr/bin/env python3
from __future__ import annotations
from system_path_contract import project_system_path

import argparse
import hashlib
import json
import stat
import time
from pathlib import Path
from typing import Any

SCHEMA = 'energie_control_plane_runtime_guard_v1'
RUNTIME_SCHEMA = 'energie_control_plane_runtime_v1'
FINGERPRINT_FILES = ('control_plane.py', 'qnap_control_plane_bootstrap.py', 'control_plane_release_bridge.py', 'release_scoped_auth.py')
DEFAULT_STALE_SECONDS = 30


def _fingerprint(directory: Path) -> str:
    digest = hashlib.sha256()
    for name in FINGERPRINT_FILES:
        path = directory / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f'control-plane source missing/unsafe: {name}')
        digest.update(name.encode('utf-8') + b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()


def expected_fingerprint(project_root: Path | str) -> str:
    root = Path(project_root).resolve()
    return _fingerprint(root / 'Data/03_Systeem/Projectmanager/ControlPlane')


def _result(*, ready: bool, reason: str, expected: str | None = None, loaded: str | None = None, age: float | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'schema': SCHEMA,
        'status': 'GREEN' if ready else 'RESTART_REQUIRED',
        'ready': ready,
        'reason': reason,
        'expected_fingerprint': expected,
        'loaded_fingerprint': loaded,
    }
    if age is not None:
        payload['heartbeat_age_seconds'] = round(max(0.0, age), 3)
    return payload


def probe(project_root: Path | str, *, now: float | None = None, stale_seconds: int = DEFAULT_STALE_SECONDS) -> dict[str, Any]:
    if stale_seconds < 5:
        raise ValueError('stale_seconds must be at least 5')
    root = Path(project_root).resolve()
    try:
        expected = expected_fingerprint(root)
    except Exception as exc:
        return _result(ready=False, reason=f'source_invalid:{type(exc).__name__}')
    marker = project_system_path(root, 'Inbox/control_plane/runtime.json')
    try:
        st = marker.lstat()
    except FileNotFoundError:
        return _result(ready=False, reason='runtime_marker_missing', expected=expected)
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return _result(ready=False, reason='runtime_marker_unsafe', expected=expected)
    try:
        payload = json.loads(marker.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _result(ready=False, reason='runtime_marker_invalid', expected=expected)
    if not isinstance(payload, dict) or payload.get('schema') != RUNTIME_SCHEMA:
        return _result(ready=False, reason='runtime_marker_invalid', expected=expected)
    loaded = str(payload.get('loaded_fingerprint') or '').lower()
    if len(loaded) != 64 or any(ch not in '0123456789abcdef' for ch in loaded):
        return _result(ready=False, reason='runtime_marker_invalid', expected=expected, loaded=loaded or None)
    if loaded != expected:
        return _result(ready=False, reason='loaded_runtime_fingerprint_mismatch', expected=expected, loaded=loaded)
    try:
        heartbeat = float(payload.get('heartbeat_at_epoch'))
    except (TypeError, ValueError):
        return _result(ready=False, reason='runtime_marker_invalid', expected=expected, loaded=loaded)
    now_value = float(time.time() if now is None else now)
    age = now_value - heartbeat
    if age < -300:
        return _result(ready=False, reason='runtime_heartbeat_clock_invalid', expected=expected, loaded=loaded, age=age)
    if age > stale_seconds:
        return _result(ready=False, reason='runtime_heartbeat_stale', expected=expected, loaded=loaded, age=age)
    return _result(ready=True, reason='loaded_runtime_fingerprint_match', expected=expected, loaded=loaded, age=age)


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify loaded control-plane runtime against synced source')
    parser.add_argument('--root', required=True)
    parser.add_argument('--stale-seconds', type=int, default=DEFAULT_STALE_SECONDS)
    args = parser.parse_args()
    result = probe(Path(args.root), stale_seconds=args.stale_seconds)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('ready') else 3


if __name__ == '__main__':
    raise SystemExit(main())
