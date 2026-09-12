import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

from command_store import CommandStore
from decision_queue import DecisionQueue
from state_reconciliation import StateReconciler
from task_engine import TaskStore


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


class _EmptyStore:
    def all(self): return []
    def open_items(self): return []


def _runtime(release='32.4.48', atomic='ACCEPTED'):
    return {
        'release': {'version': release, 'source': '/project/App/VERSIE.txt'},
        'release_chain': {
            'atomic_swap': {
                'state': atomic,
                'source': '/project/Inbox/atomic_app_swap_state.json',
                'raw': {'to_version': release, 'state': atomic},
            }
        },
        'native_mcp_runtime': {
            'status': 'RELOAD_REQUIRED', 'ready': False, 'reload_required': True,
            'expected_fingerprint': 'a' * 64, 'runtime_fingerprint': 'b' * 64,
            'source': '/project/Inbox/native_mcp_runtime/runtime_guard.json',
        },
    }


def test_32448_stale_control_plane_archive_uses_pmv2_runtime_writable_root(tmp_path):
    from protected_action_executor import ProtectedActionExecutor

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.48\n', encoding='utf-8')
    _write_json(project / 'Inbox/native_mcp_runtime/runtime_guard.json', {
        'status': 'RELOAD_REQUIRED', 'ready': False, 'reload_required': True,
        'expected_fingerprint': 'a' * 64, 'runtime_fingerprint': 'b' * 64,
    })
    stale = project / 'Inbox/control_plane/requests/native_mcp_reload.json'
    _write_json(stale, {
        'schema': 'energie_control_plane_request_v1', 'request_id': '1' * 32,
        'action': 'native_mcp_reload', 'approved_by': 'Peter',
        'decision_id': 'old-decision', 'command_id': 'old-command',
        'release_version': '32.4.47', 'expected_fingerprint': 'c' * 64,
    })

    executor = ProtectedActionExecutor(project, None, None, None)
    result = executor._queue_native_mcp_reload(
        {'id': 'action48', 'command_id': 'cmd48', 'decision_id': 'dec48'},
        {'id': 'cmd48', 'approval_decision_id': 'dec48', 'release_version': '32.4.48'},
        {'id': 'dec48', 'status': 'APPROVED', 'approved_by': 'Peter', 'kind': 'PRODUCTION_RESTART',
         'context': {'command_id': 'cmd48', 'intent': 'native_mcp_reload', 'release_version': '32.4.48'}},
    )

    assert result['restart_queued'] is True
    archive_root = project / 'Inbox/projectmanager_v2/RuntimeV2/control_plane_archive'
    archived = list(archive_root.glob('native_mcp_reload.32.4.47.*.json'))
    assert len(archived) == 1
    assert not (project / 'Data/03_Systeem/Projectmanager/RuntimeEvidence/control_plane_archive').exists()


def test_32448_dutch_versioned_closure_task_is_superseded_by_newer_live_release(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    task = tasks.start(
        '32.4.44 volledige closure en Incoming-hardening',
        'Los alle actuele RED-punten op en bouw daarna exact één 32.4.44 ZIP.',
        mode='DEVELOPMENT', steps_total=6,
    )
    reconciler = StateReconciler(tasks, _EmptyStore(), _EmptyStore(), None, None)
    result = reconciler.reconcile(runtime=_runtime('32.4.48'))
    assert result['changed_count'] == 1
    assert tasks.get(task['id'])['status'] == 'SUPERSEDED'


def test_32448_stale_native_mcp_restart_decision_is_superseded_by_newer_live_release(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    commands = CommandStore(tmp_path / 'commands.json')
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    command = commands.enqueue({
        'intent': 'native_mcp_reload', 'source': 'projectmanager_auto', 'release_version': '32.4.47',
    })
    decision = decisions.request('PRODUCTION_RESTART', 'reload old', context={
        'command_id': command['id'], 'intent': 'native_mcp_reload',
        'release_version': '32.4.47', 'source': 'projectmanager_auto',
    })
    commands.wait_for_approval(command['id'], decision_id=decision['id'])

    reconciler = StateReconciler(tasks, decisions, commands, None, None)
    result = reconciler.reconcile(runtime=_runtime('32.4.48'))

    assert result['changed_count'] == 1
    assert decisions.get(decision['id'])['status'] == 'SUPERSEDED'
    assert commands.get(command['id'])['status'] == 'CANCELLED'


def test_32448_current_native_mcp_restart_decision_remains_backup_when_runtime_not_green(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    commands = CommandStore(tmp_path / 'commands.json')
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    command = commands.enqueue({
        'intent': 'native_mcp_reload', 'source': 'projectmanager_auto', 'release_version': '32.4.48',
    })
    decision = decisions.request('PRODUCTION_RESTART', 'reload current', context={
        'command_id': command['id'], 'intent': 'native_mcp_reload',
        'release_version': '32.4.48', 'source': 'projectmanager_auto',
    })
    commands.wait_for_approval(command['id'], decision_id=decision['id'])

    reconciler = StateReconciler(tasks, decisions, commands, None, None)
    result = reconciler.reconcile(runtime=_runtime('32.4.48'))

    item = next(x for x in result['items'] if x['entity_type'] == 'decision')
    assert item['disposition'] == 'ACTIVE_KEEP'
    assert decisions.get(decision['id'])['status'] == 'PENDING'
    assert commands.get(command['id'])['status'] == 'WAITING_APPROVAL'


def test_32448_self_audit_has_semantic_stale_active_task_guard():
    source = (PM / 'self_audit.py').read_text(encoding='utf-8')
    assert 'active_task_release_older_than_runtime' in source
    assert 'release_task_semantic_guard' in source
