#!/usr/bin/env python
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))

from conversation_intake import ConversationIntakeBridge, route_for_classification
from document_sync import ManagedDocumentSync
from opportunity_register import OpportunityRegister
from task_engine import TaskStore


class IntakeFollowupTests(unittest.TestCase):
    def _bridge(self, td):
        root = Path(td)
        tasks = TaskStore(root / 'RuntimeV2/state/tasks.json')
        active = tasks.start(
            '32.4.10 active', 'keep active task',
            mode='DEVELOPMENT', steps_total=7, priority=1,
        )
        reports = root / 'reports'
        (reports / 'KnowledgeBase').mkdir(parents=True)
        opportunities = OpportunityRegister(root / 'RuntimeV2/opportunities/register.json')
        bridge = ConversationIntakeBridge(
            root / 'RuntimeV2/intake/items.json',
            tasks,
            ManagedDocumentSync(),
            reports,
            opportunity_register=opportunities,
        )
        return bridge, tasks, active, opportunities, reports

    def test_idea_intake_creates_traceable_watching_opportunity(self):
        with tempfile.TemporaryDirectory() as td:
            bridge, tasks, active, opportunities, reports = self._bridge(td)
            result = bridge.accept({
                'text': 'Misschien is een andere laadstrategie een goed idee',
                'source_channel': 'chatgpt',
                'source_ref': 'chat:idea:32410:1',
                'classification_hint': 'idea_opportunity',
            })
            self.assertEqual(result['classification'], 'idea_opportunity')
            self.assertEqual(result['routes'], ['wishlist'])
            items = opportunities.all()
            self.assertEqual(len(items), 1)
            item = items[0]
            self.assertEqual(item['fingerprint'], f"intake:{result['fingerprint']}")
            self.assertEqual(item['category'], 'conversation_opportunity')
            self.assertEqual(item['proactive_evaluation']['decision'], 'WATCH')
            self.assertEqual(item['proactive_evaluation']['reason'], 'assessment_missing')
            self.assertEqual(item['details']['intake_id'], result['id'])
            self.assertEqual(item['details']['source_channel'], 'chatgpt')
            self.assertEqual(item['details']['source_ref'], 'chat:idea:32410:1')
            self.assertTrue(item['evidence'][0].endswith(f"#{result['id']}"))
            self.assertNotIn('last_notified_at', item)
            self.assertEqual(tasks.active()['id'], active['id'])
            wishlist = (reports / 'KnowledgeBase/Wensenlijst.md').read_text(encoding='utf-8')
            self.assertIn('chat:idea:32410:1', wishlist)

    def test_later_return_creates_open_followup_without_invented_due_date(self):
        with tempfile.TemporaryDirectory() as td:
            bridge, tasks, active, opportunities, _ = self._bridge(td)
            result = bridge.accept({
                'text': 'Kom hier later op terug',
                'source_channel': 'speech',
                'source_ref': 'speech:later:32410:1',
                'classification_hint': 'later_return',
            })
            item = opportunities.all()[0]
            self.assertEqual(item['fingerprint'], f"intake:{result['fingerprint']}")
            self.assertEqual(item['category'], 'follow_up')
            self.assertEqual(item['details']['follow_up_policy'], 'open_until_reviewed')
            self.assertNotIn('due_at', item)
            self.assertNotIn('due_at', item['details'])
            self.assertNotIn('last_notified_at', item)
            self.assertEqual(item['proactive_evaluation']['decision'], 'WATCH')
            self.assertEqual(tasks.active()['id'], active['id'])

    def test_duplicate_intake_does_not_duplicate_opportunity(self):
        with tempfile.TemporaryDirectory() as td:
            bridge, _, _, opportunities, _ = self._bridge(td)
            command = {
                'text': 'Misschien is dit een kans',
                'source_channel': 'nomad',
                'source_ref': 'nomad:idea:duplicate:32410',
                'classification_hint': 'idea_opportunity',
            }
            first = bridge.accept(command)
            second = bridge.accept(command)
            self.assertFalse(first['duplicate'])
            self.assertTrue(second['duplicate'])
            self.assertEqual(len(opportunities.all()), 1)
            self.assertEqual(opportunities.all()[0]['fingerprint'], f"intake:{first['fingerprint']}")

    def test_non_followup_classifications_keep_existing_routes_without_opportunity(self):
        with tempfile.TemporaryDirectory() as td:
            bridge, tasks, active, opportunities, _ = self._bridge(td)
            result = bridge.accept({
                'text': 'Dit moet voortaan een harde eis zijn',
                'source_channel': 'chatgpt',
                'source_ref': 'chat:hard:32410:1',
                'classification_hint': 'hard_requirement',
            })
            self.assertEqual(result['routes'], ['knowledge_base', 'roadmap'])
            self.assertEqual(route_for_classification('hard_requirement'), ['knowledge_base', 'roadmap'])
            self.assertEqual(opportunities.all(), [])
            self.assertEqual(tasks.active()['id'], active['id'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
