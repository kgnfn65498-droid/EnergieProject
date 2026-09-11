#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CONTRACT_VERSION = 3
CONTAINER_NAME = 'energie-release-watcher'
EXPECTED_IMAGE = 'python:3.12-slim'
EXPECTED_COMMAND = ['sh', '/energy/App/tools/release_watcher.sh']
MARKER_REL = Path('Inbox/watcher_container_contract.json')
REQUEST_REL = Path('Inbox/watcher_recreate_request.json')
REQUIRED_CAP_ADD = {'DAC_OVERRIDE', 'DAC_READ_SEARCH', 'FOWNER'}

def expected_spec() -> dict:
    return {
        'contract_version': CONTRACT_VERSION,
        'container': CONTAINER_NAME,
        'image': EXPECTED_IMAGE,
        'command': EXPECTED_COMMAND,
        'network_mode': 'none',
        'cap_drop': ['ALL'],
        'cap_add': sorted(REQUIRED_CAP_ADD),
        'security_opt': ['no-new-privileges'],
        'restart_policy': 'unless-stopped',
        'mounts': {'/energy': 'project_root', '/var/run/docker.sock': '/var/run/docker.sock'},
    }

def spec_fingerprint() -> str:
    raw = json.dumps(expected_spec(), sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()

def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f'unsafe symlink path: {path}')
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def _payload(*, ready: bool, reason: str, details: dict | None = None) -> dict:
    return {
        'schema': 'energie_watcher_container_contract_v2',
        'status': 'GREEN' if ready else 'RECREATE_REQUIRED',
        'ready': ready,
        'recreate_required': not ready,
        'contract_version': CONTRACT_VERSION,
        'spec_fingerprint': spec_fingerprint(),
        'reason': reason,
        'details': details or {},
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }

def _write_recreate_request(root: Path, reason: str) -> dict:
    try:
        release_version = (root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    except OSError as exc:
        raise RuntimeError(f'cannot read release version: {exc}') from exc
    parts = release_version.split('.')
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise RuntimeError(f'invalid active release version for watcher recreate: {release_version!r}')
    fingerprint = spec_fingerprint()
    request_id = hashlib.sha256(f'{release_version}:{fingerprint}'.encode('utf-8')).hexdigest()[:32]
    payload = {
        'schema': 'energie_watcher_recreate_request_v1',
        'request_id': request_id,
        'operation': 'recreate_exact_energie_release_watcher',
        'release_version': release_version,
        'container': CONTAINER_NAME,
        'contract_version': CONTRACT_VERSION,
        'spec_fingerprint': fingerprint,
        'reason': reason,
        'confirmation_required': f'RECREATE WATCHER {release_version}',
    }
    path = root / REQUEST_REL
    if path.is_file():
        existing = json.loads(path.read_text(encoding='utf-8'))
        stable_keys = ('schema','request_id','operation','release_version','container','contract_version','spec_fingerprint','confirmation_required')
        if any(existing.get(key) != payload.get(key) for key in stable_keys):
            raise RuntimeError('existing watcher recreate request conflicts with current contract')
        return existing
    _atomic_json(path, payload)
    return payload

def probe(project_root: Path | str, *, socket_path: Path | str = '/var/run/docker.sock', client_factory=None, request_recreate: bool = False) -> dict:
    root = Path(project_root).resolve()
    marker = root / MARKER_REL
    socket = Path(socket_path)
    if not socket.exists():
        result = _payload(ready=False, reason='docker_socket_missing')
        _atomic_json(marker, result)
        if request_recreate:
            _write_recreate_request(root, result['reason'])
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
        command = list(config.get('Cmd') or [])
        image = str(config.get('Image') or '')
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
            'image_exact': image == EXPECTED_IMAGE,
            'command_exact': command == EXPECTED_COMMAND,
        }
        ready = all(checks.values())
        result = _payload(ready=ready, reason='contract_match' if ready else 'container_contract_mismatch', details=checks)
    except Exception as exc:
        result = _payload(ready=False, reason=f'probe_error:{type(exc).__name__}', details={'error': str(exc)})
    _atomic_json(marker, result)
    if not result.get('ready') and request_recreate:
        _write_recreate_request(root, result['reason'])
    if result.get('ready'):
        request = root / REQUEST_REL
        if request.is_file() and not request.is_symlink():
            request.unlink()
    return result

def main() -> int:
    parser = argparse.ArgumentParser(description='Verify exact Energie release-watcher container contract')
    parser.add_argument('--root', required=True)
    parser.add_argument('--request-recreate', action='store_true')
    args = parser.parse_args()
    result = probe(Path(args.root), request_recreate=args.request_recreate)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('ready') else 3

if __name__ == '__main__':
    raise SystemExit(main())
