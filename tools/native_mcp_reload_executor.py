#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import http.client
import json
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

REQUEST = Path('Inbox/native_mcp_runtime/reload_request.json')
RESULT = Path('Inbox/native_mcp_runtime/reload_result.json')
RUNTIME_MARKER = Path('Data/03_Systeem/Projectmanager/RuntimeEvidence/native_mcp_runtime_fingerprint.json')
SOCKET_PATH = '/var/run/docker.sock'
CONTAINER = 'energie-filesystem-mcp'


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self):
        super().__init__('localhost', timeout=30)
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(SOCKET_PATH)


def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _restart() -> None:
    conn = _UnixHTTPConnection()
    try:
        conn.request('POST', f'/v1.41/containers/{CONTAINER}/restart?t=30', body=b'')
        response = conn.getresponse()
        response.read()
        if response.status not in (204,):
            raise RuntimeError(f'fixed MCP restart HTTP {response.status}')
    finally:
        conn.close()


def run(root: Path | str, *, wait_seconds: float = 60.0) -> dict:
    base = Path(root).resolve()
    request_path = base / REQUEST
    result_path = base / RESULT
    if not request_path.is_file() or request_path.is_symlink():
        raise RuntimeError('fixed native MCP reload request ontbreekt/onveilig')
    request = json.loads(request_path.read_text(encoding='utf-8'))
    if request.get('schema') != 'energie_native_mcp_reload_request_v1':
        raise RuntimeError('native MCP reload request schema ongeldig')
    if request.get('operation') != 'restart_exact_energie_filesystem_mcp':
        raise RuntimeError('native MCP reload operation ongeldig')
    if request.get('approved_by') != 'Peter' or not str(request.get('decision_id') or '').strip():
        raise RuntimeError('native MCP reload approval ontbreekt/ongeldig')
    request_id = str(request.get('request_id') or '')
    expected = str(request.get('expected_fingerprint') or '')
    if len(request_id) != 32 or any(c not in '0123456789abcdef' for c in request_id.lower()):
        raise RuntimeError('native MCP reload request-id ongeldig')
    if len(expected) != 64 or any(c not in '0123456789abcdef' for c in expected.lower()):
        raise RuntimeError('native MCP verwachte fingerprint ongeldig')
    _restart()
    marker_path = base / RUNTIME_MARKER
    deadline = time.monotonic() + max(1.0, float(wait_seconds))
    actual = ''
    while time.monotonic() < deadline:
        try:
            marker = json.loads(marker_path.read_text(encoding='utf-8'))
            if marker.get('schema') in {'energie_native_mcp_runtime_v2', 'energie_native_mcp_runtime_v3'}:
                actual = str(marker.get('fingerprint') or '')
        except (OSError, json.JSONDecodeError, UnicodeError):
            actual = ''
        if actual == expected:
            break
        time.sleep(0.25)
    ok = actual == expected
    result = {
        'schema': 'energie_native_mcp_reload_result_v1',
        'request_id': request_id,
        'status': 'GREEN' if ok else 'RED',
        'ok': ok,
        'container': CONTAINER,
        'expected_fingerprint': expected,
        'runtime_fingerprint': actual or None,
        'restart_performed': True,
        'finished_at': datetime.now(timezone.utc).isoformat(),
    }
    _atomic(result_path, result)
    if not ok:
        raise RuntimeError('native MCP restart uitgevoerd maar runtime fingerprint bleef mismatch')
    return result
