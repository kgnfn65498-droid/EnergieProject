import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for path in (str(APP), str(PM), str(TOOLS)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def test_32444_cr_hotfix_removes_legacy_readonly_native_runtime_writer():
    import cr_standard_native_mcp_hotfix as hotfix

    source = '''from pathlib import Path\nfrom typing import Any\nimport hashlib\nimport json\nimport os\nfrom datetime import datetime, timezone\n\nPATHS = RecoveryPaths(\n    project_root=PROJECT_ROOT,\n    report_root=REPORT_ROOT,\n    recovery_root=RECOVERY_ROOT,\n)\n\ndef _write_native_mcp_runtime_fingerprint() -> None:\n    target = PROJECT_ROOT / "Inbox/native_mcp_runtime/runtime_fingerprint.json"\n    payload = {"schema": "energie_native_mcp_runtime_v1"}\n    temp = target.with_name(target.name + f".tmp-{os.getpid()}")\n    try:\n        temp.write_text(json.dumps(payload))\n        os.replace(temp, target)\n    finally:\n        temp.unlink(missing_ok=True)\n\n_write_native_mcp_runtime_fingerprint()\n\ndef preview_month_closure():\n    return dict(retention=3,)\n\ndef preview_crash_recovery_backup():\n    return dict(retention=3,)\n'''
    transformed = hotfix._tools_recovery(source)
    assert 'PROJECT_ROOT / "Inbox/native_mcp_runtime/runtime_fingerprint.json"' not in transformed
    assert 'energie_native_mcp_runtime_v1' not in transformed
    assert '_write_native_mcp_runtime_fingerprint()' not in transformed


def test_32444_native_reload_archives_stale_previous_release_request(tmp_path):
    from protected_action_executor import ProtectedActionExecutor

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.44\n', encoding='utf-8')
    guard = project / 'Inbox/native_mcp_runtime/runtime_guard.json'
    _write_json(guard, {
        'status': 'RELOAD_REQUIRED', 'ready': False, 'reload_required': True,
        'expected_fingerprint': 'a' * 64, 'runtime_fingerprint': 'b' * 64,
    })
    stale = project / 'Inbox/control_plane/requests/native_mcp_reload.json'
    _write_json(stale, {
        'schema': 'energie_control_plane_request_v1', 'request_id': '1' * 32,
        'action': 'native_mcp_reload', 'approved_by': 'Peter',
        'decision_id': 'old-decision', 'command_id': 'old-command',
        'release_version': '32.4.43', 'expected_fingerprint': 'c' * 64,
    })

    executor = ProtectedActionExecutor(project, None, None, None)
    action = {'id': 'action-44', 'command_id': 'cmd44', 'decision_id': 'dec44'}
    command = {'id': 'cmd44', 'approval_decision_id': 'dec44', 'release_version': '32.4.44'}
    decision = {
        'id': 'dec44', 'status': 'APPROVED', 'approved_by': 'Peter', 'kind': 'PRODUCTION_RESTART',
        'context': {'command_id': 'cmd44', 'intent': 'native_mcp_reload', 'release_version': '32.4.44'},
    }
    result = executor._queue_native_mcp_reload(action, command, decision)
    current = json.loads(stale.read_text(encoding='utf-8'))
    assert result['restart_queued'] is True
    assert current['release_version'] == '32.4.44'
    archives = list((project / 'Inbox/control_plane/archive').glob('native_mcp_reload.32.4.43.*.json'))
    assert len(archives) == 1
    archived = json.loads(archives[0].read_text(encoding='utf-8'))
    assert archived['request_id'] == '1' * 32


def test_32444_final_coordination_refreshes_heartbeat_before_self_audit(tmp_path):
    from orchestrator import ProjectmanagerRuntime

    runtime = ProjectmanagerRuntime.__new__(ProjectmanagerRuntime)
    runtime.root = tmp_path / 'RuntimeV2'
    old = datetime.now(timezone.utc) - timedelta(hours=1)
    _write_json(runtime.root / 'heartbeat/manager.json', {
        'schema': 1, 'service': 'energie-projectmanager-v2', 'state': 'waiting',
        'heartbeat_at': old.isoformat(), 'health': 'GREEN', 'mode': 'MAINTENANCE',
        'pending_decisions': 0, 'pending_notifications': 0,
    })

    class Auditor:
        def run(self, *, now=None, require_coordination=False):
            hb = json.loads((runtime.root / 'heartbeat/manager.json').read_text(encoding='utf-8'))
            stamp = datetime.fromisoformat(hb['heartbeat_at'])
            reference = now or datetime.now(timezone.utc)
            fresh = (reference - stamp).total_seconds() < 60
            return {'status': 'GREEN' if fresh else 'RED', 'invalid': [] if fresh else [{'path':'heartbeat/manager.json','reason':'stale'}], 'warnings': []}

    runtime.base = SimpleNamespace(
        self_auditor=Auditor(),
        _reconcile_self_audit_outcome=lambda audit, now=None: None,
        issues=SimpleNamespace(open_items=lambda: []),
    )
    runtime._refresh_coordination = lambda status: None
    status = {
        'mode': 'MAINTENANCE', 'cycle_generation': 'gen44',
        'health': {'status': 'GREEN', 'checks': []},
    }
    runtime._finalize_coordination_audit(status, now=None)
    heartbeat = json.loads((runtime.root / 'heartbeat/manager.json').read_text(encoding='utf-8'))
    assert status['self_audit']['status'] == 'GREEN'
    assert (datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat['heartbeat_at'])).total_seconds() < 60


