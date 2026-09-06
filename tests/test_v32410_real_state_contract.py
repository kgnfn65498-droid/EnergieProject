from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from command_store import CommandStore
from decision_queue import DecisionQueue
from handoff_queue import HandoffQueue
from handoff_result_ingress import HandoffResultIngressConsumer
from issue_store import IssueStore
from roadmap_regie import RoadmapRegie
from state_reconciliation import StateReconciler
from task_engine import TaskStore


def _runtime(mode='DEVELOPMENT'):
    return {
        'release': {'version': '32.4.9', 'source': '/project/App/VERSIE.txt'},
        'operating_mode': {
            'effective_mode': mode,
            'source': '/project/Inbox/operating_mode/operating_mode_state.json',
        },
    }


def _released_ok():
    return {
        'active': False,
        'validation_status': 'ok',
        '_source': '/project/Inbox/operating_mode/release_validation_hold.json',
    }


def test_real_3244_shape_is_review_required_without_machine_proof(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    task = tasks.start(
        '32.4.4 development mode',
        'set base mode DEVELOPMENT for controlled 32.4.4 processing',
        mode='DEVELOPMENT',
        steps_total=1,
        priority=2,
    )
    task = tasks.progress(
        task['id'],
        next_action='verify runtime DEVELOPMENT before 32.4.4 goes incoming',
    )
    reconciler = StateReconciler(
        tasks,
        DecisionQueue(tmp_path / 'decisions.json'),
        CommandStore(tmp_path / 'commands.json'),
        None,
        None,
    )
    result = reconciler.reconcile(runtime=_runtime(), release_validation=_released_ok())
    row = next(x for x in result['items'] if x['entity_type'] == 'task' and x['id'] == task['id'])
    assert row['disposition'] == 'REVIEW_REQUIRED'
    assert row['changed'] is False
    assert tasks.get(task['id'])['status'] == 'ACTIVE'


def test_real_stale_development_decision_is_superseded_only_by_pure_state_proof(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    commands = CommandStore(tmp_path / 'commands.json')
    command = commands.enqueue({
        'source': 'mcp_remote',
        'intent': 'start_development',
        'text': 'Wijzig Projectmanager-modus naar DEVELOPMENT?',
        'title': '32.4.9 Conversation Intake Bridge',
    })
    decision = decisions.request(
        'MODE_CHANGE',
        'Wijzig Projectmanager-modus naar DEVELOPMENT?',
        context={
            'command_id': command['id'],
            'source': 'mcp_remote',
            'intent': 'start_development',
            'target_mode': 'DEVELOPMENT',
            'title': '32.4.9 Conversation Intake Bridge',
        },
    )
    commands.wait_for_approval(command['id'], decision_id=decision['id'])
    reconciler = StateReconciler(tasks, decisions, commands, None, None)
    result = reconciler.reconcile(runtime=_runtime(), release_validation=_released_ok())
    row = next(x for x in result['items'] if x['entity_type'] == 'decision' and x['id'] == decision['id'])
    assert row['disposition'] == 'SUPERSEDED'
    assert row['changed'] is True
    final = decisions.get(decision['id'])
    assert final['status'] == 'SUPERSEDED'
    assert 'approved_by' not in final
    assert commands.get(command['id'])['status'] == 'CANCELLED'


def test_historical_0640_issue_is_not_hidden_without_exact_repair_rule(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    commands = CommandStore(tmp_path / 'commands.json')
    issues = IssueStore(tmp_path / 'issues.json')
    issue = issues.open(
        'command_ingress:53ef7c5c9de04249be98fe8e6c2ae248',
        severity='ORANGE',
        title='Extern Projectmanager-command geweigerd',
        details={'reason': 'PermissionError: [Errno 13] Permission denied: ingress 0640'},
    )
    reconciler = StateReconciler(tasks, decisions, commands, None, issues)
    result = reconciler.reconcile(runtime=_runtime(), release_validation=_released_ok())
    row = next(x for x in result['items'] if x['entity_type'] == 'issue' and x['id'] == issue['id'])
    assert row['disposition'] == 'ACTIVE_KEEP'
    assert row['changed'] is False
    assert any(x['id'] == issue['id'] for x in issues.open_items())


def test_real_paused_conversation_handoff_can_converge_without_displacing_later_task(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    roadmap = RoadmapRegie(tmp_path / 'roadmap.json')
    roadmap.seed_defaults()
    road = roadmap.next_open()
    handoff_task = tasks.start(
        'Conversation Intake Bridge bouwen en end-to-end accepteren',
        'ChatGPT/Nomad/spraak traceerbaar classificeren en routeren',
        mode='DEVELOPMENT',
        steps_total=1,
        priority=2,
    )
    handoff_task = tasks.progress(
        handoff_task['id'], next_action=f"handoff:{road['key']} — complete conversation intake"
    )
    roadmap.mark_active(road['key'], handoff_task['id'])
    handoffs = HandoffQueue(tmp_path / 'handoffs.json')
    handoff = handoffs.ensure_for_task(handoff_task, road)
    later = tasks.start('32.4.10 development', 'continue proactive PM', mode='DEVELOPMENT', steps_total=1, priority=1)
    assert tasks.get(handoff_task['id'])['status'] == 'PAUSED'

    ingress_dir = tmp_path / 'HandoffResultIngress'
    ingress_dir.mkdir()
    ingress_id = '32127bab84f64a7da52738a29bac8a20-replay'
    (ingress_dir / f'{ingress_id}.json').write_text(
        json.dumps({
            'schema': 'energie_pmv2_handoff_result_v1',
            'id': ingress_id,
            'handoff_id': handoff['id'],
            'outcome': 'DONE',
            'summary': '32.4.9 conversation intake live accepted',
            'evidence_refs': ['RuntimeV2/intake/items.json', 'Knowledge_Base_Chat_Bronregister.md'],
        }),
        encoding='utf-8',
    )
    consumer = HandoffResultIngressConsumer(
        ingress_dir,
        tmp_path / 'receipts.json',
        handoffs,
        tasks,
        roadmap,
    )
    result = consumer.consume()
    assert result[0]['status'] == 'APPLIED'
    assert result[0]['resumed_from_paused'] is True
    assert tasks.get(handoff_task['id'])['status'] == 'DONE'
    assert tasks.get(later['id'])['status'] == 'ACTIVE'
    assert handoffs.get(handoff['id'])['status'] == 'DONE'
    assert next(x for x in roadmap.all() if x['key'] == road['key'])['status'] == 'DONE'
