from __future__ import annotations

import importlib.util
import json
import sys
import pytest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for path in (APP, PM, TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))


def _old_canonical():
    return {
        'schema': 'energie_projectmanager_canonical_roadmap_v3',
        'version': 3,
        'approved_at': '2026-09-05',
        'approved_by': 'Peter',
        'source': 'baseline',
        'items': [
            {'key':'conversation-intake','title':'Conversation','status':'OPEN','depends_on':[]},
            {'key':'proactive-pm','title':'Proactive','status':'DONE','depends_on':['conversation-intake']},
            {'key':'nomad-next','title':'Nomad','status':'OPEN','depends_on':['proactive-pm']},
            {'key':'ngrok-assessment','title':'ngrok','status':'OPEN','depends_on':['nomad-next']},
            {'key':'subscription-independence','title':'Subscription','status':'OPEN','depends_on':['ngrok-assessment']},
            {'key':'cowork-pilot','title':'Cowork','status':'OPEN','depends_on':['subscription-independence']},
            {'key':'month-import-next','title':'Month','status':'OPEN','depends_on':['cowork-pilot']},
        ],
    }


def test_32439_four_core_scope_identity():
    import release_test_contract as contract
    assert (ROOT / 'VERSIE.txt').read_text().strip() == contract.CURRENT_RELEASE
    assert (PM / 'VERSION.txt').read_text().strip() == contract.CURRENT_PM_VERSION
    assert f'version: "{contract.CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    assert f'APP_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / 'main.py').read_text()
    assert f'TARGET_RELEASE_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text()


def test_watcher_red_is_actionable_request_not_dead_end():
    from series_324_live_closure import next_action
    checks = {
        'watcher_container_contract': 'RED', 'native_mcp_runtime': 'RED',
        'project_crash_recovery_set': 'ORANGE', 'nas_container_crash_recovery_retention': 'ORANGE',
        'project_structure_hygiene': 'ORANGE',
    }
    assert next_action(checks, clearup_done=False) == 'REQUEST_WATCHER_RECREATE'
    contract = (TOOLS / 'watcher_container_contract.py').read_text()
    host = (TOOLS / 'watcher_recreate_host_once.sh').read_text()
    bootstrap = (TOOLS / 'bootstrap_release_watcher_container.sh').read_text()
    assert 'CONTRACT_VERSION = 3' in contract
    assert "EXPECTED_IMAGE = 'python:3.12-slim'" in contract
    assert "EXPECTED_COMMAND = ['sh', '/energy/App/tools/release_watcher.sh']" in contract
    assert "'image_exact'" in contract and "'command_exact'" in contract
    assert 'recreate_exact_energie_release_watcher' in host
    assert 'RECREATE WATCHER $VERSION' in host
    assert 'VERSION="$(tr -d' in host
    assert 'ENERGIE_WATCHER_CONTAINER_CONTRACT=3' in bootstrap


def test_native_mcp_runtime_truth_is_system_writable_and_schema_scoped():
    guard = (TOOLS / 'native_mcp_runtime_guard.py').read_text()
    hotfix = (TOOLS / 'native_mcp_runtime_contract_hotfix.py').read_text()
    reload_executor = (TOOLS / 'native_mcp_reload_executor.py').read_text()
    marker = 'Data/03_Systeem/Projectmanager/RuntimeEvidence/native_mcp_runtime_fingerprint.json'
    assert marker in guard and marker in reload_executor
    assert 'energie_native_mcp_runtime_v3' in guard and 'energie_native_mcp_runtime_v3' in reload_executor
    assert 'tools_projectmanager.py' in hotfix
    for field in ('source_channel', 'source_ref', 'occurred_at', 'classification_hint'):
        assert field in hotfix


