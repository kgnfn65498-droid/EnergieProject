#!/usr/bin/env python
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from decision_queue import DecisionQueue
from handoff_queue import HandoffQueue
from handoff_result_ingress import HandoffResultIngressConsumer
from task_engine import TaskStore


class _RoadmapStub:
    def __init__(self):
        self.done = []

    def mark_done_for_task(self, task_id):
        self.done.append(task_id)
        return [{'task_id': task_id, 'status': 'DONE'}]


class StateLifecycleTests(unittest.TestCase):
    def test_task_supersede_preserves_history_and_requires_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            store = TaskStore(Path(td) / 'tasks.json')
            task = store.start('old task', 'old goal', mode='DEVELOPMENT', steps_total=1)
            with self.assertRaisesRegex(ValueError, 'supersede_evidence_required'):
                store.supersede(task['id'], reason='old', evidence_refs=[])
            final = store.supersede(
                task['id'],
                reason='goal already satisfied',
                evidence_refs=['runtime:mode', 'runtime:release'],
                superseded_by='32.4.10',
            )
            self.assertEqual(final['status'], 'SUPERSEDED')
            self.assertEqual(final['title'], 'old task')
            self.assertEqual(final['goal'], 'old goal')
            self.assertEqual(final['superseded_evidence_refs'], ['runtime:mode', 'runtime:release'])
            self.assertEqual(final['superseded_by'], '32.4.10')

    def test_decision_supersede_is_not_approval_or_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            queue = DecisionQueue(Path(td) / 'decisions.json')
            item = queue.request(
                'MODE_CHANGE',
                'naar DEVELOPMENT?',
                context={'target_mode': 'DEVELOPMENT'},
            )
            final = queue.supersede(
                item['id'],
                reason='target mode already authoritative',
                evidence_refs=['runtime:operating_mode'],
                superseded_by='runtime',
            )
            self.assertEqual(final['status'], 'SUPERSEDED')
            self.assertNotIn('approved_by', final)
            self.assertNotIn('resolved_at', final)
            self.assertEqual(final['superseded_evidence_refs'], ['runtime:operating_mode'])

    def test_paused_handoff_can_resume_and_complete_without_displacing_other_active_task(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = TaskStore(Path(td) / 'tasks.json')
            handoff_task = tasks.start('handoff', 'goal', mode='USER', steps_total=1, priority=2)
            handoff_task = tasks.progress(
                handoff_task['id'],
                next_action='handoff:conversation-intake — finish',
            )
            other = tasks.start('new active', 'new work', mode='DEVELOPMENT', steps_total=1, priority=1)
            self.assertEqual(tasks.get(handoff_task['id'])['status'], 'PAUSED')
            resumed = tasks.resume_handoff(
                handoff_task['id'],
                reason='valid result arrived',
                evidence_refs=['handoff-result:abc'],
            )
            self.assertEqual(resumed['status'], 'ACTIVE')
            self.assertEqual(tasks.get(other['id'])['status'], 'ACTIVE')
            done = tasks.complete_handoff(
                handoff_task['id'],
                summary='accepted',
                evidence_refs=['evidence:1'],
            )
            self.assertEqual(done['status'], 'DONE')
            self.assertEqual(tasks.get(other['id'])['status'], 'ACTIVE')

    def test_ingress_resumes_exact_paused_handoff_and_applies_once(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks = TaskStore(root / 'tasks.json')
            handoff_task = tasks.start('handoff', 'goal', mode='USER', steps_total=1, priority=2)
            handoff_task = tasks.progress(
                handoff_task['id'],
                next_action='handoff:conversation-intake — finish',
            )
            handoffs = HandoffQueue(root / 'handoffs.json')
            handoff = handoffs.ensure_for_task(
                handoff_task,
                {
                    'key': 'conversation-intake',
                    'title': 'Conversation Intake',
                    'acceptance': 'live evidence',
                    'priority': 1,
                },
            )
            other = tasks.start('new active', 'new work', mode='DEVELOPMENT', steps_total=1, priority=1)
            self.assertEqual(tasks.get(handoff_task['id'])['status'], 'PAUSED')

            ingress_dir = root / 'HandoffResultIngress'
            ingress_dir.mkdir()
            ingress_id = 'result-001'
            (ingress_dir / f'{ingress_id}.json').write_text(
                json.dumps(
                    {
                        'schema': 'energie_pmv2_handoff_result_v1',
                        'id': ingress_id,
                        'handoff_id': handoff['id'],
                        'outcome': 'DONE',
                        'summary': '32.4.9 live accepted',
                        'evidence_refs': ['runtime:intake:accepted'],
                    }
                ),
                encoding='utf-8',
            )
            roadmap = _RoadmapStub()
            consumer = HandoffResultIngressConsumer(
                ingress_dir,
                root / 'receipts.json',
                handoffs,
                tasks,
                roadmap,
            )
            first = consumer.consume()
            self.assertEqual(len(first), 1)
            self.assertEqual(first[0]['status'], 'APPLIED')
            self.assertTrue(first[0]['resumed_from_paused'])
            self.assertEqual(tasks.get(handoff_task['id'])['status'], 'DONE')
            self.assertEqual(tasks.get(other['id'])['status'], 'ACTIVE')
            self.assertEqual(handoffs.get(handoff['id'])['status'], 'DONE')
            self.assertEqual(roadmap.done, [handoff_task['id']])
            self.assertEqual(consumer.consume(), [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
