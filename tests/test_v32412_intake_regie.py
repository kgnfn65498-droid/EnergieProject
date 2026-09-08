import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from conversation_intake import ConversationIntakeBridge, classify_intake, route_for_classifications
from document_sync import ManagedDocumentSync
from roadmap_regie import RoadmapRegie
from task_engine import TaskStore


def _bridge(tmp_path):
    runtime = tmp_path / 'RuntimeV2'
    tasks = TaskStore(runtime / 'state/tasks.json')
    active = tasks.start('32.4.12', 'closure', mode='DEVELOPMENT', steps_total=7, priority=1)
    roadmap = RoadmapRegie(runtime / 'roadmap/queue.json')
    reports = tmp_path / 'reports'
    (reports / 'KnowledgeBase').mkdir(parents=True)
    bridge = ConversationIntakeBridge(
        runtime / 'intake/items.json',
        tasks,
        ManagedDocumentSync(),
        reports,
        roadmap_regie=roadmap,
    )
    return bridge, tasks, roadmap, active


def test_one_message_preserves_multiple_meaningful_agreements():
    result = classify_intake(
        'Dit moet als harde eis op de roadmap. Bouw en test de koppeling. Kom hier later op terug.'
    )
    assert result['classification'] == 'hard_requirement'
    assert result['classifications'] == ['hard_requirement', 'action_item', 'later_return']
    assert route_for_classifications(result['classifications']) == [
        'knowledge_base', 'roadmap', 'tasks', 'wishlist'
    ]


def test_intake_routes_to_real_roadmap_and_task_without_displacing_active_work(tmp_path):
    bridge, tasks, roadmap, active = _bridge(tmp_path)
    result = bridge.accept({
        'text': 'Dit moet als harde eis op de roadmap. Bouw en test deze koppeling.',
        'source_channel': 'spraak',
        'source_ref': 'voice:32412:1',
    })
    assert result['classifications'] == ['hard_requirement', 'action_item']
    assert result['status'] == 'ROUTED'
    captured = [item for item in tasks.all() if item.get('intake_fingerprint')]
    assert len(captured) == 1 and captured[0]['status'] == 'PAUSED'
    assert tasks.active()['id'] == active['id']
    intake_roadmap = [item for item in roadmap.all() if item.get('origin') == 'conversation_intake']
    assert len(intake_roadmap) == 1
    assert intake_roadmap[0]['status'] == 'OPEN'
    assert intake_roadmap[0]['intake_fingerprint'] == result['fingerprint']


def test_canonical_reconciliation_preserves_real_intake_roadmap_items(tmp_path):
    bridge, tasks, roadmap, active = _bridge(tmp_path)
    bridge.accept({
        'text': 'Dit moet op de roadmap als harde eis. Bouw dit beheerst.',
        'source_channel': 'chatgpt',
        'source_ref': 'chat:32412:roadmap',
    })
    spec = {
        'schema': 3,
        'version': 'test',
        'items': [
            {'key': 'canonical-one', 'title': 'Canonical one', 'status': 'OPEN', 'mode': 'USER', 'executor': 'handoff'}
        ],
    }
    roadmap.reconcile_canonical(spec, source_path='canonical.json')
    intake_items = [item for item in roadmap.all() if item.get('origin') == 'conversation_intake']
    assert len(intake_items) == 1
    assert intake_items[0]['status'] == 'OPEN'
    assert roadmap.next_open(mode='DEVELOPMENT')['key'] == intake_items[0]['key']


def test_captured_action_item_is_reagendaable_but_protected_actions_are_not_auto_selected(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    normal = tasks.capture(
        'Bouw testkoppeling', 'Bouw testkoppeling', mode='DEVELOPMENT', priority=3,
        intake_fingerprint='normal', approval_required=False,
    )
    protected = tasks.capture(
        'Architectuurwijziging productie', 'Implementeer architectuurwijziging in productie',
        mode='DEVELOPMENT', priority=1, intake_fingerprint='protected', approval_required=True,
    )
    candidate = tasks.next_captured(mode='DEVELOPMENT')
    assert candidate['id'] == normal['id']
    resumed = tasks.resume_captured(candidate['id'], reason='development regie selected backlog')
    assert resumed['status'] == 'ACTIVE'
    assert tasks.get(protected['id'])['status'] == 'PAUSED'


def test_runtime_wires_conversation_intake_to_canonical_roadmap(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import orchestrator as orchestrator_module

    captured = {}

    class SpyBridge:
        def __init__(self, *args, **kwargs):
            captured['roadmap_regie'] = kwargs.get('roadmap_regie')

    class DummyAudit:
        def write(self, *args, **kwargs):
            return None

    roadmap = RoadmapRegie(tmp_path / 'RuntimeV2/roadmap/queue.json')
    tasks = TaskStore(tmp_path / 'RuntimeV2/state/tasks.json')
    base = SimpleNamespace(
        tasks=tasks,
        document_sync=ManagedDocumentSync(),
        opportunities=None,
        handoffs=object(),
        roadmap=roadmap,
        decisions=object(),
        mode=object(),
        audit=DummyAudit(),
        issues=None,
    )
    config = SimpleNamespace(
        system_root=str(tmp_path / 'RuntimeV2'),
        reports_root=str(tmp_path / 'reports'),
        project_root=str(tmp_path),
        mode_command_path='',
        command_ingress_root='',
        approval_ingress_root='',
        handoff_result_ingress_root='',
    )
    monkeypatch.setattr(orchestrator_module, 'ConversationIntakeBridge', SpyBridge)

    orchestrator_module.ProjectmanagerRuntime(
        config,
        base_service=base,
        nas_container_cr_service=object(),
    )

    assert captured['roadmap_regie'] is roadmap
