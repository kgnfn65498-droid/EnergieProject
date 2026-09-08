import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(APP))

try:
    from handover_snapshot import HandoverSnapshotService
except ImportError as exc:
    HandoverSnapshotService = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def _write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _fixture(tmp_path):
    runtime = tmp_path / 'RuntimeV2'
    project = tmp_path / 'project'
    (project / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.15\n', encoding='utf-8')
    (project / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt').write_text('2.0.0-rc12\n', encoding='utf-8')
    status = {
        'schema': 'energie_projectmanager_status_v2',
        'updated_at': '2026-09-08T18:00:00+00:00',
        'project_id': 'energie',
        'mode': 'DEVELOPMENT',
        'health': {'status': 'ORANGE', 'checks': [{'name': 'release_atomic_state', 'status': 'ORANGE', 'reason': 'installer_or_atomic_transition_active'}]},
        'release': {'version': '32.4.15', 'rollback_version': '32.4.14', 'ha_runtime_version': '32.4.15', 'nas_version': '32.4.15'},
        'release_chain': {
            'watcher': {'active': True, 'heartbeat_age_seconds': 1},
            'incoming': {'count': 0, 'files': []},
            'processing': {'count': 0, 'files': []},
            'atomic_swap': {'state': 'LIVE_ACCEPTANCE', 'to_version': '32.4.15', 'age_seconds': 12},
            'publisher': {'status': 'published', 'version': '32.4.15'},
        },
        'active_task': {
            'id': 'task-1', 'title': '32.4.15 closure', 'goal': 'sluit serie', 'mode': 'DEVELOPMENT',
            'status': 'BLOCKED', 'step': 4, 'steps_total': 6, 'next_action': 'los blocker op',
            'blockers': ['voice approval e2e nog niet groen'], 'priority': 1,
        },
        'progress': {
            'step': 4, 'steps_total': 6, 'step_label': 'Stap 4/6', 'percentage': 66.7,
            'eta': 'NOG_TE_CONTROLEREN', 'blockers': ['voice approval e2e nog niet groen'],
            'next_action': 'los blocker op', 'trend': 'STABIEL',
        },
        'next_action': 'los blocker op',
        'decisions_needed': [{'id': 'dec-1', 'kind': 'PRODUCTION_DEPLOY', 'status': 'PENDING', 'question': 'Deploy 32.4.15?'}],
        'open_issues': [{'id': 'issue-1', 'fingerprint': 'voice:e2e', 'severity': 'ORANGE', 'status': 'OPEN', 'title': 'Voice E2E'}],
        'approved_actions': [],
        'handoffs': [{'id': 'hand-1', 'task_id': 'task-1', 'roadmap_key': 'v32415', 'status': 'OPEN', 'title': 'test handoff'}],
    }
    _write(runtime / 'status/current.json', status)
    _write(runtime / 'roadmap/queue.json', {
        'schema': 2,
        'canonical': {'version': '32.4-closure', 'approved_by': 'Peter'},
        'items': [
            {'key': 'v32415', 'title': '32.4.15 closure', 'status': 'ACTIVE', 'priority': 1, 'mode': 'DEVELOPMENT', 'executor': 'embedded'},
            {'key': 'ngrok', 'title': 'ngrok audit', 'status': 'OPEN', 'priority': 2, 'mode': 'USER', 'executor': 'handoff'},
        ],
    })
    _write(runtime / 'state/tasks.json', {'schema': 1, 'tasks': [status['active_task']]})
    _write(runtime / 'decisions/queue.json', {'schema': 1, 'items': status['decisions_needed']})
    _write(runtime / 'issues/issues.json', {'schema': 1, 'items': status['open_issues']})
    _write(runtime / 'handoffs/queue.json', {'schema': 1, 'items': status['handoffs']})
    _write(runtime / 'intake/items.json', {'schema': 1, 'items': [
        {'id': 'i1', 'fingerprint': 'f1', 'classification': 'hard_requirement', 'classifications': ['hard_requirement'], 'text': 'Voice Mode moet voor 32.5 groen zijn.', 'source_channel': 'chatgpt', 'created_at': '2026-09-08T17:00:00+00:00'},
        {'id': 'i2', 'fingerprint': 'f2', 'classification': 'informational_context', 'classifications': ['informational_context'], 'text': 'token=SUPERSECRET', 'source_channel': 'voice', 'created_at': '2026-09-08T17:01:00+00:00'},
    ]})
    _write(runtime / 'self_audit/current.json', {'status': 'GREEN', 'invalid': [], 'warnings': []})
    _write(runtime / 'snapshots/current_runtime.json', {
        'observed_at': '2026-09-08T18:00:00+00:00',
        'runtime': {'release': status['release'], 'release_chain': status['release_chain']},
        'checks': [{'name': 'watcher', 'status': 'GREEN', 'evidence_ref': 'runtime:watcher'}],
    })
    assert HandoverSnapshotService is not None, f'handover snapshot runtime missing: {IMPORT_ERROR}'
    return runtime, project, HandoverSnapshotService(runtime, project_root=project)


def test_typed_new_chat_snapshot_uses_current_canonical_truth_and_is_ready(tmp_path):
    runtime, project, service = _fixture(tmp_path)
    snap = service.create(source_channel='chatgpt', trigger_text='ga verder in een nieuwe chat', trigger_id='turn-1')
    assert snap['status'] == 'ready'
    assert snap['release_version'] == '32.4.15'
    assert snap['pm_version'] == '2.0.0-rc12'
    assert snap['mode'] == 'DEVELOPMENT'
    assert snap['progress']['step_label'] == 'Stap 4/6'
    assert snap['next_step'] == 'los blocker op'
    assert snap['blockers'] == ['voice approval e2e nog niet groen']
    assert snap['open_approvals'][0]['kind'] == 'PRODUCTION_DEPLOY'
    assert snap['open_issues'][0]['fingerprint'] == 'voice:e2e'
    assert snap['active_handoffs'][0]['id'] == 'hand-1'
    assert snap['release_truth']['release_chain']['atomic_swap']['to_version'] == '32.4.15'
    assert snap['roadmap']['active'][0]['key'] == 'v32415'
    assert snap['roadmap']['next'][0]['key'] == 'ngrok'
    assert (runtime / 'handover/ready/current.json').is_file()
    assert (runtime / 'handover/ready/current.md').is_file()


def test_voice_snapshot_has_same_truth_as_typed_except_source_identity(tmp_path):
    runtime, project, service = _fixture(tmp_path)
    typed = service.create(source_channel='chatgpt', trigger_text='nieuwe chat', trigger_id='typed-1', now=datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc))
    voice = service.create(source_channel='voice', trigger_text='We gaan verder in een nieuwe chat.', trigger_id='voice-1', now=datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc))
    for key in ('release_version', 'pm_version', 'mode', 'progress', 'next_step', 'blockers', 'open_approvals', 'open_issues', 'release_truth', 'roadmap'):
        assert typed[key] == voice[key]
    assert typed['source']['channel'] == 'chatgpt'
    assert voice['source']['channel'] == 'voice'
    assert typed['handover_id'] != voice['handover_id']


