from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
import types
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
HOTFIX = ROOT / 'tools/native_mcp_runtime_contract_hotfix.py'


def _load_hotfix():
    import importlib.util
    spec = importlib.util.spec_from_file_location('hotfix_32513', HOTFIX)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _MCP:
    def __init__(self):
        self.routes = {}

    def custom_route(self, path, methods, name=None, include_in_schema=True):
        def deco(fn):
            self.routes[path] = {
                'fn': fn,
                'methods': list(methods),
                'include_in_schema': include_in_schema,
            }
            return fn
        return deco


class _Request:
    def __init__(self, params):
        self.query_params = params


def _zip(path: Path, cid: str, payload: bytes = b'payload') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        'schema': 'energie_clearup_type2_recovery_v1',
        'classification': 'TYPE2',
        'clearup_id': cid,
        'deletion_performed': False,
        'items': [{'source_rows': []}],
        'plan_sha256': 'a' * 64,
    }
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('TYPE2_MANIFEST.json', json.dumps(manifest))
        z.writestr('payload.bin', payload)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _install_fake_export_module(system: Path):
    m = types.ModuleType('tools_clearup_export')

    def info(cid: str):
        if cid not in {f'ClearUp_{i:03d}' for i in range(2, 13)}:
            raise ValueError('unsupported Type2 clearup_id')
        path = system / 'Projectmanager/ClearUp/Exports' / f'{cid}_Type2_recovery.zip'
        if not path.is_file() or path.is_symlink():
            raise ValueError('missing')
        with zipfile.ZipFile(path) as z:
            if z.testzip() is not None:
                raise ValueError('corrupt')
            manifest = json.loads(z.read('TYPE2_MANIFEST.json'))
            if manifest.get('clearup_id') != cid or manifest.get('classification') != 'TYPE2':
                raise ValueError('identity')
            if manifest.get('deletion_performed') is not False:
                raise ValueError('not pre-delete')
        return {
            'status': 'GREEN',
            'clearup_id': cid,
            'artifact': path.name,
            'size': path.stat().st_size,
            'sha256': _sha(path),
            'plan_sha256': str(manifest.get('plan_sha256') or ''),
            'item_count': len(manifest.get('items') or []),
            'deletion_performed': False,
        }

    m.clearup_type2_recovery_export_info = info
    sys.modules['tools_clearup_export'] = m
    return m


def test_32513_reuses_existing_status_tool_and_existing_clearup_exports_path():
    hotfix = _load_hotfix()
    src = hotfix.TYPE2_DOWNLOAD_BRIDGE_BLOCK
    assert 'Projectmanager/ClearUp/Exports' in src
    assert 'TYPE2_EXTERNAL_RECOVERY_GATE.json' in src
    assert 'from tools_clearup_export import clearup_type2_recovery_export_info' in src
    assert '@mcp.tool' not in src
    assert 'mcp.custom_route' in src
    lowered = src.lower()
    for forbidden in ('unlink(', 'rmtree(', 'os.remove(', 'os.replace(', 'shutil.move(', 'shutil.rmtree('):
        assert forbidden not in lowered

    current = '''from pathlib import Path\nimport json, os\nfrom typing import Any\nfrom registry import mcp\nclass ProjectmanagerAPI: pass\n\ndef _api() -> ProjectmanagerAPI:\n    return object()\n\n@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)\ndef projectmanager_status() -> dict[str, Any]:\n    return _api().status()\n'''
    patched, changed, reason = hotfix._ensure_type2_download_bridge(current)
    assert changed is True and reason == 'type2_download_bridge_added'
    assert hotfix.TYPE2_DOWNLOAD_BRIDGE_MARKER in patched
    assert 'return _attach_type2_recovery_downloads(_api().status())' in patched
    assert 'def projectmanager_status()' in patched


