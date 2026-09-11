#!/usr/bin/env python3
from __future__ import annotations

import argparse
import http.client
import json
import os
import socket
import time
from pathlib import Path
from urllib.parse import quote, urlencode

ALLOWED_ACTIONS = {'watcher_recreate', 'native_mcp_reload'}
WATCHER_CONTAINER = 'energie-release-watcher'
MCP_CONTAINER = 'energie-filesystem-mcp'
WATCHER_IMAGE = 'python:3.12-slim'
WATCHER_COMMAND = ['sh', '/energy/App/tools/release_watcher.sh']
WATCHER_CAPS = ['DAC_OVERRIDE', 'DAC_READ_SEARCH', 'FOWNER']


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 30.0):
        super().__init__('localhost', timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self.sock = sock


class DockerUnixClient:
    def __init__(self, socket_path: str = '/var/run/docker.sock', timeout: float = 30.0):
        self.socket_path = socket_path
        self.timeout = timeout

    def _request(self, method: str, path: str, *, payload=None, ok=(200, 201, 204)):
        body = None
        headers = {}
        if payload is not None:
            body = json.dumps(payload, separators=(',', ':')).encode('utf-8')
            headers = {'Content-Type': 'application/json', 'Content-Length': str(len(body))}
        conn = _UnixHTTPConnection(self.socket_path, self.timeout)
        try:
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            raw = response.read()
            if response.status not in ok:
                detail = raw.decode('utf-8', errors='replace')[:1000]
                raise RuntimeError(f'Docker Engine HTTP {response.status}: {detail}')
            if not raw:
                return {'ok': True}
            return json.loads(raw.decode('utf-8'))
        finally:
            conn.close()

    def ping(self):
        conn = _UnixHTTPConnection(self.socket_path, self.timeout)
        try:
            conn.request('GET', '/_ping')
            response = conn.getresponse()
            raw = response.read().decode('utf-8', errors='replace').strip()
            if response.status != 200 or raw != 'OK':
                raise RuntimeError(f'Docker ping mislukt: HTTP {response.status} {raw}')
            return {'ok': True}
        finally:
            conn.close()

    def inspect_container(self, name: str):
        safe = quote(name, safe='')
        try:
            return self._request('GET', f'/containers/{safe}/json', ok=(200,))
        except RuntimeError as exc:
            if 'HTTP 404' in str(exc):
                return None
            raise

    def inspect_image(self, image: str):
        safe = quote(image, safe='')
        return self._request('GET', f'/images/{safe}/json', ok=(200,))

    def rename_container(self, name: str, new_name: str):
        safe = quote(name, safe='')
        return self._request('POST', f'/containers/{safe}/rename?{urlencode({"name": new_name})}', ok=(204,))

    def stop_container(self, name: str, timeout: int = 15):
        safe = quote(name, safe='')
        return self._request('POST', f'/containers/{safe}/stop?t={int(timeout)}', ok=(204, 304))

    def remove_container(self, name: str, *, force: bool = True):
        safe = quote(name, safe='')
        return self._request('DELETE', f'/containers/{safe}?force={1 if force else 0}&v=1', ok=(204,))

    def create_container(self, name: str, payload: dict):
        return self._request('POST', f'/containers/create?{urlencode({"name": name})}', payload=payload, ok=(201,))

    def start_container(self, name: str):
        safe = quote(name, safe='')
        return self._request('POST', f'/containers/{safe}/start', ok=(204, 304))

    def restart_container(self, name: str, timeout: int = 30):
        safe = quote(name, safe='')
        return self._request('POST', f'/containers/{safe}/restart?t={int(timeout)}', ok=(204,))


def _load_json(path: Path) -> dict:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f'vereist regulier bestand ontbreekt/onveilig: {path}')
    value = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise RuntimeError(f'ongeldige JSON-objectstructuur: {path}')
    return value


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f'onveilig symlinkdoel: {path}')
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def find_live_approval(queue_path: Path, action: str, *, decision_id: str | None = None) -> dict:
    if action not in ALLOWED_ACTIONS:
        raise RuntimeError('actie niet toegestaan')
    data = _load_json(Path(queue_path))
    for item in reversed(data.get('items') or []):
        if not isinstance(item, dict):
            continue
        if item.get('action') != action:
            continue
        if item.get('approved_by') != 'Peter':
            continue
        if item.get('status') != 'APPROVED_AWAITING_SAFETY_OR_EXECUTOR':
            continue
        if decision_id is not None and item.get('decision_id') != decision_id:
            continue
        return item
    raise RuntimeError(f'geen live Peter-goedkeuring voor {action}')



