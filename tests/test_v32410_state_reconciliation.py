from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from command_store import CommandStore
from decision_queue import DecisionQueue
from handoff_queue import HandoffQueue
from issue_store import IssueStore
from state_reconciliation import StateReconciler
from task_engine import TaskStore


def runtime(mode='DEVELOPMENT'):
    return {
        'operating_mode': {
            'effective_mode': mode,
            'source': '/project/Inbox/operating_mode/operating_mode_state.json',
        },
        'release': {'version': '32.4.9', 'source': '/project/App/VERSIE.txt'},
    }


def release_green():
    return {
        'active': False,
        'validation_status': 'ok',
        '_source': '/project/Inbox/operating_mode/release_validation_hold.json',
    }


class StateReconciliationTests(unittest.TestCase):
    def _stores(self, root):
        tasks = TaskStore(root / 'tasks.json')
        decisions = DecisionQueue(root / 'decisions.json')
        commands = CommandStore(root / 'commands.json')
        handoffs = HandoffQueue(root / 'handoffs.json')
        issues = IssueStore(root / 'issues.json')
        reconciler = StateReconciler(tasks, decisions, commands, handoffs, issues)
        return tasks, decisions, commands, handoffs, issues, reconciler

    def _pending_mode(self, decisions, commands, target='DEVELOPMENT', **extra):
        command = commands.enqueue({
            'intent': 'start_development' if target == 'DEVELOPMENT' else 'start_maintenance',
            'source': 'mcp_remote',
            'title': 'mode request',
            'goal': 'mode request',
            'artifact_path': extra.get('artifact_path', ''),
            'artifact_sha256': extra.get('artifact_sha256', ''),
            'release_version': extra.get('release_version', ''),
            'verification_report': extra.get('verification_report', ''),
        })
        decision = decisions.request(
            'MODE_CHANGE',
            f'naar {target}?',
            context={
                'command_id': command['id'],
                'intent': command['intent'],
                'target_mode': target,
                'artifact_path': extra.get('artifact_path'),
                'artifact_sha256': extra.get('artifact_sha256'),
                'release_version': extra.get('release_version'),
                'verification_report': extra.get('verification_report'),
            },
        )
        command = commands.wait_for_approval(command['id'], decision_id=decision['id'])
        return decision, command

    def test_mode_match_alone_is_review_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, handoffs, issues, reconciler = self._stores(root)
            decision, command = self._pending_mode(decisions, commands)
            result = reconciler.reconcile(runtime=runtime(), release_validation=None)
            row = next(item for item in result['items'] if item['id'] == decision['id'])
            self.assertEqual(row['disposition'], 'REVIEW_REQUIRED')
            self.assertFalse(row['changed'])
            self.assertEqual(decisions.get(decision['id'])['status'], 'PENDING')
            self.assertEqual(commands.get(command['id'])['status'], 'WAITING_APPROVAL')

    def test_pure_mode_change_supersedes_with_authoritative_mode_and_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, handoffs, issues, reconciler = self._stores(root)
            decision, command = self._pending_mode(decisions, commands)
            result = reconciler.reconcile(runtime=runtime(), release_validation=release_green())
            row = next(item for item in result['items'] if item['id'] == decision['id'])
            self.assertEqual(row['disposition'], 'SUPERSEDED')
            self.assertTrue(row['changed'])
            final_decision = decisions.get(decision['id'])
            self.assertEqual(final_decision['status'], 'SUPERSEDED')
            self.assertNotIn('approved_by', final_decision)
            final_command = commands.get(command['id'])
            self.assertEqual(final_command['status'], 'CANCELLED')
            self.assertTrue(final_command['cancellation_reason'].startswith('superseded_by_state_reconciliation:'))

    def test_mode_change_with_artifact_payload_is_not_auto_superseded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, handoffs, issues, reconciler = self._stores(root)
            decision, command = self._pending_mode(decisions, commands, artifact_path='/tmp/release.zip')
            result = reconciler.reconcile(runtime=runtime(), release_validation=release_green())
            row = next(item for item in result['items'] if item['id'] == decision['id'])
            self.assertEqual(row['disposition'], 'REVIEW_REQUIRED')
            self.assertEqual(decisions.get(decision['id'])['status'], 'PENDING')
            self.assertEqual(commands.get(command['id'])['status'], 'WAITING_APPROVAL')

    def test_production_decision_is_never_auto_superseded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, handoffs, issues, reconciler = self._stores(root)
            decision = decisions.request('PRODUCTION_DEPLOY', 'deploy?', context={'command_id': 'missing'})
            result = reconciler.reconcile(runtime=runtime(), release_validation=release_green())
            row = next(item for item in result['items'] if item['id'] == decision['id'])
            self.assertEqual(row['disposition'], 'ACTIVE_KEEP')
            self.assertFalse(row['changed'])
            self.assertEqual(decisions.get(decision['id'])['status'], 'PENDING')

    def test_old_task_without_explicit_proof_is_review_required(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, handoffs, issues, reconciler = self._stores(root)
            task = tasks.start(
                '32.4.4 development mode',
                'Zet de basis-modus naar DEVELOPMENT voor gecontroleerde releaseverwerking van 32.4.4.',
                mode='DEVELOPMENT',
                steps_total=1,
                priority=1,
            )
            result = reconciler.reconcile(runtime=runtime(), release_validation=release_green())
            row = next(item for item in result['items'] if item['id'] == task['id'])
            self.assertEqual(row['disposition'], 'REVIEW_REQUIRED')
            self.assertFalse(row['changed'])
            self.assertEqual(tasks.get(task['id'])['status'], 'ACTIVE')

    def test_explicit_machine_proof_can_supersede_task(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, handoffs, issues, reconciler = self._stores(root)
            task = tasks.start('old', 'goal', mode='USER', steps_total=1)
            data = tasks._load()
            stored = next(item for item in data['tasks'] if item['id'] == task['id'])
            stored['reconciliation_proof'] = {
                'goal_satisfied': True,
                'reason': 'later runtime evidence satisfies goal',
                'evidence_refs': ['runtime:a', 'runtime:b'],
                'superseded_by': 'later-runtime',
            }
            tasks._save(data)
            result = reconciler.reconcile(runtime=runtime(), release_validation=release_green())
            row = next(item for item in result['items'] if item['id'] == task['id'])
            self.assertEqual(row['disposition'], 'SUPERSEDED')
            self.assertTrue(row['changed'])
            self.assertEqual(tasks.get(task['id'])['status'], 'SUPERSEDED')

    def test_reconciliation_is_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks, decisions, commands, handoffs, issues, reconciler = self._stores(root)
            decision, command = self._pending_mode(decisions, commands)
            first = reconciler.reconcile(runtime=runtime(), release_validation=release_green())
            second = reconciler.reconcile(runtime=runtime(), release_validation=release_green())
            self.assertEqual(first['changed_count'], 1)
            self.assertEqual(second['changed_count'], 0)
            self.assertEqual(decisions.get(decision['id'])['status'], 'SUPERSEDED')
            self.assertEqual(commands.get(command['id'])['status'], 'CANCELLED')


if __name__ == '__main__':
    unittest.main(verbosity=2)