def test_runtime_canonical_loader_never_migrates_unpersisted_truth(monkeypatch, tmp_path):
    source = (PM / 'configured_service.py').read_text()
    assert 'migrate_canonical_roadmap' not in source
    migration_path = PM / 'canonical_roadmap_migration.py'
    spec = importlib.util.spec_from_file_location('migration_32439_failclosed', migration_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    path = tmp_path / 'canonical.json'
    original = _old_canonical()
    path.write_text(json.dumps(original), encoding='utf-8')
    monkeypatch.setattr(module, 'atomic_write_json', lambda *_a, **_k: (_ for _ in ()).throw(PermissionError('read-only')))
    result = module.migrate_canonical_roadmap(path)
    assert result['status'] == 'persistence_required'
    assert result['persistence_required'] is True
    assert 'spec' not in result
    assert json.loads(path.read_text(encoding='utf-8')) == original


def test_clearup_executor_accepts_only_exact_same_release_preacceptance(tmp_path):
    import project_clearup_move_executor as executor
    root = tmp_path
    (root / 'App').mkdir()
    (root / 'App/VERSIE.txt').write_text('32.4.39\n')
    (root / 'CLEARUP').mkdir()
    rollback = root / 'App.__rollback_32.4.38'
    rollback.mkdir()
    (rollback / 'VERSIE.txt').write_text('32.4.38\n')
    (root / 'Inbox/operating_mode').mkdir(parents=True)
    (root / 'Inbox/atomic_app_swap_state.json').write_text(json.dumps({
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.38', 'to_version': '32.4.39'}))
    (root / 'Inbox/operating_mode/release_validation_hold.json').write_text(json.dumps({
        'active': True, 'release_version': '32.4.39', 'validation_status': 'required'}))
    request = {
        'schema': executor.REQUEST_SCHEMA, 'request_id': 'a' * 32, 'operation': 'apply',
        'release_version': '32.4.39', 'expires_at': '2099-01-01T00:00:00+00:00', 'pre_acceptance': True,
    }
    request_id, operation, version, remaining, pre = executor._validate_common(root, request)
    assert request_id == 'a' * 32 and operation == 'apply' and version == '32.4.39'
    assert remaining > 0 and pre is True


def test_clearup_auto_gate_has_preacceptance_phase_and_recovery_fingerprint():
    source = (APP / 'project_clearup_auto.py').read_text()
    assert 'def _pre_acceptance_phase(' in source
    assert 'release_phase_ok' in source
    assert 'prerequisite_fingerprint' in source


def test_clearup_both_watcher_routes_carry_preacceptance():
    source = (APP / 'project_clearup_auto.py').read_text()
    assert source.count('pre_acceptance=bool(gate.get("pre_acceptance"))') == 2


def _r4_preacceptance_fixture(tmp_path):
    import project_clearup_move_executor as executor
    root = tmp_path
    (root / 'App').mkdir()
    (root / 'App/VERSIE.txt').write_text('32.4.39\n')
    (root / 'CLEARUP').mkdir()
    rollback = root / 'App.__rollback_32.4.38'
    rollback.mkdir()
    (rollback / 'VERSIE.txt').write_text('32.4.38\n')
    (root / 'Inbox/operating_mode').mkdir(parents=True)
    (root / 'Inbox/atomic_app_swap_state.json').write_text(json.dumps({
        'state':'LIVE_ACCEPTANCE','from_version':'32.4.38','to_version':'32.4.39'}))
    (root / 'Inbox/operating_mode/release_validation_hold.json').write_text(json.dumps({
        'active':True,'release_version':'32.4.39','validation_status':'required'}))
    request = {
        'schema': executor.REQUEST_SCHEMA,
        'request_id': 'b' * 32,
        'operation': 'apply',
        'release_version': '32.4.39',
        'expires_at': '2099-01-01T00:00:00+00:00',
        'pre_acceptance': True,
    }
    return executor, root, request


def test_r4_preacceptance_rejects_missing_exact_rollback(tmp_path):
    executor, root, request = _r4_preacceptance_fixture(tmp_path)
    rollback = root / 'App.__rollback_32.4.38'
    (rollback / 'VERSIE.txt').unlink()
    rollback.rmdir()
    with pytest.raises(executor.RequestRejected, match='rollbackdirectory'):
        executor._validate_common(root, request)


def test_r4_preacceptance_rejects_installer_and_atomic_locks(tmp_path):
    executor, root, request = _r4_preacceptance_fixture(tmp_path)
    (root / 'Inbox/.installer.lock').mkdir()
    with pytest.raises(executor.RequestRejected, match='installer lock'):
        executor._validate_common(root, request)
    (root / 'Inbox/.installer.lock').rmdir()
    (root / 'Inbox/.atomic_app_swap.lock').mkdir()
    with pytest.raises(executor.RequestRejected, match='atomic swap lock'):
        executor._validate_common(root, request)


def test_r4_preacceptance_rejects_processing_but_allows_waiting_incoming(tmp_path):
    executor, root, request = _r4_preacceptance_fixture(tmp_path)
    incoming = root / 'Inbox/incoming'
    incoming.mkdir()
    (incoming / 'EnergieProject_v32.4.41.zip').write_bytes(b'waiting')
    result = executor._validate_common(root, request)
    assert result[4] is True
    processing = root / 'Inbox/processing'
    processing.mkdir()
    (processing / 'active.zip').write_bytes(b'active')
    with pytest.raises(executor.RequestRejected, match='processing release'):
        executor._validate_common(root, request)


def test_r4_preacceptance_plan_can_never_move_active_rollback(tmp_path, monkeypatch):
    executor, root, request = _r4_preacceptance_fixture(tmp_path)
    request.update({
        'confirmation':'CONFIRM',
        'run_id':'r4-safety',
        'plan':{
            'current_version':'32.4.39',
            'delete_capability':False,
            'confirmation_required':'CONFIRM',
            'items':[{'source_path':'App.__rollback_32.4.38'}],
        },
    })
    request_path = root / 'request.json'
    request_path.write_text(json.dumps(request))
    monkeypatch.setattr(executor, '_load_project_clearup', lambda _root: object())
    with pytest.raises(executor.RequestRejected, match='actieve rollback'):
        executor.execute_request(root, request_path)
