#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import socket
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from control_plane_release_bridge import authorize_release_native_reconcile, authorize_release_native_request, release_result_fields

ALLOWED_ACTIONS = {'watcher_recreate', 'native_mcp_reload', 'platformtest_run'}
WATCHER_CONTAINER = 'energie-release-watcher'
MCP_CONTAINER = 'energie-filesystem-mcp'
WATCHER_IMAGE = 'python:3.12-slim'
WATCHER_COMMAND = ['sh', '/energy/App/tools/release_watcher.sh']
WATCHER_CAPS = ['DAC_OVERRIDE', 'DAC_READ_SEARCH', 'FOWNER']
PLATFORMTEST_IMAGE = 'energie-filesystem-mcp:runtime-v1'
PLATFORMTEST_PROFILE = 'publisher_full_suite_v1'
PLATFORMTEST_RUNNER = r'''import hashlib,json,os,pathlib,pytest,sys
root=pathlib.Path('/workspace')
mp=root/'.energie-platformtest-source.json'
m=json.loads(mp.read_text(encoding='utf-8'))
assert m.get('schema')=='energie_platformtest_source_v1'
assert m.get('candidate_sha')==os.environ['ENERGIE_CANDIDATE_SHA']
actual=[]
for p in sorted(root.rglob('*')):
    if p==mp: continue
    assert not p.is_symlink()
    if p.is_dir(): continue
    assert p.is_file()
    actual.append({'path':p.relative_to(root).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size,'mode':'100755' if p.stat().st_mode & 0o111 else '100644'})
canonical=json.dumps(actual,separators=(',',':'),sort_keys=True).encode()
digest=hashlib.sha256(canonical).hexdigest()
assert actual==m.get('files') and digest==m.get('source_sha256')==os.environ['ENERGIE_SOURCE_SHA256']
commit=bytes.fromhex(m['git_commit_hex'])
candidate=hashlib.sha1(b'commit '+str(len(commit)).encode()+b'\0'+commit).hexdigest()
assert candidate==m['candidate_sha']==os.environ['ENERGIE_CANDIDATE_SHA']
def tree_sha(prefix=''):
    children={}
    for entry in actual:
        rel=entry['path']
        if prefix:
            if not rel.startswith(prefix+'/'): continue
            rel=rel[len(prefix)+1:]
        head,sep,_=rel.partition('/')
        children.setdefault(head,[] if sep else entry)
    raw=bytearray()
    for name,value in sorted(children.items(),key=lambda item:(item[0]+('/' if isinstance(item[1],list) else '')).encode()):
        if isinstance(value,list): mode='40000'; oid=tree_sha(prefix+'/'+name if prefix else name)
        else:
            data=(root/value['path']).read_bytes();mode=value['mode'];oid=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
        raw.extend(mode.encode()+b' '+name.encode()+b'\0'+bytes.fromhex(oid))
    data=bytes(raw);return hashlib.sha1(b'tree '+str(len(data)).encode()+b'\0'+data).hexdigest()
expected_tree=next(line[5:].decode() for line in commit.splitlines() if line.startswith(b'tree '))
assert tree_sha()==expected_tree
sys.exit(pytest.main(['-q','-p','no:cacheprovider']))'''
PLATFORMTEST_COMMAND = ['python3', '-c', PLATFORMTEST_RUNNER]
PLATFORMTEST_REQUEST_SCHEMA = 'energie_platformtest_run_request_v1'
PLATFORMTEST_RESULT_SCHEMA = 'energie_platformtest_run_result_v1'
PLATFORMTEST_TIMEOUT_SECONDS = 3 * 60 * 60
RUNTIME_FINGERPRINT_FILES = ('control_plane.py', 'qnap_control_plane_bootstrap.py', 'control_plane_release_bridge.py', 'release_scoped_auth.py')

def _loaded_runtime_fingerprint() -> str:
    root = Path(__file__).resolve().parent
    digest = hashlib.sha256()
    for name in RUNTIME_FINGERPRINT_FILES:
        path = root / name
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f'control-plane runtime fingerprint source missing/unsafe: {name}')
        digest.update(name.encode('utf-8') + b'\0')
        digest.update(path.read_bytes())
    return digest.hexdigest()

