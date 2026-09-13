from __future__ import annotations

import hashlib
import inspect
import json
import re
import sys
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _minimal_nas_project(tmp_path: Path, version: str = '32.4.36') -> Path:
    root = tmp_path / 'EnergieProject'
    (root / 'App').mkdir(parents=True)
    (root / 'Infra/Docker').mkdir(parents=True)
    (root / 'Backups/NAS Container').mkdir(parents=True)
    (root / 'Inbox/nas_container_cr_local').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text(version + '\n', encoding='utf-8')
    (root / 'Infra/docker-compose.yml').write_text('services: {}\n', encoding='utf-8')
    (root / 'Infra/Docker/Energie.env').write_text('SECRET=test\n', encoding='utf-8')
    return root


def _write_nas_set(target: Path, stem: str, *, marker: str = 'NAS_CR_RETENTION_MAX1_OK'):
    z = target / f'{stem}.zip'
    with zipfile.ZipFile(z, 'w') as archive:
        archive.writestr('ok.txt', 'ok')
    digest = hashlib.sha256(z.read_bytes()).hexdigest()
    (target / f'{stem}.zip.sha256').write_text(f'{digest}  {z.name}\n', encoding='utf-8')
    (target / f'{stem} VERIFY.txt').write_text(
        'NAS_CONTAINER_CR_ACCEPTANCE_OK\nPRODUCTION_CONTAINERS_CHANGED=NO\n' + marker + '\n',
        encoding='utf-8',
    )
    return z


def test_nas_cr_name_contains_runtime_version_and_max1_marker():
    source = (PM / 'nas_container_cr_service.py').read_text(encoding='utf-8')
    assert "CR NAS Containers" in source
    assert "NAS_CR_RETENTION_MAX1_OK" in source
    assert "NAS_CR_RETENTION_KEEP1_OK" not in source


def test_nas_retention_discovers_legacy_and_canonical_names(tmp_path):
    from nas_container_cr_service import NasContainerCrService

    class Docker:
        pass

    root = _minimal_nas_project(tmp_path)
    service = NasContainerCrService(root, Docker())
    target = root / 'Backups/NAS Container'
    legacy = '2026-09-04 12.29 CrashRecovery NAS Containers'
    canonical = '2026-09-10 19.58 32.4.35 CR NAS Containers'
    _write_nas_set(target, legacy)
    _write_nas_set(target, canonical)
    assert {p.name for p in service._retention_zip_candidates()} == {legacy + '.zip', canonical + '.zip'}


def test_active_configured_service_is_fixed_local_bridge_not_tls():
    from nas_container_cr_service import ConfiguredNasContainerCrService

    sig = inspect.signature(ConfiguredNasContainerCrService.__init__)
    assert 'private_root' not in sig.parameters
    source = inspect.getsource(ConfiguredNasContainerCrService)
    assert 'nas_docker_tls' not in source
    assert 'docker_engine_tls_client' not in source
    assert "Inbox" in source and "nas_container_cr_local" in source


def test_local_bridge_uses_matching_request_id_and_ignores_stale_result(tmp_path):
    from nas_container_cr_service import ConfiguredNasContainerCrService

    root = _minimal_nas_project(tmp_path)
    bridge = root / 'Inbox/nas_container_cr_local'
    service = ConfiguredNasContainerCrService(root, timeout_seconds=2.0, poll_seconds=0.01)

    def responder():
        request_path = bridge / 'request.json'
        deadline = time.monotonic() + 1.0
        while not request_path.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        request = json.loads(request_path.read_text(encoding='utf-8'))
        (bridge / 'result.json').write_text(json.dumps({
            'schema': 'energie_nas_container_cr_local_result_v1',
            'request_id': '0' * 32,
            'status': 'GREEN', 'ok': True,
            'production_containers_changed': False,
            'version': '32.4.36',
        }), encoding='utf-8')
        time.sleep(0.03)
        (bridge / 'result.json').write_text(json.dumps({
            'schema': 'energie_nas_container_cr_local_result_v1',
            'request_id': request['request_id'],
            'status': 'GREEN', 'ok': True,
            'production_containers_changed': False,
            'version': '32.4.36',
            'backup_dir': 'Backups/NAS Container',
        }), encoding='utf-8')

    thread = threading.Thread(target=responder, daemon=True)
    thread.start()
    result = service.create()
    thread.join(timeout=1)
    request = json.loads((bridge / 'request.json').read_text(encoding='utf-8'))
    assert request['schema'] == 'energie_nas_container_cr_local_request_v1'
    assert request['operation'] == 'nas_container_cr_create'
    assert re.fullmatch(r'[0-9a-f]{32}', request['request_id'])
    assert request['expected_runtime_version'] == '32.4.36'
    assert result['status'] == 'GREEN' and result['ok'] is True