def test_32444_stale_maintenance_closure_task_is_superseded_by_newer_release(tmp_path):
    from task_engine import TaskStore
    from decision_queue import DecisionQueue
    from command_store import CommandStore
    from state_reconciliation import StateReconciler

    tasks = TaskStore(tmp_path / 'tasks.json')
    old = tasks.start(
        '32.4.42 Projectmanager technische closure',
        'Autonoom technische closure', mode='MAINTENANCE', steps_total=2, priority=1,
        build_metadata={
            'thinking_level': 'HOOG', 'release_version': '32.4.42',
            'estimated_total_seconds': 100, 'estimated_test_verification_seconds': 20,
            'step_estimates_seconds': [50, 50],
            'original_estimate_recorded_at': datetime.now(timezone.utc).isoformat(),
        },
    )
    reconciler = StateReconciler(
        tasks, DecisionQueue(tmp_path/'decisions.json'), CommandStore(tmp_path/'commands.json'),
        None, None,
    )
    runtime = {
        'release': {'version': '32.4.43', 'source': '/project/App/VERSIE.txt'},
        'release_chain': {'atomic_swap': {'state': 'ACCEPTED', 'source': '/project/Inbox/atomic_app_swap_state.json', 'raw': {'state':'ACCEPTED','to_version':'32.4.43'}}},
    }
    summary = reconciler.reconcile(runtime=runtime, release_validation={})
    assert tasks.get(old['id'])['status'] == 'SUPERSEDED'
    row = next(item for item in summary['items'] if item['entity_type'] == 'task' and item['id'] == old['id'])
    assert row['disposition'] == 'SUPERSEDED'


def test_32444_interrupted_restart_issue_resolves_when_queue_has_no_interrupted_commands(tmp_path):
    from issue_repair_evidence import collect_issue_repair_evidence

    queue = tmp_path / 'commands/queue.json'
    _write_json(queue, {'schema': 1, 'items': [
        {'id': 'old', 'status': 'SUPERSEDED', 'intent': 'project_cr_create'},
        {'id': 'done', 'status': 'DONE', 'intent': 'status_query'},
    ]})
    issue = {
        'id': 'issue-restart', 'fingerprint': 'commands:interrupted_after_restart',
        'created_at': '2026-09-12T10:00:00+00:00', 'last_seen_at': '2026-09-12T11:00:00+00:00',
        'details': {'count': 1},
    }
    result = collect_issue_repair_evidence(tmp_path, [issue])
    assert result['issue-restart']['repair_class'] == 'interrupted_command_queue_drained'
    assert str(queue) in result['issue-restart']['evidence_refs']


def test_32444_series_closure_has_autonomous_cr_nas_clearup_sequence():
    from series_324_live_closure import evaluate, next_action

    base = {
        'watcher_container_contract': 'GREEN', 'native_mcp_runtime': 'GREEN',
        'project_crash_recovery_set': 'ORANGE', 'nas_container_crash_recovery_retention': 'ORANGE',
        'project_structure_hygiene': 'ORANGE',
    }
    assert next_action(base, clearup_done=False, project_close_deferred=False) == 'CREATE_PROJECT_CR'
    base['project_crash_recovery_set'] = 'GREEN'
    assert next_action(base, clearup_done=False, project_close_deferred=False) == 'CREATE_NAS_CR'
    base['nas_container_crash_recovery_retention'] = 'GREEN'
    assert next_action(base, clearup_done=False, project_close_deferred=False) == 'RUN_CLEARUP'
    base['project_structure_hygiene'] = 'GREEN'
    assert next_action(base, clearup_done=True, project_close_deferred=False) == 'COMPLETE'
    checks = [{'name': name, 'status': status} for name, status in base.items()]
    closure = evaluate(checks, clearup={'status':'completed','release_version':'32.4.44'}, release_version='32.4.44')
    assert closure['status'] == 'GREEN'


def test_32444_exact_uploaded_32443_basis_is_recorded():
    evidence = json.loads((ROOT / 'docs/32.4.44-build-basis.json').read_text(encoding='utf-8'))
    assert evidence['target_release'] == '32.4.44'
    assert evidence['previous_release'] == '32.4.43'
    assert evidence['artifact_sha256'] == 'f1a4352a78ea2daf10359603fc4bd94c68b1f50d9f19694848adbb4ac28c54ec'
    assert evidence['manifest_files_verified'] == 423
    assert evidence['verified_against_live_atomic_swap'] is True


def test_32444_release_identity_is_coherent():
    import release_test_contract as contract

    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.44'
    assert 'version: "32.4.44"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.4.44"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.4.44"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == '2.0.0-rc31'
    assert contract.CURRENT_RELEASE == '32.4.44'
    assert contract.CURRENT_PM_VERSION == '2.0.0-rc31'
