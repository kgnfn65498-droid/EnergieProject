import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from configured_service import ConfiguredManagerService
from handoff_queue import HandoffQueue
from handoff_result_ingress import HandoffResultIngressConsumer, VALID_SCHEMA
from roadmap_regie import RoadmapRegie
from task_engine import REQUIRED_DOD_GATES, TaskStore


class Mode:
    def __init__(self, value):
        self.value = value
    def get(self):
        return {'mode': self.value}


class EmptyQueue:
    def by_status(self, *statuses):
        return []
    def open_items(self):
        return []


class Audit:
    def write(self, *args, **kwargs):
        return None


def _configured_service(tmp_path, mode='DEVELOPMENT'):
    service = object.__new__(ConfiguredManagerService)
    service.tasks = TaskStore(tmp_path / 'tasks.json')
    service.roadmap = RoadmapRegie(tmp_path / 'roadmap.json')
    service.mode = Mode(mode)
    service._coordination_commands = EmptyQueue()
    service._coordination_actions = EmptyQueue()
    service.handoffs = HandoffQueue(tmp_path / 'handoffs.json')
    service.audit = Audit()
    service._reconcile_canonical_roadmap = lambda: {'ok': True, 'canonical': {'version': 'test'}}
    return service


def test_development_regie_autonomously_selects_safe_development_roadmap_item(tmp_path):
    service = _configured_service(tmp_path)
    item = service.roadmap.capture_intake(
        'Bouw veilige validatie', mode='DEVELOPMENT', intake_fingerprint='dev-safe',
        approval_required=False, priority=2,
    )

    selected = service._maybe_select_roadmap_task({'status': 'GREEN'}, [])

    assert selected['key'] == item['key']
    task = service.tasks.get(selected['task_id'])
    assert task['mode'] == 'DEVELOPMENT'
    assert task['status'] == 'ACTIVE'


def test_development_regie_reagendas_safe_captured_action_when_roadmap_empty(tmp_path):
    service = _configured_service(tmp_path)
    captured = service.tasks.capture(
        'Test koppeling', 'Test koppeling', mode='DEVELOPMENT', priority=3,
        intake_fingerprint='captured-safe', approval_required=False,
    )

    selected = service._maybe_select_roadmap_task({'status': 'GREEN'}, [])

    assert selected['task_id'] == captured['id']
    assert selected['source'] == 'conversation_backlog'
    assert service.tasks.get(captured['id'])['status'] == 'ACTIVE'


def test_development_regie_never_auto_selects_protected_intake_action(tmp_path):
    service = _configured_service(tmp_path)
    service.roadmap.capture_intake(
        'Architectuurwijziging productie', mode='DEVELOPMENT', intake_fingerprint='protected-roadmap',
        approval_required=True, priority=1,
    )
    protected = service.tasks.capture(
        'Architectuurwijziging productie', 'Plaats architectuurwijziging in productie', mode='DEVELOPMENT', priority=1,
        intake_fingerprint='protected-task', approval_required=True,
    )

    selected = service._maybe_select_roadmap_task({'status': 'GREEN'}, [])

    assert selected is None
    assert service.tasks.get(protected['id'])['status'] == 'PAUSED'


def _handoff_task(tmp_path, *, mode='DEVELOPMENT'):
    tasks = TaskStore(tmp_path / 'tasks.json')
    task = tasks.start('handoff work', 'handoff work', mode=mode, steps_total=2, priority=2)
    task = tasks.progress(task['id'], next_action='handoff:item-1')
    return tasks, task


def _all_dod_green():
    return {name: True for name in REQUIRED_DOD_GATES}


def test_development_handoff_cannot_complete_without_all_definition_of_done_gates(tmp_path):
    tasks, task = _handoff_task(tmp_path, mode='DEVELOPMENT')
    try:
        tasks.complete_handoff(task['id'], summary='klaar', evidence_refs=['tests:green'], gates={})
    except ValueError as exc:
        assert 'definition of done missing' in str(exc)
    else:
        raise AssertionError('DEVELOPMENT handoff bypassed Definition of Done')
    assert tasks.get(task['id'])['status'] == 'ACTIVE'


def test_development_handoff_completes_with_all_definition_of_done_gates(tmp_path):
    tasks, task = _handoff_task(tmp_path, mode='DEVELOPMENT')
    done = tasks.complete_handoff(
        task['id'], summary='klaar', evidence_refs=['tests:green'], gates=_all_dod_green(),
    )
    assert done['status'] == 'DONE'
    assert done['dod_gates'] == _all_dod_green()


def test_user_handoff_keeps_existing_non_development_completion_route(tmp_path):
    tasks, task = _handoff_task(tmp_path, mode='USER')
    done = tasks.complete_handoff(task['id'], summary='onderzoek klaar', evidence_refs=['report:1'])
    assert done['status'] == 'DONE'


def test_handoff_result_ingress_requires_dod_evidence_for_development_done(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    roadmap = RoadmapRegie(tmp_path / 'roadmap.json')
    handoffs = HandoffQueue(tmp_path / 'handoffs.json')
    task = tasks.start('dev handoff', 'dev handoff', mode='DEVELOPMENT', steps_total=1, priority=2)
    task = tasks.progress(task['id'], next_action='handoff:dev-item')
    roadmap_item = roadmap.capture_intake(
        'dev handoff', mode='DEVELOPMENT', intake_fingerprint='dev-item', approval_required=False,
    )
    roadmap.mark_active(roadmap_item['key'], task['id'])
    active_roadmap_item = next(item for item in roadmap.all() if item['key'] == roadmap_item['key'])
    handoff = handoffs.ensure_for_task(task, active_roadmap_item)
    ingress = tmp_path / 'ingress'
    ingress.mkdir()
    payload = {
        'schema': VALID_SCHEMA,
        'id': 'result1',
        'handoff_id': handoff['id'],
        'outcome': 'DONE',
        'summary': 'klaar',
        'evidence_refs': ['tests:green'],
        'dod_gates': {},
    }
    (ingress / 'result1.json').write_text(json.dumps(payload), encoding='utf-8')
    consumer = HandoffResultIngressConsumer(ingress, tmp_path / 'receipts.json', handoffs, tasks, roadmap)

    result = consumer.consume(max_items=1)[0]

    assert result['status'] == 'REJECTED'
    assert 'definition of done missing' in result['reason']
    assert tasks.get(task['id'])['status'] == 'ACTIVE'
    assert next(item for item in roadmap.all() if item['key'] == roadmap_item['key'])['status'] == 'ACTIVE'