def test_docker_unix_client_public_surface_is_narrow():
    import docker_engine_unix_client as mod

    public = {
        name for name, value in vars(mod.DockerEngineUnixClient).items()
        if callable(value) and not name.startswith('_')
    }
    assert public == {
        'ping', 'container_inspect', 'image_inspect', 'image_export',
        'container_create_probe', 'container_remove_probe',
    }
    source = inspect.getsource(mod.DockerEngineUnixClient)
    for forbidden in ('def exec', 'def start', 'def stop', 'def restart', 'def pull'):
        assert forbidden not in source


def test_docker_unix_client_rejects_non_probe_container_name():
    import docker_engine_unix_client as mod

    client = mod.DockerEngineUnixClient()
    with pytest.raises(ValueError, match='nas-cr-probe'):
        client.container_create_probe('python:3.12-slim', 'production-container')
    with pytest.raises(ValueError, match='nas-cr-probe'):
        client.container_remove_probe('production-container')


def test_projectmanager_panel_uses_local_capability_and_no_certificate_route(tmp_path):
    import projectmanager_web as web

    root = _minimal_nas_project(tmp_path)
    capability = root / 'Inbox/nas_container_cr_local/capability.json'
    capability.write_text(json.dumps({'ready': True, 'status': 'GREEN', 'version': '32.4.36'}), encoding='utf-8')
    html = web.render_nas_container_cr_setup(root)
    assert 'NAS Container Crash Recovery' in html
    assert 'Gereed' in html
    for forbidden in ('certificate_bundle', '2376', 'Activeer ChatGPT-koppeling', 'Docker-certificaat'):
        assert forbidden not in html


def test_web_post_handler_does_not_accept_tls_setup_or_activation():
    import projectmanager_web as web

    source = inspect.getsource(web.install_projectmanager_web)
    assert 'projectmanager-nas-cr-setup' not in source
    assert 'projectmanager-nas-cr-activate' not in source
    assert 'certificate_bundle' not in source


def test_active_orchestrator_has_no_tls_dependency():
    import orchestrator

    source = inspect.getsource(orchestrator.ProjectmanagerRuntime.__init__)
    assert 'nas_docker_tls_root' not in source
    assert 'private_root' not in source
    assert 'ConfiguredNasContainerCrService(config.project_root)' in source


def test_watcher_bootstrap_has_local_socket_hardening_and_minimum_fs_caps():
    source = (ROOT / 'tools/bootstrap_release_watcher_container.sh').read_text(encoding='utf-8')
    for token in (
        '--network none', '--cap-drop ALL', '--security-opt no-new-privileges',
        '/var/run/docker.sock:/var/run/docker.sock',
        '--cap-add DAC_OVERRIDE', '--cap-add DAC_READ_SEARCH', '--cap-add FOWNER',
        'nas_container_cr_local/capability.json',
    ):
        assert token in source
    assert '--privileged' not in source


def test_watcher_runs_cr_hotfix_before_local_nas_request_and_probes_capability():
    source = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    for token in ('process_cr_standard_hotfix', 'process_nas_cr_capability_probe', 'process_nas_container_cr_local'):
        assert token in source
    assert source.index('process_cr_standard_hotfix') < source.index('process_nas_container_cr_local')
    startup = source[source.index('Release watcher gestart'):source.index('while :; do')]
    assert 'process_nas_cr_capability_probe' in startup
    assert '1200' in source


def test_local_executor_has_fixed_contract_without_generic_shell_surface():
    path = ROOT / 'tools/nas_cr_local_executor.py'
    source = path.read_text(encoding='utf-8')
    assert 'energie_nas_container_cr_local_request_v1' in source
    assert 'nas_container_cr_create' in source
    assert 'Inbox/nas_container_cr_local' in source or "'Inbox' / 'nas_container_cr_local'" in source
    assert 'shell=True' not in source
    assert '--command' not in source
    assert '--request' not in source
    assert '--result' not in source


def test_capability_probe_only_marks_ready_after_real_local_ping():
    path = ROOT / 'tools/nas_cr_local_probe.py'
    source = path.read_text(encoding='utf-8')
    assert 'capability.json' in source
    assert 'DockerEngineUnixClient' in source
    assert '.ping()' in source
    assert "'ready': True" in source or '"ready": True' in source
    assert '2376' not in source


def _health_check_by_name(root: Path, now: datetime, name: str):
    from projectmanager_v2.energy_health_collector import EnergyHealthCollector

    input_root = root / 'Data/01_Input'
    recovery_root = root / 'Backups'
    input_root.mkdir(parents=True, exist_ok=True)
    recovery_root.mkdir(parents=True, exist_ok=True)
    checks = EnergyHealthCollector(root, input_root, recovery_root).collect(now=now)
    return next(item for item in checks if item['name'] == name)


