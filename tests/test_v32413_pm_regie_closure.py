import json
import hashlib
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeter_import_missing'
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
RUNTIME_APP = ROOT / 'slimmemeterportal_import/rootfs/app'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(RUNTIME_APP))

from alert_policy import AlertState
from audit_log import AuditLog
from conversation_intake import ConversationIntakeBridge, classify_intake
from document_sync import ManagedDocumentSync
from handoff_queue import HandoffQueue
from handoff_result_ingress import HandoffResultIngressConsumer, VALID_SCHEMA
from issue_store import IssueStore
from manager_service import ManagerService
from notification_transport import NotificationOutbox
from release_health import release_health_checks
from roadmap_regie import RoadmapRegie
from task_engine import REQUIRED_DOD_GATES, TaskStore


def _all_dod_green():
    return {name: True for name in REQUIRED_DOD_GATES}


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_release_hold_green_finalizes_atomic_live_acceptance(tmp_path, monkeypatch):
    import operating_mode_runtime as runtime
    from release_validation_hold import activate_release_hold, record_hold_validation, load_release_hold

    root = tmp_path / 'energy'
    app = root / 'App'
    rollback = root / 'App.__rollback_32.4.12'
    (app / 'slimmemeterportal_import/rootfs/app/projectmanager_v2').mkdir(parents=True)
    (app / 'tools').mkdir(parents=True)
    rollback.mkdir(parents=True)
    (app / 'VERSIE.txt').write_text('32.4.13\n', encoding='utf-8')
    (app / 'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt').write_text('2.0.0-rc10\n', encoding='utf-8')
    (rollback / 'VERSIE.txt').write_text('32.4.12\n', encoding='utf-8')
    shutil.copy2(ROOT / 'tools/atomic_app_swap.py', app / 'tools/atomic_app_swap.py')
    for name in ('README.md', 'INSTALL.md', 'CHANGELOG.md', 'repository.yaml'):
        (app / name).write_text(f'{name}\n', encoding='utf-8')
    (app / 'SHA256SUMS.json').write_text('{}\n', encoding='utf-8')
    manifest_rows = []
    for rel in ('VERSIE.txt', 'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt'):
        payload = (app / rel).read_bytes()
        manifest_rows.append(f"{hashlib.sha256(payload).hexdigest()}  {rel}")
    (app / 'MANIFEST.sha256').write_text('\n'.join(manifest_rows) + '\n', encoding='utf-8')
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE',
        'from_version': '32.4.12',
        'to_version': '32.4.13',
        'artifact_sha256': 'abc123',
        'candidate_path': 'App.__candidate_32.4.13',
        'rollback_path': 'App.__rollback_32.4.12',
        'error': '',
    })
    activate_release_hold(root, '32.4.13', 'release_install')
    record_hold_validation(root, '32.4.13', {'synthetic': {'ok': True}}, 'ok')
    monkeypatch.setattr(runtime, 'validate_release_hold', lambda *a, **k: {
        'status': 'ok', 'version': '32.4.13', 'checks': {'synthetic': {'ok': True}}, 'reconcile_status': 'ok', 'drift': [],
    })

    result = runtime.attempt_release_hold(
        SimpleNamespace(APP_VERSION='32.4.13'), root, '32.4.13', issued_by='test'
    )

    assert result['status'] == 'released'
    journal = json.loads((root / 'Inbox/atomic_app_swap_state.json').read_text(encoding='utf-8'))
    assert journal['state'] == 'ACCEPTED'
    assert load_release_hold(root, '32.4.13').active is False


def test_production_intake_is_protected_regardless_of_word_order():
    variants = [
        'Bouw en installeer deze release in productie.',
        'Plaats deze wijziging straks in productie.',
        'Deploy de release naar production.',
        'Productie: installeer deze release.',
    ]
    for text in variants:
        classified = classify_intake(text)
        assert classified['development_context'] is True, text
        assert classified['approval_required'] is True, text