# Captured at module import: mounted source may change while loaded code stays old.
LOADED_RUNTIME_FINGERPRINT = _loaded_runtime_fingerprint()


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

    def _request_raw(self, method: str, path: str, *, ok=(200, 201, 204), timeout: float | None = None):
        conn = _UnixHTTPConnection(self.socket_path, self.timeout if timeout is None else float(timeout))
        try:
            conn.request(method, path, body=None, headers={})
            response = conn.getresponse()
            raw = response.read()
            if response.status not in ok:
                detail = raw.decode('utf-8', errors='replace')[:1000]
                raise RuntimeError(f'Docker Engine HTTP {response.status}: {detail}')
            return raw
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

    def container_logs(self, name: str) -> str:
        safe = quote(name, safe='')
        raw = self._request_raw('GET', f'/containers/{safe}/logs?stdout=1&stderr=1', ok=(200,))
        return raw.decode('utf-8', errors='replace')


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
    fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.tmp-', dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
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


def _optional_json(path: Path) -> dict:
    try:
        return _load_json(Path(path))
    except Exception:
        return {}


def _native_runtime_matches(runtime_evidence: Path, expected: str) -> bool:
    marker = _optional_json(Path(runtime_evidence) / 'native_mcp_runtime_fingerprint.json')
    return bool(
        marker.get('schema') in {'energie_native_mcp_runtime_v2', 'energie_native_mcp_runtime_v3'}
        and str(marker.get('fingerprint') or '').lower() == str(expected or '').lower()
    )


def _native_result_base(request: dict, approval: dict | None) -> dict:
    result = {
        'schema': 'energie_native_mcp_reload_result_v1',
        'request_id': request['request_id'],
        'container': MCP_CONTAINER,
        'expected_fingerprint': str(request['expected_fingerprint']).lower(),
        'release_version': request['release_version'],
    }
    if approval is not None:
        result.update({
            'approval_action_id': approval['id'],
            'decision_id': request['decision_id'],
            'command_id': request['command_id'],
            'authorization': 'peter_approval',
        })
    else:
        result.update(release_result_fields(request))
        result['authorization'] = 'release_controller'
    return result


def load_control_plane_native_request(inbox: Path, approved_queue: Path):
    request = _load_json(Path(inbox) / 'control_plane' / 'requests' / 'native_mcp_reload.json')
    if request.get('schema') != 'energie_control_plane_request_v1':
        raise RuntimeError('control-plane native MCP request schema ongeldig')
    if request.get('action') != 'native_mcp_reload':
        raise RuntimeError('control-plane native MCP action ongeldig')
    if request.get('approved_by') != 'Peter':
        raise RuntimeError('control-plane native MCP actor ongeldig')
    decision_id = str(request.get('decision_id') or '').strip()
    command_id = str(request.get('command_id') or '').strip()
    release_version = str(request.get('release_version') or '').strip()
    request_id = str(request.get('request_id') or '').lower()
    expected = str(request.get('expected_fingerprint') or '').lower()
    if len(request_id) != 32 or any(ch not in '0123456789abcdef' for ch in request_id):
        raise RuntimeError('control-plane native MCP request_id ongeldig')
    if len(expected) != 64 or any(ch not in '0123456789abcdef' for ch in expected):
        raise RuntimeError('control-plane native MCP fingerprint ongeldig')
    if not decision_id:
        raise RuntimeError('control-plane native MCP decision_id ontbreekt')
    if not command_id:
        raise RuntimeError('control-plane native MCP command_id ontbreekt')
    if not release_version:
        raise RuntimeError('control-plane native MCP release_version ontbreekt')
    approval = find_live_approval(approved_queue, 'native_mcp_reload', decision_id=decision_id)
    if str(approval.get('command_id') or '').strip() != command_id:
        raise RuntimeError('control-plane native MCP command/approval mismatch')
    return request, approval


