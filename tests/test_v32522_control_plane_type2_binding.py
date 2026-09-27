from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
CP_DIR = TOOLS / 'control_plane'
for p in (str(TOOLS), str(CP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import control_plane_bootstrap as bootstrap


def _activate(root: Path, key: str, destination: str) -> None:
    dest = root / destination
    dest.mkdir(parents=True, exist_ok=True)
    marker = root / 'Data/03_Systeem/Projectmanager/ClearUp/PathActivation' / f'{key}.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        'schema': 'energie_clearup_system_path_contract_v1',
        'key': key,
        'active': True,
        'destination': destination,
    }) + '\n', encoding='utf-8')


def _container_info(*, canonical: bool) -> dict:
    cmd = ['python3', '/control-plane/qnap_control_plane_bootstrap.py', '--inbox', '/energy-inbox']
    binds = ['/share/Energie_NAS/EnergieProject/Inbox:/energy-inbox:rw']
    if canonical:
        cmd += [
            '--runtime-root', '/control-plane-runtime',
            '--security-root', '/control-plane-runtime',
            '--release-controller-root', '/release-controller',
            '--native-mcp-runtime-root', '/native-mcp-runtime',
        ]
        binds += [
            '/share/Energie_NAS/EnergieProject/Data/03_Systeem/Projectmanager/ControlPlane/Runtime:/control-plane-runtime:rw',
            '/share/Energie_NAS/EnergieProject/Data/03_Systeem/Projectmanager/ReleaseController:/release-controller:ro',
            '/share/Energie_NAS/EnergieProject/Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP:/native-mcp-runtime:ro',
        ]
    return {
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
        'Config': {'Cmd': cmd, 'Image': 'python:3.12-slim'},
        'HostConfig': {
            'Binds': binds,
            'NetworkMode': 'none',
            'ReadonlyRootfs': True,
            'CapDrop': ['ALL'],
            'CapAdd': ['DAC_OVERRIDE', 'DAC_READ_SEARCH', 'FOWNER'],
            'SecurityOpt': ['no-new-privileges'],
        },
    }


def test_type2_active_binding_rejects_legacy_control_plane_runtime(tmp_path):
    _activate(tmp_path, 'control_plane_runtime', 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime')
    assert bootstrap._binding_current(tmp_path, _container_info(canonical=False)) is False
    assert bootstrap._binding_current(tmp_path, _container_info(canonical=True)) is True


def test_bootstrap_recreates_legacy_binding_once_after_type2_activation(tmp_path, monkeypatch):
    _activate(tmp_path, 'control_plane_runtime', 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime')
    expected = 'b' * 64
    probes = iter([
        {'ready': False, 'reason': 'runtime_heartbeat_stale', 'expected_fingerprint': expected, 'loaded_fingerprint': expected},
        {'ready': True, 'reason': 'loaded_runtime_fingerprint_match', 'expected_fingerprint': expected, 'loaded_fingerprint': expected},
    ])
    monkeypatch.setattr(bootstrap, 'sync_control_plane_source', lambda root: {'changed': []})
    monkeypatch.setattr(bootstrap.control_plane_runtime_guard, 'probe', lambda root, stale_seconds=30: next(probes))

    current = {'canonical': False}
    calls: list[tuple[str, str, dict | None]] = []

    def fake_request(method, path, ok, payload=None):
        calls.append((method, path, payload))
        if method == 'GET':
            return _container_info(canonical=current['canonical'])
        if method == 'POST' and path.startswith('/containers/create?name=energie-control-plane'):
            assert payload is not None
            assert payload['Cmd'][payload['Cmd'].index('--runtime-root') + 1] == '/control-plane-runtime'
            assert payload['Cmd'][payload['Cmd'].index('--security-root') + 1] == '/control-plane-runtime'
            assert any(str(x).endswith(':/control-plane-runtime:rw') for x in payload['HostConfig']['Binds'])
            assert set(payload['HostConfig']['CapAdd']) == {'DAC_OVERRIDE', 'DAC_READ_SEARCH', 'FOWNER'}
            current['canonical'] = True
            return {'Id': 'new'}
        return {}

    monkeypatch.setattr(bootstrap, '_request', fake_request)
    result = bootstrap.ensure_control_plane_current(tmp_path, timeout_seconds=2)
    assert result['status'] == 'GREEN'
    assert result['recreate_performed'] is True
    assert result['restart_performed'] is False
    assert result['binding_current'] is True
    assert sum(1 for method, path, _ in calls if method == 'POST' and path.startswith('/containers/create?name=')) == 1
    assert not (tmp_path / 'Inbox/release_controller/control_plane_restart_attempt.json').exists()


def test_qnap_bootstrap_writes_security_marker_to_canonical_release_controller(tmp_path):
    spec = importlib.util.spec_from_file_location('qnap_control_plane_bootstrap_v32522', CP_DIR / 'qnap_control_plane_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    inbox = tmp_path / 'Inbox'
    canonical = tmp_path / 'Data/03_Systeem/Projectmanager/ReleaseController'
    inbox.mkdir(parents=True)
    canonical.mkdir(parents=True)
    module._write_security_migration(inbox, canonical)
    assert (canonical / 'platformtest_security_migration_v1.json').is_file()
    assert not (inbox / 'release_controller/platformtest_security_migration_v1.json').exists()
