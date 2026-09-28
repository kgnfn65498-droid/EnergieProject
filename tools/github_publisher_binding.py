from __future__ import annotations

import http.client
import hashlib
import json
import socket
import time
from pathlib import Path
from typing import Any

CONTAINER = 'energie-github-publisher'
SOCKET = '/var/run/docker.sock'
CANONICAL_BINDS = {
    '/energy/Inbox': 'Inbox',
    '/energy/Data/03_Systeem': 'Data/03_Systeem',
    '/energy/App/tools/system_path_contract.sh': 'App/tools/system_path_contract.sh',
    '/usr/local/bin/nas_github_publisher.sh': 'App/tools/nas_github_publisher.sh',
    '/publisher-private': 'Data/03_Systeem/Projectmanager/Private/github_publisher',
}


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path: str = SOCKET, timeout: float = 8.0):
        super().__init__('localhost', timeout=timeout)
        self.path = path

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect(self.path)
        self.sock = s


def _request(method: str, path: str, ok: tuple[int, ...], payload: dict | None = None) -> Any:
    conn = _UnixHTTPConnection()
    try:
        body = None if payload is None else json.dumps(payload).encode('utf-8')
        headers = {} if body is None else {'Content-Type': 'application/json'}
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        if resp.status not in ok:
            raise RuntimeError(f'docker http {resp.status}: {raw[:200]!r}')
        if not raw:
            return {}
        return json.loads(raw.decode('utf-8'))
    finally:
        conn.close()


def _bind_map(info: dict) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    host = info.get('HostConfig') if isinstance(info, dict) else {}
    for raw in (host.get('Binds') or []) if isinstance(host, dict) else []:
        parts = str(raw).rsplit(':', 2)
        if len(parts) == 3:
            result[parts[1]] = (parts[0], parts[2])
    return result


def _host_root_and_private(info: dict) -> tuple[str, str]:
    binds = _bind_map(info)
    inbox = binds.get('/energy/Inbox')
    private = binds.get('/publisher-private')
    if not inbox or not inbox[0].endswith('/Inbox'):
        raise RuntimeError('publisher host project-root bind ontbreekt')
    if not private:
        raise RuntimeError('publisher private bind ontbreekt')
    return inbox[0][:-len('/Inbox')], private[0]


def _sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()

def _code_identity(project_root: Path | str) -> dict[str,str]:
    root=Path(project_root)
    script=root/'App/tools/nas_github_publisher.sh'
    contract=root/'App/tools/system_path_contract.sh'
    if script.is_symlink() or not script.is_file() or contract.is_symlink() or not contract.is_file():
        raise RuntimeError('publisher code identity sources missing/unsafe')
    return {'script_sha256':_sha256(script),'path_contract_sha256':_sha256(contract)}

def binding_current(info: dict, project_root: Path | str | None = None) -> bool:
    try:
        host_root, private_root = _host_root_and_private(info)
    except Exception:
        return False
    binds = _bind_map(info)
    expected = {
        '/energy/Inbox': (f'{host_root}/Inbox', 'rw'),
        '/energy/Data/03_Systeem': (f'{host_root}/Data/03_Systeem', 'rw'),
        '/energy/App/tools/system_path_contract.sh': (f'{host_root}/App/tools/system_path_contract.sh', 'ro'),
        '/usr/local/bin/nas_github_publisher.sh': (f'{host_root}/App/tools/nas_github_publisher.sh', 'ro'),
        '/publisher-private': (private_root, 'rw'),
    }
    for dest, (src, mode) in expected.items():
        actual = binds.get(dest)
        if actual is None or actual[0] != src or mode not in str(actual[1]).split(','):
            return False
    if project_root is not None:
        try: identity=_code_identity(project_root)
        except Exception:return False
        labels=(info.get('Config') or {}).get('Labels') if isinstance(info,dict) else {}
        labels=labels if isinstance(labels,dict) else {}
        if labels.get('com.energie.publisher.script_sha256')!=identity['script_sha256']:
            return False
        if labels.get('com.energie.publisher.path_contract_sha256')!=identity['path_contract_sha256']:
            return False
    state = info.get('State') if isinstance(info, dict) else {}
    return isinstance(state, dict) and state.get('Running') is True