def load_platformtest_request(inbox: Path) -> dict:
    request = _load_json(Path(inbox) / 'control_plane' / 'requests' / 'platformtest_run.json')
    allowed = {'schema', 'request_id', 'action', 'candidate_sha', 'source_sha256', 'test_profile'}
    if set(request) != allowed:
        raise RuntimeError('platformtest request bevat onbekende/ontbrekende velden')
    if request.get('schema') != PLATFORMTEST_REQUEST_SCHEMA:
        raise RuntimeError('platformtest request schema ongeldig')
    if request.get('action') != 'platformtest_run':
        raise RuntimeError('platformtest action ongeldig')
    request_id = str(request.get('request_id') or '').lower()
    candidate = str(request.get('candidate_sha') or '').lower()
    source_sha256 = str(request.get('source_sha256') or '').lower()
    profile = str(request.get('test_profile') or '')
    if len(request_id) != 32 or any(ch not in '0123456789abcdef' for ch in request_id):
        raise RuntimeError('platformtest request_id ongeldig')
    if len(candidate) != 40 or any(ch not in '0123456789abcdef' for ch in candidate):
        raise RuntimeError('platformtest candidate_sha ongeldig')
    if len(source_sha256) != 64 or any(ch not in '0123456789abcdef' for ch in source_sha256):
        raise RuntimeError('platformtest source_sha256 ongeldig')
    if profile != PLATFORMTEST_PROFILE:
        raise RuntimeError('platformtest profile niet toegestaan')
    return request


def platformtest_create_payload(host_project_root: str, request: dict, *, image_id: str) -> dict:
    host_root = str(host_project_root).rstrip('/')
    if host_root != '/share/Energie_NAS/EnergieProject':
        raise RuntimeError('onverwachte host project-root')
    candidate = str(request['candidate_sha']).lower()
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', str(image_id or '').lower()):
        raise RuntimeError('platformtest immutable image identity ongeldig')
    workspace = f'{host_root}/Data/03_Systeem/Projectmanager/Staging/PlatformTest/{candidate}'
    return {
        'Image': str(image_id).lower(),
        'Cmd': list(PLATFORMTEST_COMMAND),
        'WorkingDir': '/workspace',
        'Env': [
            'PYTHONPATH=/workspace',
            f'ENERGIE_CANDIDATE_SHA={candidate}',
            f'ENERGIE_SOURCE_SHA256={request["source_sha256"]}',
        ],
        'Tty': True,
        'Labels': {
            'com.energie.component': 'platformtest',
            'com.energie.request_id': str(request['request_id']),
            'com.energie.candidate_sha': candidate,
            'com.energie.source_sha256': str(request['source_sha256']),
            'com.energie.test_profile': PLATFORMTEST_PROFILE,
        },
        'HostConfig': {
            'Binds': [f'{workspace}:/workspace:ro'],
            'NetworkMode': 'none',
            'ReadonlyRootfs': True,
            'CapDrop': ['ALL'],
            'SecurityOpt': ['no-new-privileges'],
            'Tmpfs': {'/tmp': 'rw,noexec,nosuid,nodev,size=256m'},
            'AutoRemove': False,
        },
    }


def _pytest_counts(logs: str) -> dict:
    counts = {'passed': 0, 'failed': 0, 'skipped': 0, 'errors': 0}
    patterns = {
        'passed': r'(\d+) passed',
        'failed': r'(\d+) failed',
        'skipped': r'(\d+) skipped',
        'errors': r'(\d+) error(?:s)?',
    }
    for key, pattern in patterns.items():
        matches = re.findall(pattern, logs or '', flags=re.IGNORECASE)
        if matches:
            counts[key] = int(matches[-1])
    return counts


