#!/usr/bin/env python
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from command_store import CommandStore
from decision_queue import DecisionQueue
from issue_store import IssueStore
from state_reconciliation import StateReconciler
from task_engine import TaskStore

LEGACY_TASK_ID = '9baa6fc1ae384379a1192004762bf8fa'


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _runtime():
    return {
        'operating_mode': {
            'effective_mode': 'DEVELOPMENT',
            'source': '/project/Inbox/operating_mode/operating_mode_state.json',
        },
        'release': {
            'version': '32.4.11',
            'source': '/project/App/VERSIE.txt',
        },
    }


def _release_green():
    return {
        'active': False,
        'validation_status': 'ok',
        '_source': '/project/Inbox/operating_mode/release_validation_hold.json',
    }


def _collector():
    path = PM / 'issue_repair_evidence.py'
    if not path.is_file():
        raise AssertionError('issue_repair_evidence.py ontbreekt')
    spec = importlib.util.spec_from_file_location('issue_repair_evidence', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.collect_issue_repair_evidence


class ReconciliationClosureTests(unittest.TestCase):
    def _stores(self, root: Path):
        return (
            TaskStore(root / 'state/tasks.json'),
            DecisionQueue(root / 'decisions/queue.json'),
            CommandStore(root / 'commands/queue.json'),
            IssueStore(root / 'issues/issues.json'),
        )

    def test_exact_known_legacy_task_supersedes_only_with_authoritative_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, issues = self._stores(root)
            _write_json(root / 'state/tasks.json', {
                'schema': 1,
                'tasks': [{
                    'id': LEGACY_TASK_ID,
                    'title': 'legacy title intentionally irrelevant',
                    'goal': 'legacy goal intentionally irrelevant',
                    'mode': 'DEVELOPMENT',
                    'status': 'ACTIVE',
                    'priority': 1,
                    'created_at': '2026-09-05T12:13:39+00:00',
                    'updated_at': '2026-09-05T12:13:39+00:00',
                    'next_action': 'legacy',
                    'blockers': [], 'changes': [], 'evidence_refs': [],
                    'step': 1, 'steps_total': 1,
                }],
            })
            reconciler = StateReconciler(tasks, decisions, commands, None, issues)
            result = reconciler.reconcile(runtime=_runtime(), release_validation=_release_green())
            row = next(item for item in result['items'] if item['entity_type'] == 'task')
            self.assertEqual(row['disposition'], 'SUPERSEDED')
            final = tasks.get(LEGACY_TASK_ID)
            self.assertEqual(final['status'], 'SUPERSEDED')
            self.assertIn('/project/App/VERSIE.txt', final['superseded_evidence_refs'])
            self.assertIn('/project/Inbox/operating_mode/operating_mode_state.json', final['superseded_evidence_refs'])
            self.assertIn('/project/Inbox/operating_mode/release_validation_hold.json', final['superseded_evidence_refs'])

    def test_near_miss_legacy_task_id_never_uses_special_rule(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, issues = self._stores(root)
            _write_json(root / 'state/tasks.json', {
                'schema': 1,
                'tasks': [{
                    'id': LEGACY_TASK_ID + 'x', 'title': '32.4.4 development mode',
                    'goal': 'same words are not proof', 'mode': 'DEVELOPMENT',
                    'status': 'ACTIVE', 'priority': 1, 'next_action': 'legacy',
                    'blockers': [], 'changes': [], 'evidence_refs': [],
                    'step': 1, 'steps_total': 1,
                    'created_at': '2026-09-05T12:13:39+00:00',
                    'updated_at': '2026-09-05T12:13:39+00:00',
                }],
            })
            result = StateReconciler(tasks, decisions, commands, None, issues).reconcile(
                runtime=_runtime(), release_validation=_release_green()
            )
            row = next(item for item in result['items'] if item['entity_type'] == 'task')
            self.assertEqual(row['disposition'], 'REVIEW_REQUIRED')
            self.assertEqual(tasks.get(LEGACY_TASK_ID + 'x')['status'], 'ACTIVE')

    def test_later_success_receipts_close_only_supported_historical_issue_classes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, issues = self._stores(root)
            command_issue = issues.open(
                'command_ingress:old-command', severity='ORANGE',
                title='old command permission', details={'reason': "PermissionError: [Errno 13] Permission denied"},
            )
            handoff_issue = issues.open(
                'handoff_result_ingress:old-handoff', severity='ORANGE',
                title='old paused handoff', details={'reason': 'ValueError: handoff task cannot complete from PAUSED'},
            )
            other_issue = issues.open(
                'command_ingress:other', severity='ORANGE',
                title='different failure', details={'reason': 'ValueError: invalid schema'},
            )
            data = json.loads((root / 'issues/issues.json').read_text(encoding='utf-8'))
            for item in data['items']:
                item['last_seen_at'] = '2026-09-06T12:00:00+00:00'
            _write_json(root / 'issues/issues.json', data)

            _write_json(root / 'commands/ingress_receipts.json', {
                'schema': 1,
                'items': {
                    'old-command': {'status': 'REJECTED', 'at': '2026-09-06T11:00:00+00:00', 'reason': 'PermissionError'},
                    'new-command': {'status': 'IMPORTED', 'at': '2026-09-06T21:00:00+00:00', 'command_id': 'c-new', 'intent': 'status_query'},
                },
            })
            _write_json(root / 'handoffs/result_ingress_receipts.json', {
                'schema': 1,
                'items': {
                    'old-handoff': {'status': 'REJECTED', 'at': '2026-09-06T11:30:00+00:00', 'reason': 'ValueError: handoff task cannot complete from PAUSED'},
                    'new-handoff': {'status': 'APPLIED', 'at': '2026-09-06T21:05:00+00:00', 'resumed_from_paused': True, 'handoff_id': 'h1'},
                },
            })

            repairs = _collector()(root, issues.open_items())
            self.assertIn(command_issue['id'], repairs)
            self.assertIn(handoff_issue['id'], repairs)
            self.assertNotIn(other_issue['id'], repairs)

            try:
                result = StateReconciler(tasks, decisions, commands, None, issues).reconcile(
                    runtime=_runtime(), release_validation=_release_green(), issue_repairs=repairs
                )
            except TypeError as exc:
                raise AssertionError('StateReconciler.reconcile mist issue_repairs contract') from exc
            dispositions = {item['id']: item['disposition'] for item in result['items'] if item['entity_type'] == 'issue'}
            self.assertEqual(dispositions[command_issue['id']], 'RESOLVED')
            self.assertEqual(dispositions[handoff_issue['id']], 'RESOLVED')
            self.assertEqual(dispositions[other_issue['id']], 'ACTIVE_KEEP')
            open_ids = {item['id'] for item in issues.open_items()}
            self.assertNotIn(command_issue['id'], open_ids)
            self.assertNotIn(handoff_issue['id'], open_ids)
            self.assertIn(other_issue['id'], open_ids)

    def test_orchestrator_collects_and_passes_issue_repair_evidence(self):
        source = (PM / 'orchestrator.py').read_text(encoding='utf-8')
        self.assertIn('from issue_repair_evidence import collect_issue_repair_evidence', source)
        run_once = source.split('    def run_once(self, *, now=None):', 1)[1].split('\n    def _refresh_coordination', 1)[0]
        self.assertIn('issue_repairs = collect_issue_repair_evidence(', run_once)
        self.assertIn('issue_repairs=issue_repairs', run_once)


if __name__ == '__main__':
    unittest.main(verbosity=2)