def _handoff_fixture(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    roadmap = RoadmapRegie(tmp_path / 'roadmap.json')
    handoffs = HandoffQueue(tmp_path / 'handoffs.json')
    task = tasks.start('handoff work', 'handoff work', mode='DEVELOPMENT', steps_total=1, priority=2)
    task = tasks.progress(task['id'], next_action='handoff:item-1')
    roadmap_item = roadmap.capture_intake(
        'handoff work', mode='DEVELOPMENT', intake_fingerprint='handoff-1', approval_required=False,
    )
    roadmap.mark_active(roadmap_item['key'], task['id'])
    active_roadmap = next(item for item in roadmap.all() if item['key'] == roadmap_item['key'])
    handoff = handoffs.ensure_for_task(task, active_roadmap)
    ingress = tmp_path / 'ingress'
    ingress.mkdir()
    return tasks, roadmap, handoffs, task, roadmap_item, handoff, ingress


def _write_done(ingress, handoff_id, ingress_id='result1'):
    _write_json(ingress / f'{ingress_id}.json', {
        'schema': VALID_SCHEMA,
        'id': ingress_id,
        'handoff_id': handoff_id,
        'outcome': 'DONE',
        'summary': 'klaar',
        'evidence_refs': ['tests:green'],
        'dod_gates': _all_dod_green(),
    })


def test_late_done_for_blocked_handoff_is_rejected_without_mutating_task_or_roadmap(tmp_path):
    tasks, roadmap, handoffs, task, roadmap_item, handoff, ingress = _handoff_fixture(tmp_path)
    handoffs.block(handoff['id'], summary='extern geblokkeerd')
    _write_done(ingress, handoff['id'])
    consumer = HandoffResultIngressConsumer(ingress, tmp_path / 'receipts.json', handoffs, tasks, roadmap)

    result = consumer.consume(max_items=1)[0]

    assert result['status'] == 'REJECTED'
    assert 'handoff_not_open:BLOCKED' in result['reason']
    assert tasks.get(task['id'])['status'] == 'ACTIVE'
    assert next(item for item in roadmap.all() if item['key'] == roadmap_item['key'])['status'] == 'ACTIVE'
    assert handoffs.get(handoff['id'])['status'] == 'BLOCKED'


def test_handoff_result_rolls_back_all_stores_if_late_write_fails(tmp_path, monkeypatch):
    tasks, roadmap, handoffs, task, roadmap_item, handoff, ingress = _handoff_fixture(tmp_path)
    _write_done(ingress, handoff['id'])
    before_task = tasks.get(task['id'])
    before_roadmap = next(item for item in roadmap.all() if item['key'] == roadmap_item['key'])
    before_handoff = handoffs.get(handoff['id'])

    def fail_complete(*args, **kwargs):
        raise OSError('simulated handoff store write failure')

    monkeypatch.setattr(handoffs, 'complete', fail_complete)
    consumer = HandoffResultIngressConsumer(ingress, tmp_path / 'receipts.json', handoffs, tasks, roadmap)
    result = consumer.consume(max_items=1)[0]

    assert result['status'] == 'REJECTED'
    assert tasks.get(task['id']) == before_task
    assert next(item for item in roadmap.all() if item['key'] == roadmap_item['key']) == before_roadmap
    assert handoffs.get(handoff['id']) == before_handoff


def _runtime_chain(**overrides):
    chain = {
        'watcher': {'active': True, 'heartbeat_age_seconds': 1},
        'incoming': {'count': 0, 'stuck_count': 0, 'files': []},
        'processing': {'count': 0, 'stuck_count': 0, 'files': []},
        'installer_lock': {'active': False, 'age_seconds': None},
        'atomic_swap': {'state': 'ACCEPTED', 'age_seconds': 1, 'exists': True},
        'publisher': {'status': 'published', 'version': '32.4.13', 'age_seconds': 1, 'exists': True},
        'github_publication': {'status': 'published', 'version': '32.4.13', 'contract_pending': False},
    }
    chain.update(overrides)
    return {
        'release_chain': chain,
        'release': {
            'version': '32.4.13', 'ha_runtime_version': '32.4.13', 'nas_version': '32.4.13',
            'rollback_version': '32.4.12', 'rollback_versions': ['32.4.12'],
        },
    }


def _by_name(checks):
    return {item['name']: item for item in checks}


def test_release_health_never_marks_unknown_or_blocking_chain_state_green():
    checks = _by_name(release_health_checks(_runtime_chain(
        incoming={'count': 2, 'stuck_count': 0, 'files': [{'name': 'a.zip'}, {'name': 'b.zip'}]},
        atomic_swap={'state': 'BOGUS', 'age_seconds': 1, 'exists': True},
        publisher={'status': None, 'version': None, 'age_seconds': None, 'exists': False},
    )))
    assert checks['release_incoming']['status'] == 'RED'
    assert checks['release_atomic_state']['status'] == 'RED'
    assert checks['release_publisher']['status'] != 'GREEN'


def test_release_health_escalates_stale_live_acceptance_that_blocks_next_release():
    checks = _by_name(release_health_checks(_runtime_chain(
        incoming={'count': 1, 'stuck_count': 0, 'files': [{'name': 'next.zip'}]},
        atomic_swap={'state': 'LIVE_ACCEPTANCE', 'age_seconds': 180, 'exists': True},
    )))
    assert checks['release_atomic_state']['status'] == 'RED'
    assert checks['release_atomic_state']['reason'] == 'live_acceptance_blocks_release_ingress'


def test_self_audit_red_opens_issue_and_queues_direct_warning(tmp_path):
    assert hasattr(ManagerService, '_reconcile_self_audit_outcome')
    service = object.__new__(ManagerService)
    service.issues = IssueStore(tmp_path / 'issues.json')
    service.outbox = NotificationOutbox(tmp_path / 'outbox')
    service.alerts = AlertState(tmp_path / 'alerts.json')
    service.audit = AuditLog(tmp_path / 'audit.jsonl')
    now = datetime.now(timezone.utc)

    check = service._reconcile_self_audit_outcome(
        {'status': 'RED', 'invalid': [{'reason': 'synthetic_failure'}]}, now=now
    )

    assert check['status'] == 'RED'
    issues = service.issues.open_items()
    assert any(item['fingerprint'] == 'health:projectmanager_self_audit' and item['severity'] == 'RED' for item in issues)
    pending = service.outbox.pending()
    assert len(pending) == 1
    assert pending[0][1]['severity'] == 'RED'
    assert 'self_audit_red' in pending[0][1]['fingerprint']


def test_conversation_summary_counts_every_classification_not_only_primary(tmp_path):
    runtime = tmp_path / 'RuntimeV2'
    reports = tmp_path / 'reports'
    (reports / 'KnowledgeBase').mkdir(parents=True)
    bridge = ConversationIntakeBridge(
        runtime / 'intake/items.json',
        TaskStore(runtime / 'state/tasks.json'),
        ManagedDocumentSync(),
        reports,
        roadmap_regie=RoadmapRegie(runtime / 'roadmap/queue.json'),
    )
    bridge.accept({
        'text': 'Dit moet als harde eis. Bouw dit. Kom hier later op terug.',
        'source_channel': 'chatgpt',
        'source_ref': 'chat:multi-count',
    })

    counts = bridge.summary()['classification_counts']
    assert counts['hard_requirement'] == 1
    assert counts['action_item'] == 1
    assert counts['later_return'] == 1


def test_projectmanager_gui_renders_shared_progress_truth(tmp_path):
    import projectmanager_v2.projectmanager_web as web
    assert hasattr(web, 'render_projectmanager_progress')
    runtime = tmp_path / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
    _write_json(runtime, {
        'health': {'status': 'ORANGE'},
        'active_task': {'title': '32.4.13 closure'},
        'progress': {
            'step_label': 'Stap 3/7',
            'completed_steps': 2,
            'remaining_steps': 5,
            'next_step': 'handoff audit',
            'elapsed_seconds': 120,
            'estimated_remaining_seconds': 300,
            'blockers': ['geen productieplaatsing'],
            'status_color': 'ORANGE',
            'progress_percent': 42.9,
            'planning_trend': 'improving',
        },
    })
    card = web.render_projectmanager_progress(tmp_path)
    for expected in ('Stap 3/7', '42.9%', 'handoff audit', '300', 'improving', 'geen productieplaatsing'):
        assert expected in card

    class Handler:
        def do_POST(self):
            return None

    App = type('App', (), {
        'Handler': Handler,
        'html_page': staticmethod(lambda: b'<html><body><h1>GUI</h1></body></html>'),
    })

    web.install_projectmanager_web(App, tmp_path, private_root=tmp_path / 'private')
    page = App.html_page().decode('utf-8')
    assert 'id="pmv2-progress"' in page
    assert 'Stap 3/7' in page