def already_completed(result_path: Path, request_id: str) -> bool:
    try:
        result = _load_json(Path(result_path))
    except Exception:
        return False
    return result.get('status') == 'GREEN' and result.get('ok') is True and result.get('request_id') == request_id


def load_control_plane_native_request(inbox: Path, approved_queue: Path):
    request = _load_json(Path(inbox) / 'control_plane' / 'requests' / 'native_mcp_reload.json')
    if request.get('schema') != 'energie_control_plane_request_v1':
        raise RuntimeError('control-plane native MCP request schema ongeldig')
    if request.get('action') != 'native_mcp_reload':
        raise RuntimeError('control-plane native MCP action ongeldig')
    if request.get('approved_by') != 'Peter':
        raise RuntimeError('control-plane native MCP actor ongeldig')
    decision_id = str(request.get('decision_id') or '').strip()
    request_id = str(request.get('request_id') or '').lower()
    expected = str(request.get('expected_fingerprint') or '').lower()
    if len(request_id) != 32 or any(ch not in '0123456789abcdef' for ch in request_id):
        raise RuntimeError('control-plane native MCP request_id ongeldig')
    if len(expected) != 64 or any(ch not in '0123456789abcdef' for ch in expected):
        raise RuntimeError('control-plane native MCP fingerprint ongeldig')
    if not decision_id:
        raise RuntimeError('control-plane native MCP decision_id ontbreekt')
    approval = find_live_approval(approved_queue, 'native_mcp_reload', decision_id=decision_id)
    return request, approval

def watcher_create_payload(host_project_root: str) -> dict:
    host_root = str(host_project_root).rstrip('/')
    if host_root != '/share/Energie_NAS/EnergieProject':
        raise RuntimeError('onverwachte host project-root')
    return {
        'Image': WATCHER_IMAGE,
        'Cmd': list(WATCHER_COMMAND),
        'Env': [
            'ENERGIE_ROOT=/energy',
            'ENERGIE_WATCH_INTERVAL=5',
            'ENERGIE_ZIP_STABLE_POLLS=3',
            'ENERGIE_WATCHER_HEARTBEAT_STALE_SECONDS=30',
            'ENERGIE_WATCHER_CONTAINER_CONTRACT=3',
            'ENERGIE_BACKUP_RETENTION=999',
            'ENERGIE_PROCESSED_RETENTION=999',
        ],
        'HostConfig': {
            'Binds': [
                f'{host_root}:/energy',
                '/var/run/docker.sock:/var/run/docker.sock',
            ],
            'NetworkMode': 'none',
            'CapDrop': ['ALL'],
            'CapAdd': list(WATCHER_CAPS),
            'SecurityOpt': ['no-new-privileges'],
            'RestartPolicy': {'Name': 'unless-stopped', 'MaximumRetryCount': 0},
        },
    }


def load_bootstrap_watcher_request(inbox: Path, approved_queue: Path, version_path: Path):
    request = _load_json(Path(inbox) / 'watcher_recreate_request.json')
    version = Path(version_path).read_text(encoding='utf-8').strip()
    required = {
        'schema': 'energie_watcher_recreate_request_v1',
        'operation': 'recreate_exact_energie_release_watcher',
        'release_version': version,
        'container': WATCHER_CONTAINER,
        'contract_version': 3,
        'confirmation_required': f'RECREATE WATCHER {version}',
    }
    for key, expected in required.items():
        if request.get(key) != expected:
            raise RuntimeError(f'watcher request mismatch: {key}')
    request_id = str(request.get('request_id') or '')
    if len(request_id) != 32 or any(ch not in '0123456789abcdef' for ch in request_id.lower()):
        raise RuntimeError('watcher request_id ongeldig')
    approval = find_live_approval(approved_queue, 'watcher_recreate')
    return request, approval