def test_health_rejects_legacy_project_cr_and_accepts_one_canonical_complete_set(tmp_path):
    root = _minimal_nas_project(tmp_path)
    cr = root / 'Backups/CrashRecovery'
    cr.mkdir(parents=True)
    now = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)

    legacy = cr / '2026-09-10 19.13 CrashRecovery EnergieProject.zip'
    legacy.write_bytes(b'legacy')
    for suffix in ('.sha256', '.manifest.json', '.restore.txt'):
        Path(str(legacy.with_suffix('')) + suffix).write_text('x', encoding='utf-8')
    assert _health_check_by_name(root, now, 'project_crash_recovery_set')['status'] == 'ORANGE'

    legacy.unlink()
    for suffix in ('.sha256', '.manifest.json', '.restore.txt'):
        Path(str(legacy.with_suffix('')) + suffix).unlink()
    z = cr / '2026-09-10 21.00 32.4.36 CR EnergieProject.zip'
    z.write_bytes(b'canonical')
    digest = hashlib.sha256(z.read_bytes()).hexdigest()
    stem = z.with_suffix('')
    Path(str(stem) + '.sha256').write_text(f'{digest}  {z.name}\n', encoding='utf-8')
    Path(str(stem) + '.manifest.json').write_text('{}\n', encoding='utf-8')
    Path(str(stem) + '.restore.txt').write_text('restore\n', encoding='utf-8')
    assert _health_check_by_name(root, now, 'project_crash_recovery_set')['status'] == 'GREEN'


def test_health_nas_requires_canonical_name_acceptance_unchanged_and_max1(tmp_path):
    root = _minimal_nas_project(tmp_path)
    nas = root / 'Backups/NAS Container'
    z = _write_nas_set(nas, '2026-09-10 21.00 32.4.36 CR NAS Containers')
    now = datetime(2026, 9, 10, 20, 0, tzinfo=timezone.utc)
    check = _health_check_by_name(root, now, 'nas_container_crash_recovery_retention')
    assert check['status'] == 'GREEN'
    _write_nas_set(nas, '2026-09-09 21.00 32.4.35 CR NAS Containers')
    check = _health_check_by_name(root, now, 'nas_container_crash_recovery_retention')
    assert check['status'] == 'ORANGE'
    assert check['details']['zip_count'] == 2
    assert z.is_file()


def test_stale_clearup_plan_is_reaudited_once_and_only_fresh_plan_is_applied(tmp_path, monkeypatch):
    import project_clearup_auto as auto

    monkeypatch.setattr(auto, 'clearup_auto_gate', lambda *a, **k: {'ready': True})
    plans = iter([
        {'plan_id': 'stale', 'clearup_count': 1, 'review_count': 0},
        {'plan_id': 'fresh', 'clearup_count': 1, 'review_count': 0},
    ])
    build_calls = []
    monkeypatch.setattr(auto, 'build_clearup_plan', lambda *a, **k: build_calls.append(1) or next(plans))
    applied = []

    def apply(*args, **kwargs):
        plan = args[1]
        applied.append(plan['plan_id'])
        if plan['plan_id'] == 'stale':
            raise RuntimeError('CLEARUP-plan is gewijzigd; nieuwe dependency-audit vereist.')
        return {'status': 'completed', 'delete_performed': False}

    progress = []
    monkeypatch.setattr(auto, '_apply_clearup_via_watcher', apply)
    result = auto.run_approved_clearup_once(
        tmp_path, app_version='32.4.36', timeout_seconds=10,
        progress_callback=lambda item: progress.append(item),
    )
    assert len(build_calls) == 2
    assert applied == ['stale', 'fresh']
    assert result['plan_id'] == 'fresh'
    assert result['stale_plan_id'] == 'stale'
    assert result['replanned_after_stale'] is True
    assert any(item.get('phase') == 'fresh_dependency_audit' for item in progress)
    assert result['delete_performed'] is False


def test_native_mcp_hotfix_is_bounded_to_five_known_targets_and_no_restart():
    path = ROOT / 'tools/cr_standard_native_mcp_hotfix.py'
    source = path.read_text(encoding='utf-8')
    for rel in (
        'Infra/Docker/native-mcp/crash_recovery.py',
        'Infra/Docker/native-mcp/tools_recovery.py',
        'Infra/Docker/native-mcp/build_nas_container_crash_recovery.sh',
        'Infra/Docker/native-mcp/nas_cr_keep1_retention.sh',
        'Infra/Docker/native-mcp/tests/test_crash_recovery_filename_standard.py',
    ):
        assert rel in source
    assert 'Backups/MCPHotfix/v32.4.38' in source
    assert 'mcp_restart_required' in source
    assert 'docker restart' not in source
    assert 'NAS_CR_RETENTION_MAX1_OK' in source
    assert 'PRODUCTION_CONTAINERS_CHANGED=NO' in source
    assert ' CR EnergieProject' in source


def test_32436_release_identity_is_consistent():
    import release_test_contract as contract

    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == contract.CURRENT_RELEASE
    assert contract.CURRENT_RELEASE == '32.4.49'
    assert contract.CURRENT_PM_VERSION == '2.0.0-rc36'
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == contract.CURRENT_PM_VERSION
    assert f'version: "{contract.CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert f'APP_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert f'TARGET_RELEASE_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
