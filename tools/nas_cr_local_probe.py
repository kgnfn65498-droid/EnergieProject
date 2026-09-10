#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import socket
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def probe(root: Path, *, socket_path: Path = Path('/var/run/docker.sock'), client_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    root = Path(root).resolve()
    capability = root / 'Inbox' / 'nas_container_cr_local' / 'capability.json'
    version_path = root / 'App' / 'VERSIE.txt'
    payload: dict[str, Any]
    try:
        version = version_path.read_text(encoding='utf-8').strip()
        if not version:
            raise RuntimeError('runtimeversie ontbreekt')
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
