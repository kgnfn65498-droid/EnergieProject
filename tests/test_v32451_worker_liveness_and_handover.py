import inspect
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _project_root(tmp_path, version='32.4.51'):
    (tmp_path / 'App').mkdir(parents=True)
    (tmp_path / 'App' / 'VERSIE.txt').write_text(version + '\n', encoding='utf-8')
    return tmp_path


def test_project_cr_bridge_is_nonblocking_and_reports_pending(tmp_path):
    from project_cr_service import ConfiguredProjectCrService

    root = _project_root(tmp_path)
    service = ConfiguredProjectCrService(root, timeout_seconds=0.01, poll_seconds=0.001)
    result = service.create(command_id='a' * 32, expected_release='32.4.51', wait_for_result=False)

    assert result['status'] == 'PENDING'
    assert result['ok'] is None
    assert result['command_id'] == 'a' * 32
    request = json.loads((root / 'Inbox/project_cr_local/request.json').read_text(encoding='utf-8'))
    assert request['command_id'] == 'a' * 32


def test_nas_cr_bridge_is_nonblocking_and_reports_pending(tmp_path):
    from nas_container_cr_service import ConfiguredNasContainerCrService

    root = _project_root(tmp_path)
    bridge = root / 'Inbox/nas_container_cr_local'
    bridge.mkdir(parents=True)
    bridge.chmod(0o777)
    service = ConfiguredNasContainerCrService(root, timeout_seconds=0.01, poll_seconds=0.001)
    result = service.create(command_id='b' * 32, expected_release='32.4.51', wait_for_result=False)

    assert result['status'] == 'PENDING'
    assert result['ok'] is None
    assert result['command_id'] == 'b' * 32


def test_command_processor_requeues_nonblocking_cr_instead_of_failing():
    from command_processor import CommandProcessor

    source = inspect.getsource(CommandProcessor.process_next)
    assert "result.get('status') == 'PENDING'" in source
    assert 'self.commands.requeue(' in source


def test_pm_lock_conflict_retries_instead_of_terminal_return():
    import projectmanager_v2_entrypoint as entry

    source = inspect.getsource(entry._worker)
    lock_branch = source.split("if 'lock already held' in str(exc):", 1)[1].split('raise', 1)[0]
    assert 'stop_event.wait' in lock_branch
    assert 'continue' in lock_branch
    assert lock_branch.index('stop_event.wait') < lock_branch.index('continue')


def test_periodic_mode_worker_runs_lifecycle_supervisor():
    import operating_mode_runtime as runtime

    signature = inspect.signature(runtime.operating_mode_worker)
    assert 'lifecycle_tick' in signature.parameters
    source = inspect.getsource(runtime.operating_mode_worker)
    assert 'lifecycle_tick' in source


def test_mode_entrypoint_supervises_pm_and_hold_workers():
    import mode_entrypoint as entry

    assert hasattr(entry, '_supervise_background_workers')
    source = inspect.getsource(entry._supervise_background_workers)
    assert 'start_projectmanager_v2' in source
    assert 'automatic_release_hold_worker' in source


def test_release_watcher_project_cr_is_detached_from_main_loop():
    source = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    fn = source.split('process_project_cr_local(){', 1)[1].split('\n}', 1)[0]
    assert 'project_cr_local_worker.pid' in source
    assert 'run_bounded "$PROJECT_CR_LOCAL_TIMEOUT" python3 "$PROJECT_CR_LOCAL_EXECUTOR"' in fn
    assert ') &' in fn
    assert 'kill -0 "$CR_PID"' in fn


def test_handover_carries_cross_chat_build_and_audit_contract():
    from handover import build_handover

    payload = build_handover(mode={'mode': 'DEVELOPMENT'}, release={'version': '32.4.51'})
    method = payload['development_method']
    assert method['builder'] == 'ChatGPT'
    assert method['codex_role'] == 'research_only'
    assert method['exact_previous_verified_zip_required'] is True
    audit = payload['audit_contract']
    assert audit['format'] == 'point. status_badge recurrence_count — description'
    assert audit['recurrence_counts_real_repair_rounds'] is True
    preflight = payload['new_chat_preflight']
    assert preflight['manual_reexplanation_required'] is False
    assert 'requirements' in preflight['required_context']


def test_32451_release_identity():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.54'
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == '2.0.0-rc41'
    assert 'TARGET_RELEASE_VERSION = "32.4.54"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.4.54"' in (APP / 'main.py').read_text(encoding='utf-8')


