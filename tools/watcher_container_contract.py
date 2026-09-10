#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CONTRACT_VERSION = 2
CONTAINER_NAME = 'energie-release-watcher'
MARKER_REL = Path('Inbox/watcher_container_contract.json')
REQUIRED_CAP_ADD = {'DAC_OVERRIDE', 'DAC_READ_SEARCH', 'FOWNER'}


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _payload(*, ready: bool, reason: str, details: dict | None = None) -> dict:
    return {
        'schema': 'energie_watcher_container_contract_v1',
        'status': 'GREEN' if ready else 'RECREATE_REQUIRED',
        'ready': ready,
        'recreate_required': not ready,
        'contract_version': CONTRACT_VERSION,
        'reason': reason,
        'details': details or {},
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }


def probe(project_root: Path | str, *, socket_path: Path | str = '/var/run/docker.sock', client_factory=None) -> dict:
    root = Path(project_root).resolve()
    marker = root / MARKER_REL
    socket = Path(socket_path)
    if not socket.exists():
        result = _payload(ready=False, reason='docker_socket_missing')
        _atomic_json(marker, result)
        return result

    try:
        if client_factory is None:
            app = root / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2'
            if str(app) not in sys.path:
                sys.path.insert(0, str(app))
            from docker_engine_unix_client import DockerEngineUnixClient
            client = DockerEngineUnixClient(str(socket))
        else:
            client = client_factory()
        client.ping()
        info = client.container_inspect(CONTAINER_NAME)
        config = info.get('Config') or {}
        host = info.get('HostConfig') or {}
        state = info.get('State') or {}
        env = set(config.get('Env') or [])
        mounts = info.get('Mounts') or []
        mount_map = {str(m.get('Destination') or ''): str(m.get('Source') or '') for m in mounts if isinstance(m, dict)}
        cap_add = set(host.get('CapAdd') or [])
        cap_drop = set(host.get('CapDrop') or [])
        security = set(host.get('SecurityOpt') or [])
        restart_name = str((host.get('RestartPolicy') or {}).get('Name') or '')
        checks = {
            'running': state.get('Running') is True,
            'contract_env': f'ENERGIE_WATCHER_CONTAINER_CONTRACT={CONTRACT_VERSION}' in env,
            'energy_mount': bool(mount_map.get('/energy')),
            'docker_socket_mount': mount_map.get('/var/run/docker.sock') == '/var/run/docker.sock',
            'network_none': str(host.get('NetworkMode') or '') == 'none',
            'cap_drop_all': 'ALL' in cap_drop,
            'cap_add_exact': cap_add == REQUIRED_CAP_ADD,
            'no_new_privileges': any('no-new-privileges' in item for item in security),
            'restart_unless_stopped': restart_name == 'unless-stopped',
        }
        ready = all(checks.values())
        result = _payload(ready=ready, reason='contract_match' if ready else 'container_contract_mismatch', details=checks)
    except Exception as exc:
        result = _payload(ready=False, reason=f'probe_error:{type(exc).__name__}', details={'error': str(exc)})
    _atomic_json(marker, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify fixed Energie release-watcher container contract')
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    result = probe(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('ready') else 3


if __name__ == '__main__':
    raise SystemExit(main())
