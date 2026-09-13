#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fcntl
import subprocess
import json
import os
import secrets
import socket
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _atomic_json(path: Path, payload: dict[str, Any], *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(8)
    temp = path.with_name(f'.{path.name}.tmp-{os.getpid()}-{token}')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(temp), flags, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, mode)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass



def _operation_lock_exclusive_probe(lock: Path) -> None:
    lock = Path(lock)
    if lock.is_symlink() or not lock.is_file():
        raise RuntimeError('NAS CR operation-lock ontbreekt of is onveilig')
    flags = os.O_RDWR
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(lock), flags)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RuntimeError('NAS CR operation-lock is geen regulier bestand')
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        child = """import fcntl, os, sys
p = sys.argv[1]
flags = os.O_RDWR | getattr(os, 'O_NOFOLLOW', 0)
fd = os.open(p, flags)
try:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(0)
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        raise SystemExit(3)
finally:
    os.close(fd)
"""
        result = subprocess.run(
            [sys.executable, '-c', child, str(lock)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5, check=False,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f'NAS CR operation-lock flock is niet exclusief over processen: rc={result.returncode}'
            )
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

def probe(root: Path, *, socket_path: Path = Path('/var/run/docker.sock'), client_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    bridge = root / 'Inbox' / 'nas_container_cr_local'
    capability = bridge / 'capability.json'
    version_path = root / 'App' / 'VERSIE.txt'
    payload: dict[str, Any]
    try:
        version = version_path.read_text(encoding='utf-8').strip()
        if not version:
            raise RuntimeError('runtimeversie ontbreekt')
        if bridge.is_symlink():
            raise RuntimeError('NAS CR bridge-directory is onveilig')
        bridge.mkdir(parents=True, exist_ok=True)
        bridge.chmod(0o777)
        if stat.S_IMODE(bridge.stat().st_mode) != 0o777:
            raise RuntimeError('NAS CR bridge-directory voldoet niet aan mailboxcontract 0777')
        operation_lock = root / 'Inbox' / '.nas-container-cr.operation.lock'
        _operation_lock_exclusive_probe(operation_lock)
        mode = socket_path.stat().st_mode
        if not stat.S_ISSOCK(mode):
            raise RuntimeError('lokale Docker socket ontbreekt of is geen socket')
        if client_factory is None:
            pm = root / 'App' / 'slimmemeterportal_import' / 'rootfs' / 'app' / 'projectmanager_v2'
            sys.path.insert(0, str(pm))
            from docker_engine_unix_client import DockerEngineUnixClient
            client_factory = DockerEngineUnixClient
        response = client_factory().ping()
        if not isinstance(response, dict) or response.get('ok') is not True:
            raise RuntimeError('lokale Docker ping niet GREEN')
        payload = {
            'schema': 'energie_nas_container_cr_local_capability_v1',
            'ready': True,
            'status': 'GREEN',
            'version': version,
            'transport': 'local_docker_unix_socket',
            'bridge_mode': '0777',
            'request_result_mode': '0644',
            'mailbox_contract_owner': 'watcher',
            'operation_lock_exclusive': True,
            'checked_at': datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        payload = {
            'schema': 'energie_nas_container_cr_local_capability_v1',
            'ready': False,
            'status': 'RED',
            'error': str(exc),
            'checked_at': datetime.now(timezone.utc).isoformat(),
        }
    _atomic_json(capability, payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description='Probe fixed local Docker capability for NAS CR')
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    result = probe(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('ready') is True else 1


if __name__ == '__main__':
    raise SystemExit(main())