def test_release_health_fails_closed_when_pm_driver_liveness_is_stale():
    from release_health import release_health_checks

    runtime = {
        'release': {'version': '32.4.51'},
        'release_chain': {
            'watcher': {'active': True},
            'incoming': {'count': 0},
            'processing': {'stuck_count': 0},
            'installer_lock': {'active': False},
            'atomic_swap': {'exists': True, 'state': 'ACCEPTED'},
            'publisher': {'status': 'published', 'version': '32.4.51'},
            'github_publication': {'status': 'published', 'version': '32.4.51'},
        },
        'projectmanager_liveness': {'active': False, 'reason': 'manager_heartbeat_stale'},
    }
    checks = {item['name']: item for item in release_health_checks(runtime)}
    assert checks['projectmanager_driver_liveness']['status'] == 'RED'
    assert checks['projectmanager_driver_liveness']['reason'] == 'manager_heartbeat_stale'


def test_runtime_collector_exposes_projectmanager_liveness(tmp_path):
    from datetime import datetime, timezone
    from runtime_sources import RuntimeCollector

    project = _project_root(tmp_path)
    inbox = project / 'Inbox/projectmanager_v2/RuntimeV2/heartbeat'
    inbox.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    (inbox / 'manager.json').write_text(json.dumps({'heartbeat_at': now.isoformat()}), encoding='utf-8')
    runtime = RuntimeCollector(project, running_release_version='32.4.51', watcher_probe_seconds=0).collect(now=now)
    assert runtime['projectmanager_liveness']['active'] is True
    assert runtime['projectmanager_liveness']['reason'] == 'manager_heartbeat_fresh'


def test_release_recover_is_bounded_safe_command():
    from command_gateway import plan_command

    plan = plan_command({'intent': 'release_recover', 'source': 'chatgpt'})
    assert plan['action'] == 'release_recover'
    assert plan['allowed_without_approval'] is True


def test_release_recovery_quarantines_terminal_stale_project_cr_request(tmp_path):
    from release_recovery import ReleaseRecoveryService

    root = _project_root(tmp_path)
    bridge = root / 'Inbox/project_cr_local'
    bridge.mkdir(parents=True)
    request = {
        'schema': 'energie_project_cr_local_request_v1',
        'request_id': 'c' * 32,
        'operation': 'project_cr_create',
        'expected_runtime_version': '32.4.50',
        'command_id': 'd' * 32,
    }
    result = {
        'schema': 'energie_project_cr_local_result_v1',
        'request_id': 'c' * 32,
        'status': 'RED',
        'ok': False,
        'error': 'old terminal block',
    }
    (bridge / 'request.json').write_text(json.dumps(request), encoding='utf-8')
    (bridge / 'result.json').write_text(json.dumps(result), encoding='utf-8')
    recovery = ReleaseRecoveryService(root).recover()
    assert recovery['stale_project_cr_request_isolated'] is True
    assert not (bridge / 'request.json').exists()
    assert list((bridge / 'quarantine').glob('request-*.json'))


def test_release_recovery_reports_protected_watcher_recreate_when_heartbeat_missing(tmp_path):
    from release_recovery import ReleaseRecoveryService

    root = _project_root(tmp_path)
    (root / 'Inbox').mkdir(exist_ok=True)
    (root / 'Inbox/atomic_app_swap_state.json').write_text(json.dumps({'state': 'LIVE_ACCEPTANCE', 'to_version': '32.4.51'}), encoding='utf-8')
    recovery = ReleaseRecoveryService(root).recover()
    assert recovery['needs_watcher_recreate'] is True
    assert recovery['protected_action_required'] == 'watcher_recreate'


def test_handover_snapshot_carries_451_cross_chat_contract_fields():
    source = (PM / 'handover_snapshot.py').read_text(encoding='utf-8')
    assert "'development_method':" in source
    assert "'audit_contract':" in source
    assert "'new_chat_preflight':" in source
    orchestrator = (PM / 'orchestrator.py').read_text(encoding='utf-8')
    assert "HARD_REQUIREMENT_CHATGPT_BUILDS_CODEX_RESEARCH_ONLY.md" in orchestrator
    assert "HARD_REQUIREMENT_32451_COMPLETE_HANDOVER.md" in orchestrator


