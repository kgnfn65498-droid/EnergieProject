from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from command_store import CommandStore
from decision_queue import DecisionQueue
from handoff_queue import HandoffQueue
from issue_store import IssueStore
from runtime_sources import RuntimeCollector
from state_reconciliation import StateReconciler
from task_engine import TaskStore


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def _stores(root: Path):
    tasks = TaskStore(root / 'tasks.json')
    decisions = DecisionQueue(root / 'decisions.json')
    commands = CommandStore(root / 'commands.json')
    handoffs = HandoffQueue(root / 'handoffs.json')
    issues = IssueStore(root / 'issues.json')
    return tasks, decisions, commands, StateReconciler(tasks, decisions, commands, handoffs, issues)


def _pending_watcher_recreate(decisions: DecisionQueue, commands: CommandStore):
    command = commands.enqueue({
        'intent': 'watcher_recreate',
        'source': 'mcp_remote',
        'title': 'watcher herstellen',
        'goal': 'herstel uitsluitend de bestaande release-watcher',
    })
    decision = decisions.request(
        'PRODUCTION_RESTART',
        'watcher recreate?',
        context={'command_id': command['id'], 'intent': 'watcher_recreate'},
    )
    command = commands.wait_for_approval(command['id'], decision_id=decision['id'])
    return decision, command


def _watcher_runtime(*, contract_green: bool = True, active: bool = True) -> dict:
    return {
        'release_chain': {
            'watcher': {
                'active': active,
                'heartbeat_age_seconds': 0.0 if active else 999.0,
                'heartbeat_path': '/project/Inbox/watcher_heartbeat.v2',
                'stale_after_seconds': 60,
            },
            'watcher_container_contract': {
                'status': 'GREEN' if contract_green else 'RED',
                'ready': contract_green,
                'contract_version': 3,
                'source': '/project/Inbox/watcher_container_contract.json',
            },
        }
    }


def test_runtime_collector_exposes_watcher_contract_as_machine_readable_evidence(tmp_path: Path):
    project = tmp_path / 'project'
    inbox = project / 'Inbox'
    inbox.mkdir(parents=True)
    now = datetime(2026, 9, 15, 18, 0, tzinfo=timezone.utc)
    (inbox / 'watcher_heartbeat.v2').write_text(str(now.timestamp()), encoding='utf-8')
    _write_json(inbox / 'watcher_container_contract.json', {
        'status': 'GREEN', 'ready': True, 'contract_version': 3, 'reason': 'contract_match',
    })

    chain = RuntimeCollector(project, watcher_probe_seconds=0)._release_chain(now=now)

    contract = chain['watcher_container_contract']
    assert contract['status'] == 'GREEN'
    assert contract['ready'] is True
    assert contract['contract_version'] == 3
    assert contract['source'] == str(inbox / 'watcher_container_contract.json')


def test_pending_watcher_recreate_is_superseded_only_when_runtime_and_contract_are_green(tmp_path: Path):
    tasks, decisions, commands, reconciler = _stores(tmp_path)
    decision, command = _pending_watcher_recreate(decisions, commands)

    result = reconciler.reconcile(runtime=_watcher_runtime(), release_validation={})

    row = next(item for item in result['items'] if item['id'] == decision['id'])
    assert row['disposition'] == 'SUPERSEDED'
    assert row['changed'] is True
    assert row['evidence_refs'] == [
        '/project/Inbox/watcher_heartbeat.v2',
        '/project/Inbox/watcher_container_contract.json',
    ]
    assert decisions.get(decision['id'])['status'] == 'SUPERSEDED'
    assert commands.get(command['id'])['status'] == 'CANCELLED'


def test_pending_watcher_recreate_remains_protected_when_runtime_proof_is_not_green(tmp_path: Path):
    tasks, decisions, commands, reconciler = _stores(tmp_path)
    decision, command = _pending_watcher_recreate(decisions, commands)

    result = reconciler.reconcile(runtime=_watcher_runtime(contract_green=False), release_validation={})

    row = next(item for item in result['items'] if item['id'] == decision['id'])
    assert row['disposition'] == 'ACTIVE_KEEP'
    assert row['changed'] is False
    assert decisions.get(decision['id'])['status'] == 'PENDING'
    assert commands.get(command['id'])['status'] == 'WAITING_APPROVAL'


def test_watcher_recreate_supersede_is_stable_for_100_reconcile_cycles(tmp_path: Path):
    tasks, decisions, commands, reconciler = _stores(tmp_path)
    decision, command = _pending_watcher_recreate(decisions, commands)
    runtime = _watcher_runtime()

    first = reconciler.reconcile(runtime=runtime, release_validation={})
    assert first['changed_count'] == 1
    decision_after_first = dict(decisions.get(decision['id']))
    command_after_first = dict(commands.get(command['id']))

    for _ in range(100):
        again = reconciler.reconcile(runtime=runtime, release_validation={})
        assert again['changed_count'] == 0
        assert decisions.get(decision['id']) == decision_after_first
        assert commands.get(command['id']) == command_after_first
