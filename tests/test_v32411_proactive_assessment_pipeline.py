#!/usr/bin/env python
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from opportunity_register import OpportunityRegister


def _derive(category, **kwargs):
    path = PM / 'proactive_assessment.py'
    if not path.is_file():
        raise AssertionError('proactive_assessment.py ontbreekt')
    spec = importlib.util.spec_from_file_location('proactive_assessment', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.derive_assessment(category, **kwargs)


class ProactiveAssessmentPipelineTests(unittest.TestCase):
    def test_derived_assessment_has_exact_five_integer_scores(self):
        result = _derive('security', evidence=['https://example.test/advisory'])
        self.assertEqual(set(result), {'relevance', 'impact', 'urgency', 'actionability', 'confidence'})
        self.assertTrue(all(type(value) is int and 0 <= value <= 2 for value in result.values()))

    def test_real_security_style_opportunity_without_manual_assessment_promotes(self):
        with tempfile.TemporaryDirectory() as td:
            store = OpportunityRegister(Path(td) / 'opportunities.json')
            item = store.upsert(
                'market:security:1', category='security', subject='Security advisory changed',
                evidence=['https://example.test/security'], details={'source_id': 'home_assistant_security'},
            )
            self.assertIsInstance(item.get('assessment'), dict)
            self.assertEqual(item['proactive_evaluation']['decision'], 'PROMOTE')
            self.assertEqual(item['status'], 'PROMOTED')

    def test_software_and_conversation_followup_stay_watch_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            store = OpportunityRegister(Path(td) / 'opportunities.json')
            software = store.upsert(
                'market:software:1', category='software', subject='Software alert changed',
                evidence=['https://example.test/software'], details={'source_id': 'home_assistant_alerts'},
            )
            followup = store.upsert(
                'intake:later:1', category='follow_up', subject='Kom hier later op terug',
                evidence=['intake:item:1'], details={'follow_up_policy': 'open_until_reviewed'},
            )
            self.assertEqual(software['proactive_evaluation']['decision'], 'WATCH')
            self.assertEqual(software['status'], 'WATCHING')
            self.assertEqual(followup['proactive_evaluation']['decision'], 'WATCH')
            self.assertEqual(followup['status'], 'WATCHING')

    def test_explicit_assessment_remains_authoritative_over_derived_policy(self):
        with tempfile.TemporaryDirectory() as td:
            store = OpportunityRegister(Path(td) / 'opportunities.json')
            low = {'relevance': 1, 'impact': 1, 'urgency': 0, 'actionability': 0, 'confidence': 1}
            item = store.upsert(
                'security:explicit-low', category='security', subject='Explicitly low confidence/actionability',
                evidence=['source:1'], assessment=low,
            )
            self.assertEqual(item['assessment'], low)
            self.assertEqual(item['proactive_evaluation']['decision'], 'WATCH')
            self.assertEqual(item['status'], 'WATCHING')

    def test_register_status_always_matches_evaluator_and_preserves_notification_history(self):
        with tempfile.TemporaryDirectory() as td:
            store = OpportunityRegister(Path(td) / 'opportunities.json')
            first = store.upsert(
                'regulation:1', category='regulation', subject='Regulation changed',
                evidence=['https://example.test/regulation'],
            )
            expected_first = 'PROMOTED' if first['proactive_evaluation']['decision'] == 'PROMOTE' else 'WATCHING'
            self.assertEqual(first['status'], expected_first)
            material = first['proactive_evaluation']['material_fingerprint']
            store.mark_notified('regulation:1', material_fingerprint=material)
            second = store.upsert(
                'regulation:1', category='regulation', subject='Regulation changed',
                evidence=['https://example.test/regulation'], details={'phase': 2},
            )
            self.assertEqual(second['last_notified_material_fingerprint'], material)
            self.assertEqual(second['proactive_evaluation']['material_fingerprint'], material)
            expected_second = 'PROMOTED' if second['proactive_evaluation']['decision'] == 'PROMOTE' else 'WATCHING'
            self.assertEqual(second['status'], expected_second)


if __name__ == '__main__':
    unittest.main(verbosity=2)