def terminal_result(result_path: Path, request: dict) -> bool:
    try:
        result = _load_json(Path(result_path))
    except Exception:
        return False
    return (
        result.get('schema') == PLATFORMTEST_RESULT_SCHEMA
        and result.get('action') == 'platformtest_run'
        and str(result.get('request_id') or '') == str(request.get('request_id') or '')
        and str(result.get('candidate_sha') or '') == str(request.get('candidate_sha') or '')
        and str(result.get('source_sha256') or '') == str(request.get('source_sha256') or '')
        and result.get('test_profile') == request.get('test_profile')
        and re.fullmatch(r'sha256:[0-9a-f]{64}', str(result.get('image_id') or '').lower()) is not None
        and result.get('network_mode') == 'none'
        and result.get('production_modified') is False
        and result.get('container_removed') is True
        and result.get('status') in {'GREEN', 'RED'}
        and (result.get('status') != 'GREEN' or (result.get('ok') is True and result.get('exit_code') == 0))
    )


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
            runtime_marker = self.inbox / 'release_controller' / 'runtime.json'
            try:
                runtime_marker.unlink(missing_ok=True)
            except OSError:
                pass
            proof = self._wait_json(
                runtime_marker,
                lambda v: v.get('schema') == 'energie_release_controller_runtime_v1' and int(v.get('pid') or 0) > 1,
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
                'release_controller_pid': proof.get('pid'),
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

    def _write_native_result(self, result: dict) -> dict:
        _atomic_json(self.result_root / 'results' / 'native_mcp_reload.json', result)
        _atomic_json(self.inbox / 'native_mcp_runtime' / 'reload_result.json', result)
        return result

    def _reconcile_fenced_native_attempt(self, request: dict, result_path: Path) -> dict | None:
        previous = _optional_json(result_path)
        if str(previous.get('request_id') or '') != str(request.get('request_id') or ''):
            return None
        if previous.get('status') == 'GREEN' and previous.get('ok') is True:
            return previous
        if previous.get('retry_allowed') is not False:
            return None
        expected = str(request.get('expected_fingerprint') or '').lower()
        if _native_runtime_matches(self.runtime_evidence, expected):
            result = dict(previous)
            result.update({
                'status': 'GREEN',
                'ok': True,
                'runtime_fingerprint': expected,
                'side_effect_state': 'PROVEN_BY_READBACK',
                'finished_at': datetime.now(timezone.utc).isoformat(),
                'retry_allowed': False,
            })
            return self._write_native_result(result)
        return previous

    def reload_native_mcp(self) -> dict:
        request_path = self.inbox / 'control_plane' / 'requests' / 'native_mcp_reload.json'
        request_probe = _load_json(request_path)
        if request_probe.get('schema') == 'energie_control_plane_release_request_v1':
            request, _controller_state = authorize_release_native_request(
                request_path=request_path,
                controller_state_path=self.inbox / 'release_controller' / 'current.json',
                version_path=self.version_path,
                runtime_guard_path=self.inbox / 'native_mcp_runtime' / 'runtime_guard.json',
            )
            approval = None
        else:
            request, approval = load_control_plane_native_request(self.inbox, self.approved_queue)
        live_version = self.version_path.read_text(encoding='utf-8').strip()
        if str(request.get('release_version') or '').strip() != live_version:
            raise RuntimeError('control-plane native MCP request hoort niet bij actuele live release')
        self.docker.ping()
        if self.docker.inspect_container(MCP_CONTAINER) is None:
            raise RuntimeError('energie-filesystem-mcp ontbreekt')

        expected = str(request['expected_fingerprint']).lower()
        result_path = self.result_root / 'results' / 'native_mcp_reload.json'
        fenced = self._reconcile_fenced_native_attempt(request, result_path)
        if fenced is not None:
            return fenced

        # Persist the exact request fence BEFORE the side effect. A crash after
        # this write can only reconcile readback; it may never issue a second
        # automatic restart for the same request_id.
        attempt = {
            **_native_result_base(request, approval),
            'status': 'ATTEMPTING',
            'ok': False,
            'runtime_fingerprint': None,
            'restart_performed': False,
            'side_effect_state': 'FENCED_BEFORE_RESTART',
            'retry_allowed': False,
            'started_at': datetime.now(timezone.utc).isoformat(),
        }
        self._write_native_result(attempt)

        try:
            self.docker.restart_container(MCP_CONTAINER, timeout=30)
        except Exception as exc:
            failed = dict(attempt)
            failed.update({
                'status': 'RED',
                'error': f'{type(exc).__name__}:{exc}',
                'side_effect_state': 'RESTART_OUTCOME_UNKNOWN',
                'finished_at': datetime.now(timezone.utc).isoformat(),
            })
            return self._write_native_result(failed)

        attempt = dict(attempt)
        attempt.update({
            'restart_performed': True,
            'side_effect_state': 'RESTART_RETURNED',
        })
        self._write_native_result(attempt)

        try:
            proof = self._wait_json(
                self.runtime_evidence / 'native_mcp_runtime_fingerprint.json',
                lambda v: v.get('schema') in {'energie_native_mcp_runtime_v2', 'energie_native_mcp_runtime_v3'} and str(v.get('fingerprint') or '').lower() == expected,
                90.0,
            )
        except Exception as exc:
            failed = dict(attempt)
            failed.update({
                'status': 'RED',
                'error': f'{type(exc).__name__}:{exc}',
                'side_effect_state': 'RESTART_PERFORMED_UNPROVEN',
                'finished_at': datetime.now(timezone.utc).isoformat(),
            })
            return self._write_native_result(failed)

        result = dict(attempt)
        result.update({
            'status': 'GREEN',
            'ok': True,
            'runtime_fingerprint': str(proof.get('fingerprint') or '').lower(),
            'restart_performed': True,
            'side_effect_state': 'PROVEN',
            'finished_at': datetime.now(timezone.utc).isoformat(),
        })
        return self._write_native_result(result)

    def run_platformtest(self) -> dict:
        request = load_platformtest_request(self.inbox)
        request_id = str(request['request_id'])
        candidate = str(request['candidate_sha']).lower()
        container = f'energie-platformtest-{request_id[:12]}'
        result_path = self.result_root / 'results' / 'platformtest_run.json'
        attempt_path = self.result_root / 'results' / 'platformtest_attempt.json'

        self.docker.ping()
        image = self.docker.inspect_image(PLATFORMTEST_IMAGE)
        image_id = str(image.get('Id') or '').lower() if isinstance(image, dict) else ''
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', image_id):
            raise RuntimeError('platformtest lokale image heeft geen immutable digest identity')
        payload = platformtest_create_payload(self.host_project_root, request, image_id=image_id)
        existing = self.docker.inspect_container(container)
        attempt = _optional_json(attempt_path)
        expected_attempt = {
            'schema': 'energie_platformtest_attempt_v1',
            'request_id': request_id,
            'candidate_sha': candidate,
            'source_sha256': request['source_sha256'],
            'test_profile': PLATFORMTEST_PROFILE,
            'image_id': image_id,
        }
        if existing is not None:
            labels = existing.get('Config', {}).get('Labels', {}) if isinstance(existing, dict) else {}
            if any(attempt.get(key) != value for key, value in expected_attempt.items()):
                raise RuntimeError('platformtest bestaand container-attempt mismatch; fail-closed')
            if labels.get('com.energie.request_id') != request_id or labels.get('com.energie.source_sha256') != request['source_sha256']:
                raise RuntimeError('platformtest bestaand container identity mismatch; fail-closed')
        else:
            _atomic_json(attempt_path, {**expected_attempt, 'status': 'PREPARED', 'container': container})

        created = existing is not None
        logs = ''
        exit_code = None
        error = None
        cleanup_ok = False
        try:
            if existing is None:
                self.docker.create_container(container, payload)
                created = True
                _atomic_json(attempt_path, {**expected_attempt, 'status': 'CREATED', 'container': container})
                self.docker.start_container(container)
                _atomic_json(attempt_path, {**expected_attempt, 'status': 'RUNNING', 'container': container})
            deadline = time.monotonic() + PLATFORMTEST_TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                self._write_runtime_marker()
                info = self.docker.inspect_container(container)
                if not isinstance(info, dict):
                    raise RuntimeError('platformtest container verdween voor readback')
                state = info.get('State') if isinstance(info.get('State'), dict) else {}
                if state.get('Running') is not True:
                    exit_code = int(state.get('ExitCode') if state.get('ExitCode') is not None else -1)
                    break
                time.sleep(1.0)
            else:
                error = 'platformtest timeout'
            try:
                logs = self.docker.container_logs(container)
            except Exception as exc:
                if error is None:
                    error = f'platformtest logs readback failed: {type(exc).__name__}:{exc}'
        except Exception as exc:
            error = f'{type(exc).__name__}:{exc}'
        finally:
            if created:
                try:
                    self.docker.remove_container(container, force=True)
                    cleanup_ok = True
                except Exception as exc:
                    cleanup_ok = False
                    if error is None:
                        error = f'platformtest cleanup failed: {type(exc).__name__}:{exc}'

        ok = exit_code == 0 and error is None and cleanup_ok
        result = {
            'schema': PLATFORMTEST_RESULT_SCHEMA,
            'action': 'platformtest_run',
            'request_id': request_id,
            'candidate_sha': candidate,
            'source_sha256': request['source_sha256'],
            'test_profile': PLATFORMTEST_PROFILE,
            'image': PLATFORMTEST_IMAGE,
            'image_id': image_id,
            'container': container,
            'network_mode': 'none',
            'exit_code': exit_code,
            'test_counts': _pytest_counts(logs),
            'logs_sha256': hashlib.sha256(logs.encode('utf-8', errors='replace')).hexdigest(),
            'production_modified': False,
            'container_removed': cleanup_ok,
            'status': 'GREEN' if ok else 'RED',
            'ok': ok,
            'error': error,
            'finished_at': datetime.now(timezone.utc).isoformat(),
        }
        _atomic_json(result_path, result)
        try:
            attempt_path.unlink(missing_ok=True)
        except OSError:
            pass
        return result

    def _write_runtime_marker(self) -> None:
        now = time.time()
        _atomic_json(self.inbox / 'control_plane' / 'runtime.json', {
            'schema': 'energie_control_plane_runtime_v1',
            'loaded_fingerprint': LOADED_RUNTIME_FINGERPRINT,
            'loaded_files': list(RUNTIME_FINGERPRINT_FILES),
            'pid': os.getpid(),
            'heartbeat_at_epoch': now,
            'heartbeat_at': datetime.now(timezone.utc).isoformat(),
        })

    def process_once(self):
        self._write_runtime_marker()
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
                request = _load_json(native_request)
                request_id = str(request.get('request_id') or '')
                native_result = self.result_root / 'results' / 'native_mcp_reload.json'
                request_release = str(request.get('release_version') or '').strip()
                live_release = self.version_path.read_text(encoding='utf-8').strip()
                if request_release and request_release != live_release:
                    # A request from a previous release is inert. Do not let it
                    # generate fresh approval errors for the current release.
                    # Preserve any prior GREEN proof, but remove stale RED/noise.
                    try:
                        prior = _load_json(native_result)
                    except Exception:
                        prior = None
                    if not (isinstance(prior, dict) and prior.get('status') == 'GREEN' and prior.get('ok') is True):
                        native_result.unlink(missing_ok=True)
                elif not already_completed(native_result, request_id):
                    previous = _optional_json(native_result)
                    if (
                        str(previous.get('request_id') or '') == request_id
                        and previous.get('retry_allowed') is False
                    ):
                        if request.get('schema') == 'energie_control_plane_release_request_v1':
                            authorize_release_native_reconcile(
                                request_path=native_request,
                                controller_state_path=self.inbox / 'release_controller' / 'current.json',
                                version_path=self.version_path,
                                runtime_guard_path=self.inbox / 'native_mcp_runtime' / 'runtime_guard.json',
                            )
                        reconciled = self._reconcile_fenced_native_attempt(request, native_result)
                        if isinstance(reconciled, dict) and reconciled.get('status') == 'GREEN':
                            results.append(reconciled)
                    else:
                        results.append(self.reload_native_mcp())
            except RuntimeError as exc:
                native_result = self.result_root / 'results' / 'native_mcp_reload.json'
                request_now = _optional_json(native_request)
                previous = _optional_json(native_result)
                if (
                    str(previous.get('request_id') or '')
                    and str(previous.get('request_id') or '') == str(request_now.get('request_id') or '')
                    and previous.get('retry_allowed') is False
                ):
                    # Preserve the durable side-effect fence. An authorization
                    # failure may annotate it, but must never reopen/retry it.
                    preserved = dict(previous)
                    preserved['reconcile_error'] = str(exc)
                    self._write_native_result(preserved)
                else:
                    _atomic_json(native_result, {
                        'schema':'energie_control_plane_result_v1','action':'native_mcp_reload',
                        'status':'RED','ok':False,'error':str(exc)
                    })
        platformtest_request = self.inbox / 'control_plane' / 'requests' / 'platformtest_run.json'
        if platformtest_request.is_file() and not platformtest_request.is_symlink():
            platformtest_result = self.result_root / 'results' / 'platformtest_run.json'
            request_probe = _optional_json(platformtest_request)
            request_id = str(request_probe.get('request_id') or '')
            if request_id and not terminal_result(platformtest_result, request_probe):
                try:
                    results.append(self.run_platformtest())
                except RuntimeError as exc:
                    _atomic_json(platformtest_result, {
                        'schema': PLATFORMTEST_RESULT_SCHEMA,
                        'action': 'platformtest_run',
                        'request_id': request_id,
                        'candidate_sha': str(request_probe.get('candidate_sha') or '').lower(),
                        'test_profile': str(request_probe.get('test_profile') or ''),
                        'network_mode': 'none',
                        'production_modified': False,
                        'status': 'RED',
                        'ok': False,
                        'error': str(exc),
                        'finished_at': datetime.now(timezone.utc).isoformat(),
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
