from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
CP_DIR = TOOLS / 'control_plane'
for p in (str(TOOLS), str(CP_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import control_plane_binding_recreate as recreate


def test_v32524_recreated_control_plane_keeps_release_controller_readonly_and_uses_runtime_security_root():
    payload = recreate._desired_container_payload('/share/Energie_NAS/EnergieProject')
    cmd = payload['Cmd']
    assert cmd[cmd.index('--release-controller-root') + 1] == '/release-controller'
    assert cmd[cmd.index('--security-root') + 1] == '/control-plane-runtime'
    binds = payload['HostConfig']['Binds']
    assert '/share/Energie_NAS/EnergieProject/Data/03_Systeem/Projectmanager/ReleaseController:/release-controller:ro' in binds
    assert '/share/Energie_NAS/EnergieProject/Data/03_Systeem/Projectmanager/ControlPlane/Runtime:/control-plane-runtime:rw' in binds
    assert not any(x.endswith(':/release-controller:rw') for x in binds)


def test_v32524_bootstrap_writes_security_marker_to_runtime_root_not_readonly_release_controller(tmp_path):
    spec = importlib.util.spec_from_file_location('qnap_control_plane_bootstrap_v32524', CP_DIR / 'qnap_control_plane_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    inbox = tmp_path / 'Inbox'
    release_root = tmp_path / 'Data/03_Systeem/Projectmanager/ReleaseController'
    runtime_root = tmp_path / 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime'
    inbox.mkdir(parents=True)
    release_root.mkdir(parents=True)
    runtime_root.mkdir(parents=True)

    module._ensure_control_plane_mailboxes(runtime_root, inbox, release_root, runtime_root)
    assert (runtime_root / 'platformtest_security_migration_v1.json').is_file()
    assert not (release_root / 'platformtest_security_migration_v1.json').exists()


def test_v32524_bootstrap_consumes_security_root_before_delegating_to_control_plane_parser(monkeypatch):
    spec = importlib.util.spec_from_file_location('qnap_control_plane_bootstrap_v32524_args', CP_DIR / 'qnap_control_plane_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys, 'argv', ['qnap_control_plane_bootstrap.py', '--inbox', '/energy-inbox', '--security-root', '/control-plane-runtime', '--interval', '2'])
    assert module._argv_value('--security-root', '') == '/control-plane-runtime'
    module._consume_argv_pair('--security-root')
    assert '--security-root' not in sys.argv
    assert '/control-plane-runtime' not in sys.argv
    assert sys.argv == ['qnap_control_plane_bootstrap.py', '--inbox', '/energy-inbox', '--interval', '2']


def test_v32524_existing_correct_mailbox_modes_do_not_require_chmod(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('qnap_control_plane_bootstrap_v32524_qnap_modes', CP_DIR / 'qnap_control_plane_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    inbox = tmp_path / 'Inbox'
    release_root = tmp_path / 'Data/03_Systeem/Projectmanager/ReleaseController'
    runtime_root = tmp_path / 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime'
    requests = runtime_root / 'requests'
    results = runtime_root / 'results'
    for path in (inbox, release_root, requests, results):
        path.mkdir(parents=True, exist_ok=True)
    runtime_root.chmod(0o755)
    requests.chmod(0o1733)
    results.chmod(0o755)

    real_chmod = module.os.chmod
    protected = {runtime_root.resolve(), requests.resolve(), results.resolve()}
    def qnap_chmod(path, mode):
        target = Path(path).resolve()
        if target in protected:
            raise PermissionError('simulated QNAP bind chmod refusal')
        return real_chmod(path, mode)
    monkeypatch.setattr(module.os, 'chmod', qnap_chmod)

    module._ensure_control_plane_mailboxes(runtime_root, inbox, release_root, runtime_root)
    assert (runtime_root / 'platformtest_security_migration_v1.json').is_file()


def test_v32524_existing_correct_stale_activation_mode_does_not_require_chmod(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('qnap_control_plane_bootstrap_v32524_qnap_stale', CP_DIR / 'qnap_control_plane_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    inbox = tmp_path / 'Inbox'
    release_root = tmp_path / 'Data/03_Systeem/Projectmanager/ReleaseController'
    runtime_root = tmp_path / 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime'
    requests = runtime_root / 'requests'
    results = runtime_root / 'results'
    stale = runtime_root / 'stale_activation'
    for path in (inbox, release_root, requests, results, stale):
        path.mkdir(parents=True, exist_ok=True)
    runtime_root.chmod(0o755)
    requests.chmod(0o1733)
    results.chmod(0o755)
    stale.chmod(0o700)

    real_chmod = module.os.chmod
    stale_resolved = stale.resolve()
    def qnap_chmod(path, mode):
        if Path(path).resolve() == stale_resolved:
            raise PermissionError('simulated QNAP stale_activation chmod refusal')
        return real_chmod(path, mode)
    monkeypatch.setattr(module.os, 'chmod', qnap_chmod)

    module._ensure_control_plane_mailboxes(runtime_root, inbox, release_root, runtime_root)
    assert stale.stat().st_mode & 0o7777 == 0o700


def test_v32524_binding_readback_rejects_missing_security_root_or_capability(tmp_path):
    import control_plane_bootstrap as bootstrap
    marker = tmp_path / 'Data/03_Systeem/Projectmanager/ClearUp/PathActivation/control_plane_runtime.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime').mkdir(parents=True, exist_ok=True)
    marker.write_text('{"schema":"energie_clearup_system_path_contract_v1","key":"control_plane_runtime","active":true,"destination":"Data/03_Systeem/Projectmanager/ControlPlane/Runtime"}\n', encoding='utf-8')

    payload = recreate._desired_container_payload('/share/Energie_NAS/EnergieProject')
    info = {
        'Config': {'Cmd': list(payload['Cmd']), 'Image': payload['Image']},
        'HostConfig': dict(payload['HostConfig']),
        'State': {'Running': True, 'Health': {'Status': 'healthy'}},
    }
    assert bootstrap._binding_current(tmp_path, info) is True

    no_security = {
        **info,
        'Config': {**info['Config'], 'Cmd': [x for i, x in enumerate(info['Config']['Cmd']) if i not in {info['Config']['Cmd'].index('--security-root'), info['Config']['Cmd'].index('--security-root') + 1}]},
    }
    assert bootstrap._binding_current(tmp_path, no_security) is False

    weak_caps = {**info, 'HostConfig': {**info['HostConfig'], 'CapAdd': ['DAC_OVERRIDE', 'DAC_READ_SEARCH']}}
    assert bootstrap._binding_current(tmp_path, weak_caps) is False


def test_v32524_compose_matches_recreate_security_and_capability_contract():
    compose = (CP_DIR / 'docker-compose.containerstation.yml').read_text(encoding='utf-8')
    assert '      - --security-root\n      - /control-plane-runtime\n' in compose
    assert '    cap_add:\n      - DAC_OVERRIDE\n      - DAC_READ_SEARCH\n      - FOWNER\n' in compose
    assert '/ReleaseController:/release-controller:ro' in compose
    assert '/ControlPlane/Runtime:/control-plane-runtime:rw' in compose
