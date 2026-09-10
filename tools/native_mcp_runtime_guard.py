#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

TARGETS = ('crash_recovery.py', 'tools_recovery.py')
MARKER_REL = Path('Inbox/native_mcp_runtime/runtime_fingerprint.json')
STATE_REL = Path('Inbox/native_mcp_runtime/runtime_guard.json')


def expected_fingerprint(root: Path | str) -> str:
    native = Path(root).resolve() / 'Infra/Docker/native-mcp'
    digest = hashlib.sha256()
    for name in TARGETS:
        path = native / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f'native MCP bron ontbreekt/onveilig: {name}')
        digest.update(name.encode('utf-8') + b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def probe(root: Path | str) -> dict:
    base = Path(root).resolve()
    expected = expected_fingerprint(base)
    marker_path = base / MARKER_REL
    try:
        marker = json.loads(marker_path.read_text(encoding='utf-8')) if marker_path.is_file() else None
    except (OSError, json.JSONDecodeError, UnicodeError):
        marker = None
    actual = str((marker or {}).get('fingerprint') or '')
    schema_ok = (marker or {}).get('schema') == 'energie_native_mcp_runtime_v1'
    ready = schema_ok and actual == expected
    result = {
        'schema': 'energie_native_mcp_runtime_guard_v1',
        'status': 'GREEN' if ready else 'RELOAD_REQUIRED',
        'ready': ready,
        'reload_required': not ready,
        'expected_fingerprint': expected,
        'runtime_fingerprint': actual or None,
        'marker': str(marker_path),
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }
    _atomic(base / STATE_REL, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Compare native MCP source and live-runtime fingerprint')
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    result = probe(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('ready') else 3


if __name__ == '__main__':
    raise SystemExit(main())