def test_release_hold_daemon_publishes_persistent_liveness(tmp_path, monkeypatch):
    import operating_mode_auto_release as auto

    root = _project_root(tmp_path)
    monkeypatch.setattr(auto, 'automatic_release_hold_worker', lambda *args, **kwargs: {'status': 'blocked', 'reason': 'waiting'})

    class StopAfterCycle:
        def wait(self, delay):
            return True

    result = auto.automatic_release_hold_daemon(
        StopAfterCycle(), object(), root, '32.4.51', retry_delays=(), cycle_delay=0.0
    )
    assert result['status'] == 'stopped'
    state_path = root / 'Inbox/operating_mode/release_hold_worker.json'
    state = json.loads(state_path.read_text(encoding='utf-8'))
    assert state['expected_version'] == '32.4.51'
    assert state['last_result']['status'] == 'blocked'
    assert state['status'] == 'stopped'
    assert state['heartbeat_at']


def test_runtime_and_health_expose_stale_hold_driver_during_live_acceptance(tmp_path):
    from datetime import datetime, timedelta, timezone
    from projectmanager_v2.runtime_sources import RuntimeCollector
    from projectmanager_v2.release_health import release_health_checks

    root = _project_root(tmp_path)
    inbox = root / 'Inbox'
    (inbox / 'operating_mode').mkdir(parents=True)
    (inbox / 'projectmanager_v2/RuntimeV2/heartbeat').mkdir(parents=True)
    now = datetime.now(timezone.utc)
    old = now - timedelta(minutes=10)
    (inbox / 'operating_mode/release_hold_worker.json').write_text(json.dumps({
        'heartbeat_at': old.isoformat(),
        'status': 'blocked',
        'expected_version': '32.4.51',
        'last_result': {'status': 'blocked'},
    }), encoding='utf-8')
    (inbox / 'projectmanager_v2/RuntimeV2/heartbeat/manager.json').write_text(json.dumps({
        'heartbeat_at': now.isoformat(), 'cycle_generation': 'g', 'provenance': 'FINAL'
    }), encoding='utf-8')
    (inbox / 'atomic_app_swap_state.json').write_text(json.dumps({
        'state': 'LIVE_ACCEPTANCE', 'to_version': '32.4.51'
    }), encoding='utf-8')
    runtime = RuntimeCollector(root, running_release_version='32.4.51', watcher_probe_seconds=0).collect(now=now)
    assert runtime['release_hold_driver_liveness']['active'] is False
    checks = {item['name']: item for item in release_health_checks(runtime)}
    assert checks['release_hold_driver_liveness']['status'] == 'RED'
    assert checks['release_hold_driver_liveness']['reason'] == 'release_hold_worker_stale'


def test_release_recover_reproduces_450_stuck_pattern_without_bypass(tmp_path):
    from release_recovery import ReleaseRecoveryService

    root = _project_root(tmp_path)
    inbox = root / 'Inbox'
    (inbox / 'operating_mode').mkdir(parents=True)
    (inbox / 'project_cr_local').mkdir(parents=True)
    (inbox / 'incoming').mkdir(parents=True)
    import time
    (inbox / 'watcher_heartbeat.v2').write_text(str(time.time()), encoding='utf-8')
    (inbox / 'atomic_app_swap_state.json').write_text(json.dumps({
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.50', 'to_version': '32.4.51'
    }), encoding='utf-8')
    (inbox / 'operating_mode/release_validation_hold.json').write_text(json.dumps({
        'active': True, 'release_version': '32.4.51', 'validation_status': 'blocked'
    }), encoding='utf-8')
    (inbox / 'operating_mode/operating_mode_state.json').write_text(json.dumps({
        'effective_mode': 'MAINTENANCE'
    }), encoding='utf-8')
    request_id = 'e' * 32
    (inbox / 'project_cr_local/request.json').write_text(json.dumps({
        'schema': 'energie_project_cr_local_request_v1',
        'request_id': request_id,
        'operation': 'project_cr_create',
        'expected_runtime_version': '32.4.50',
        'command_id': 'f' * 32,
    }), encoding='utf-8')
    (inbox / 'project_cr_local/result.json').write_text(json.dumps({
        'schema': 'energie_project_cr_local_result_v1',
        'request_id': request_id,
        'status': 'RED', 'ok': False,
    }), encoding='utf-8')
    (inbox / 'incoming/EnergieProject_v32.4.52.zip').write_bytes(b'placeholder')

    recovery = ReleaseRecoveryService(root).recover()
    assert recovery['stale_project_cr_request_isolated'] is True
    assert recovery['needs_development'] is True
    assert recovery['needs_hold_cycle'] is True
    assert recovery['needs_watcher_recreate'] is False
    assert recovery['protected_action_required'] is None
    assert recovery['canonical_release_route'].startswith('ZIP -> Incoming/Home Assistant -> watcher')
    assert (inbox / 'incoming/EnergieProject_v32.4.52.zip').exists()