def _desired_payload(info: dict, project_root: Path | str | None = None) -> dict:
    host_root, private_root = _host_root_and_private(info)
    config = info.get('Config') if isinstance(info, dict) else {}
    host = info.get('HostConfig') if isinstance(info, dict) else {}
    image = str((config or {}).get('Image') or '').strip()
    if not image:
        raise RuntimeError('publisher image ontbreekt')
    network = str((host or {}).get('NetworkMode') or 'bridge')
    identity=_code_identity(project_root) if project_root is not None else {'script_sha256':'unverified','path_contract_sha256':'unverified'}
    return {
        'Image': image,
        'Entrypoint': ['/bin/sh'],
        'Env': ['ENERGIE_ROOT=/energy', 'ENERGIE_PUBLISHER_PRIVATE_ROOT=/publisher-private'],
        'Cmd': ['-ec', 'while :; do if [ -f /publisher-private/enabled ]; then sh /usr/local/bin/nas_github_publisher.sh || true; fi; sleep 15; done'],
        'Labels': {
            'com.energie.component':'github-publisher','com.energie.type2.binding':'canonical-v2',
            'com.energie.publisher.script_sha256':identity['script_sha256'],
            'com.energie.publisher.path_contract_sha256':identity['path_contract_sha256'],
        },
        'HostConfig': {
            'Binds': [
                f'{host_root}/Inbox:/energy/Inbox:rw',
                f'{host_root}/Data/03_Systeem:/energy/Data/03_Systeem:rw',
                f'{host_root}/App/tools/system_path_contract.sh:/energy/App/tools/system_path_contract.sh:ro',
                f'{host_root}/App/tools/nas_github_publisher.sh:/usr/local/bin/nas_github_publisher.sh:ro',
                f'{private_root}:/publisher-private:rw',
            ],
            'NetworkMode': network,
            'RestartPolicy': {'Name': 'unless-stopped', 'MaximumRetryCount': 0},
            'SecurityOpt': ['no-new-privileges'],
        },
    }


def _info() -> dict | None:
    try:
        value = _request('GET', f'/containers/{CONTAINER}/json', (200, 404))
    except RuntimeError as exc:
        if 'docker http 404' in str(exc):
            return None
        raise
    # _request cannot distinguish an empty 404 from an empty 200, so perform a
    # second lightweight lookup only when the payload has no Id/Name.
    if not isinstance(value, dict) or not (value.get('Id') or value.get('Name')):
        return None
    return value


def ensure_github_publisher_binding_current(root: Path | str, *, timeout_seconds: float = 45.0) -> dict:
    root = Path(root)
    contract = root / 'Inbox/ha_publication_required.json'
    if contract.exists():
        raise RuntimeError('publisher binding recreate refused while publication contract is active')
    info = _info()
    if info is None:
        return {'status': 'GREEN', 'reason': 'legacy_publisher_absent', 'recreate_performed': False}
    if binding_current(info, root):
        return {'status':'GREEN','reason':'publisher_binding_current_and_code_exact','recreate_performed':False,'code_identity':_code_identity(root)}

    payload = _desired_payload(info, root)
    backup = f'{CONTAINER}-type2-legacy'
    # Remove a stale backup only before touching the live container. A stale
    # backup can only be from a previously completed/rolled-back bounded attempt.
    _request('DELETE', f'/containers/{backup}?force=1&v=1', (204, 404))

    def rollback() -> None:
        try:
            _request('DELETE', f'/containers/{CONTAINER}?force=1&v=1', (204, 404))
        except Exception:
            pass
        try:
            _request('POST', f'/containers/{backup}/rename?name={CONTAINER}', (204,))
            _request('POST', f'/containers/{CONTAINER}/start', (204, 304))
        except Exception:
            pass

    try:
        _request('POST', f'/containers/{CONTAINER}/stop?t=20', (204, 304))
        _request('POST', f'/containers/{CONTAINER}/rename?name={backup}', (204,))
        _request('POST', f'/containers/create?name={CONTAINER}', (201,), payload)
        _request('POST', f'/containers/{CONTAINER}/start', (204, 304))
        deadline = time.monotonic() + max(2.0, float(timeout_seconds))
        final = None
        while time.monotonic() < deadline:
            final = _info()
            if final is not None and binding_current(final, root):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('publisher recreated binding did not become current')
        _request('DELETE', f'/containers/{backup}?force=1&v=1', (204, 404))
        return {'status':'GREEN','reason':'publisher_binding_recreated_with_current_code','recreate_performed':True,'code_identity':_code_identity(root)}
    except Exception as exc:
        rollback()
        raise RuntimeError('publisher binding recreate failed and rollback attempted') from exc