def test_32513_status_emits_signed_links_and_route_streams_exact_existing_zip(tmp_path, monkeypatch):
    hotfix = _load_hotfix()
    project = tmp_path / 'project'
    system = tmp_path / 'system'
    exports = system / 'Projectmanager/ClearUp/Exports'
    state = system / 'Projectmanager/ClearUp/State'
    project.mkdir(); state.mkdir(parents=True)

    compose = project / 'Infra/docker-compose.yml'
    compose.parent.mkdir(parents=True)
    compose.write_text('''services:\n  ngrok:\n    command:\n    - http\n    - 127.0.0.1:8000\n    - --url\n    - https://existing-energy.example\n''')

    required = []
    for i in range(2, 13):
        cid = f'ClearUp_{i:03d}'
        name = f'{cid}_Type2_recovery.zip'
        required.append(name)
        _zip(exports / name, cid, payload=f'{cid}-payload'.encode())
    gate = {
        'status': 'BLOCK_DELETE_UNTIL_EXTERNAL_COPY_CONFIRMED',
        'delete_allowed': False,
        'required_exports': required,
    }
    (state / 'TYPE2_EXTERNAL_RECOVERY_GATE.json').write_text(json.dumps(gate))

    monkeypatch.setenv('ENERGIE_SYSTEM_ROOT', str(system))
    monkeypatch.setenv('ENERGIE_ROOT', str(project))
    _install_fake_export_module(system)
    mcp = _MCP()
    ns = {'Path': Path, 'os': os, 'json': json, 'Any': Any, 'mcp': mcp}
    exec(hotfix.TYPE2_DOWNLOAD_BRIDGE_BLOCK, ns)

    before = sorted(p.relative_to(system).as_posix() for p in system.rglob('*'))
    enriched = ns['_attach_type2_recovery_downloads']({'status': 'COMPLETE'})
    bundle = enriched['type2_external_recovery']
    assert bundle['delete_allowed'] is False
    assert bundle['exports_root'] == 'Data/03_Systeem/Projectmanager/ClearUp/Exports'
    assert len(bundle['downloads']) == 11
    first = bundle['downloads'][0]
    assert first['clearup_id'] == 'ClearUp_002'
    assert first['download_url'].startswith('https://existing-energy.example/clearup/type2/download?')
    assert first['sha256'] == _sha(exports / first['artifact'])

    parsed = urlparse(first['download_url'])
    params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    route = mcp.routes['/clearup/type2/download']
    assert route['methods'] == ['GET'] and route['include_in_schema'] is False
    response = asyncio.run(route['fn'](_Request(params)))
    assert response.status_code == 200
    assert Path(response.path).read_bytes() == (exports / first['artifact']).read_bytes()
    assert response.headers['cache-control'] == 'no-store'
    assert 'attachment' in response.headers['content-disposition'].lower()

    bad = dict(params); bad['signature'] = '0' * 64
    response_bad = asyncio.run(route['fn'](_Request(bad)))
    assert response_bad.status_code == 403

    expired = dict(params); expired['expires'] = '1'
    expired['signature'] = ns['_type2_signature'](expired['clearup_id'], 1, expired['sha256'])
    response_expired = asyncio.run(route['fn'](_Request(expired)))
    assert response_expired.status_code == 403

    unknown = dict(params); unknown['clearup_id'] = 'ClearUp_013'
    response_unknown = asyncio.run(route['fn'](_Request(unknown)))
    assert response_unknown.status_code == 404

    # Exact file identity is bound into the link. Replacement after issuance is refused.
    _zip(exports / first['artifact'], 'ClearUp_002', payload=b'changed-after-link')
    response_changed = asyncio.run(route['fn'](_Request(params)))
    assert response_changed.status_code == 409

    after = sorted(p.relative_to(system).as_posix() for p in system.rglob('*'))
    assert before == after


def test_32513_download_bridge_is_fail_closed_when_external_gate_is_not_exact(tmp_path, monkeypatch):
    hotfix = _load_hotfix()
    project = tmp_path / 'project'; project.mkdir()
    system = tmp_path / 'system'; (system / 'Projectmanager/ClearUp/State').mkdir(parents=True)
    monkeypatch.setenv('ENERGIE_SYSTEM_ROOT', str(system))
    monkeypatch.setenv('ENERGIE_ROOT', str(project))
    mcp = _MCP()
    ns = {'Path': Path, 'os': os, 'json': json, 'Any': Any, 'mcp': mcp}
    exec(hotfix.TYPE2_DOWNLOAD_BRIDGE_BLOCK, ns)
    payload = {'status': 'COMPLETE'}
    assert ns['_attach_type2_recovery_downloads'](payload) == payload
    (system / 'Projectmanager/ClearUp/State/TYPE2_EXTERNAL_RECOVERY_GATE.json').write_text(json.dumps({
        'status': 'BLOCK_DELETE_UNTIL_EXTERNAL_COPY_CONFIRMED',
        'delete_allowed': True,
        'required_exports': [f'ClearUp_{i:03d}_Type2_recovery.zip' for i in range(2,13)],
    }))
    assert ns['_attach_type2_recovery_downloads'](payload) == payload