def test_change_immediately_before_handover_is_in_snapshot(tmp_path):
    runtime, project, service = _fixture(tmp_path)
    status = json.loads((runtime / 'status/current.json').read_text())
    status['active_task']['step'] = 5
    status['progress']['step'] = 5
    status['progress']['step_label'] = 'Stap 5/6'
    status['progress']['percentage'] = 83.3
    status['next_action'] = status['active_task']['next_action'] = 'fresh-extract audit'
    status['progress']['next_action'] = 'fresh-extract audit'
    _write(runtime / 'status/current.json', status)
    snap = service.create(source_channel='dictation', trigger_text='bereid de nieuwe chat voor', trigger_id='dict-2')
    assert snap['progress']['step_label'] == 'Stap 5/6'
    assert snap['next_step'] == 'fresh-extract audit'


def test_failed_new_snapshot_leaves_previous_valid_current_intact(tmp_path):
    runtime, project, service = _fixture(tmp_path)
    first = service.create(source_channel='chatgpt', trigger_text='nieuwe chat', trigger_id='ok-1')
    (runtime / 'status/current.json').write_text('{broken', encoding='utf-8')
    with pytest.raises(RuntimeError):
        service.create(source_channel='voice', trigger_text='nieuwe chat', trigger_id='bad-2')
    current = json.loads((runtime / 'handover/ready/current.json').read_text())
    assert current['handover_id'] == first['handover_id']
    assert service.latest_ready()['handover_id'] == first['handover_id']


def test_duplicate_trigger_is_idempotent_and_does_not_create_conflicting_current(tmp_path):
    runtime, project, service = _fixture(tmp_path)
    first = service.create(source_channel='voice', trigger_text='nieuwe chat', trigger_id='same-event')
    second = service.create(source_channel='voice', trigger_text='nieuwe chat', trigger_id='same-event')
    assert second['handover_id'] == first['handover_id']
    history = list((runtime / 'handover/history').glob('*.json'))
    assert len(history) == 1


def test_resume_uses_latest_valid_ready_snapshot_and_skips_incomplete_pointer(tmp_path):
    runtime, project, service = _fixture(tmp_path)
    first = service.create(source_channel='chatgpt', trigger_text='nieuwe chat', trigger_id='1', now=datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc))
    second = service.create(source_channel='voice', trigger_text='nieuwe chat', trigger_id='2', now=datetime(2026, 9, 8, 18, 1, tzinfo=timezone.utc))
    _write(runtime / 'handover/ready/current.json', {'status': 'ready', 'handover_id': 'incomplete'})
    resumed = service.resume_context()
    assert resumed['handover_id'] == second['handover_id']
    assert resumed['handover_id'] != first['handover_id']


def test_snapshot_is_compact_and_excludes_secret_like_or_junk_content(tmp_path):
    runtime, project, service = _fixture(tmp_path)
    snap = service.create(source_channel='speech', trigger_text='volgende build in een verse chat', trigger_id='safe')
    encoded = json.dumps(snap, ensure_ascii=False)
    assert 'SUPERSECRET' not in encoded
    assert '__pycache__' not in encoded and '.pyc' not in encoded
    assert len(encoded.encode('utf-8')) < 100_000
    assert any(item['text'] == 'Voice Mode moet voor 32.5 groen zijn.' for item in snap['binding_context'])