def load_native_mcp_request(inbox: Path, approved_queue: Path):
    request = _load_json(Path(inbox) / 'native_mcp_runtime' / 'reload_request.json')
    if request.get('schema') != 'energie_native_mcp_reload_request_v1':
        raise RuntimeError('native MCP request schema ongeldig')
    if request.get('operation') != 'restart_exact_energie_filesystem_mcp':
        raise RuntimeError('native MCP operation ongeldig')
    if request.get('approved_by') != 'Peter':
        raise RuntimeError('native MCP request actor ongeldig')
    decision_id = str(request.get('decision_id') or '').strip()
    if not decision_id:
        raise RuntimeError('native MCP decision_id ontbreekt')
    expected = str(request.get('expected_fingerprint') or '').lower()
    if len(expected) != 64 or any(ch not in '0123456789abcdef' for ch in expected):
        raise RuntimeError('native MCP fingerprint ongeldig')
    approval = find_live_approval(approved_queue, 'native_mcp_reload', decision_id=decision_id)
    return request, approval


class ControlPlane:
    def __init__(self, *, inbox: Path, approved_queue: Path, version_path: Path,
                 runtime_evidence: Path, host_project_root: str,
                 docker: DockerUnixClient | None = None):
        self.inbox = Path(inbox)
        self.approved_queue = Path(approved_queue)
        self.version_path = Path(version_path)
        self.runtime_evidence = Path(runtime_evidence)
        self.host_project_root = host_project_root
        self.docker = docker or DockerUnixClient()
        self.result_root = self.inbox / 'control_plane'

    def _wait_json(self, path: Path, predicate, timeout: float):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                value = _load_json(path)
            except Exception:
                value = None
            if isinstance(value, dict) and predicate(value):
                return value
            time.sleep(0.5)
        raise RuntimeError(f'timeout op live readback: {path}')

    def recreate_watcher(self) -> dict:
        request, approval = load_bootstrap_watcher_request(self.inbox, self.approved_queue, self.version_path)
        self.docker.ping()
        self.docker.inspect_image(WATCHER_IMAGE)
        rollback_name = f'{WATCHER_CONTAINER}-rollback-control-plane'
        existing_rollback = self.docker.inspect_container(rollback_name)
        if existing_rollback is not None:
            self.docker.remove_container(rollback_name, force=True)
        old = self.docker.inspect_container(WATCHER_CONTAINER)
        renamed = False
        try:
            if old is not None:
                self.docker.rename_container(WATCHER_CONTAINER, rollback_name)
                renamed = True
                try:
                    self.docker.stop_container(rollback_name, timeout=15)
                except RuntimeError:
                    pass
            self.docker.create_container(WATCHER_CONTAINER, watcher_create_payload(self.host_project_root))
            self.docker.start_container(WATCHER_CONTAINER)
            proof = self._wait_json(
                self.inbox / 'watcher_container_contract.json',
                lambda v: v.get('ready') is True and v.get('contract_version') == 3,
                60.0,
            )
            if renamed:
                self.docker.remove_container(rollback_name, force=True)
            result = {
                'schema': 'energie_control_plane_result_v1',
                'action': 'watcher_recreate',
                'status': 'GREEN', 'ok': True,
                'request_id': request['request_id'],
                'approval_action_id': approval['id'],
                'decision_id': approval.get('decision_id'),
                'contract_version': proof.get('contract_version'),
            }
            _atomic_json(self.result_root / 'watcher_recreate_result.json', result)
            _atomic_json(self.result_root / 'results' / 'watcher_recreate.json', result)
            return result
        except Exception:
            try:
                current = self.docker.inspect_container(WATCHER_CONTAINER)
                if current is not None:
                    self.docker.remove_container(WATCHER_CONTAINER, force=True)
            except Exception:
                pass
            if renamed:
                try:
                    self.docker.rename_container(rollback_name, WATCHER_CONTAINER)
                    self.docker.start_container(WATCHER_CONTAINER)
                except Exception:
                    pass
            raise

    def reload_native_mcp(self) -> dict:
        request, approval = load_control_plane_native_request(self.inbox, self.approved_queue)
        self.docker.ping()
        if self.docker.inspect_container(MCP_CONTAINER) is None:
            raise RuntimeError('energie-filesystem-mcp ontbreekt')
        self.docker.restart_container(MCP_CONTAINER, timeout=30)
        expected = request['expected_fingerprint'].lower()
        proof = self._wait_json(
            self.runtime_evidence / 'native_mcp_runtime_fingerprint.json',
            lambda v: v.get('schema') == 'energie_native_mcp_runtime_v2' and str(v.get('fingerprint') or '').lower() == expected,
            90.0,
        )
        result = {
            'schema': 'energie_native_mcp_reload_result_v1',
            'request_id': request['request_id'],
            'status': 'GREEN', 'ok': True,
            'container': MCP_CONTAINER,
            'expected_fingerprint': expected,
            'runtime_fingerprint': str(proof.get('fingerprint') or '').lower(),
            'restart_performed': True,
            'approval_action_id': approval['id'],
        }
        _atomic_json(self.result_root / 'results' / 'native_mcp_reload.json', result)
        _atomic_json(self.inbox / 'native_mcp_runtime' / 'reload_result.json', result)
        return result

    def process_once(self):
        results = []
        watcher_request = self.inbox / 'watcher_recreate_request.json'
        if watcher_request.is_file() and not watcher_request.is_symlink():
            try:
                request_id = str(_load_json(watcher_request).get('request_id') or '')
                watcher_result = self.result_root / 'watcher_recreate_result.json'
                if not already_completed(watcher_result, request_id):
                    results.append(self.recreate_watcher())
            except RuntimeError as exc:
                _atomic_json(self.result_root / 'watcher_recreate_result.json', {
                    'schema':'energie_control_plane_result_v1','action':'watcher_recreate','status':'RED','ok':False,'error':str(exc)
                })
        native_request = self.inbox / 'control_plane' / 'requests' / 'native_mcp_reload.json'
        if native_request.is_file() and not native_request.is_symlink():
            try:
                request_id = str(_load_json(native_request).get('request_id') or '')
                native_result = self.result_root / 'results' / 'native_mcp_reload.json'
                if not already_completed(native_result, request_id):
                    results.append(self.reload_native_mcp())
            except RuntimeError as exc:
                _atomic_json(self.result_root / 'results' / 'native_mcp_reload.json', {
                    'schema':'energie_control_plane_result_v1','action':'native_mcp_reload','status':'RED','ok':False,'error':str(exc)
                })
        return results


def main() -> int:
    parser = argparse.ArgumentParser(description='Energie control-plane: exact allowlisted Docker actions only')
    parser.add_argument('--inbox', default='/energy-inbox')
    parser.add_argument('--approved-queue', default='/pm-approved/queue.json')
    parser.add_argument('--version', default='/energy-version/VERSIE.txt')
    parser.add_argument('--runtime-evidence', default='/runtime-evidence')
    parser.add_argument('--host-project-root', default='/share/Energie_NAS/EnergieProject')
    parser.add_argument('--interval', type=float, default=2.0)
    args = parser.parse_args()
    cp = ControlPlane(
        inbox=Path(args.inbox), approved_queue=Path(args.approved_queue),
        version_path=Path(args.version), runtime_evidence=Path(args.runtime_evidence),
        host_project_root=args.host_project_root,
    )
    while True:
        cp.process_once()
        time.sleep(max(0.5, args.interval))


if __name__ == '__main__':
    raise SystemExit(main())
