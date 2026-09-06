#!/usr/bin/env python
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from opportunity_register import OpportunityRegister
from proactive_policy import evaluate_signal, material_fingerprint


SCORES_7 = {
    'relevance': 2,
    'impact': 2,
    'urgency': 1,
    'actionability': 1,
    'confidence': 1,
}


class ProactivePolicyTests(unittest.TestCase):
    def test_normal_signal_requires_evidence_and_seven_points(self):
        no_evidence = {
            'category': 'supplier',
            'subject': 'Contractkans',
            'evidence': [],
            'assessment': SCORES_7,
        }
        self.assertEqual(evaluate_signal(no_evidence)['decision'], 'WATCH')

        six = dict(SCORES_7)
        six['confidence'] = 0
        low = {
            'category': 'supplier',
            'subject': 'Contractkans',
            'evidence': ['source:contract'],
            'assessment': six,
        }
        self.assertEqual(evaluate_signal(low)['total_score'], 6)
        self.assertEqual(evaluate_signal(low)['decision'], 'WATCH')

        enough = dict(low, assessment=dict(SCORES_7))
        result = evaluate_signal(enough)
        self.assertEqual(result['total_score'], 7)
        self.assertEqual(result['decision'], 'PROMOTE')
        self.assertFalse(result['hard_gate'])

    def test_actionability_zero_never_promotes_even_at_high_total(self):
        item = {
            'category': 'supplier',
            'subject': 'Niet handelbare observatie',
            'evidence': ['source:1'],
            'assessment': {
                'relevance': 2,
                'impact': 2,
                'urgency': 2,
                'actionability': 0,
                'confidence': 2,
            },
        }
        result = evaluate_signal(item)
        self.assertEqual(result['total_score'], 8)
        self.assertEqual(result['decision'], 'WATCH')

    def test_invalid_score_field_fails_closed_to_review_required(self):
        item = {
            'category': 'supplier',
            'subject': 'Ongeldige score',
            'evidence': ['source:1'],
            'assessment': {
                'relevance': 2,
                'impact': 2,
                'urgency': 3,
                'actionability': 1,
                'confidence': 1,
            },
        }
        result = evaluate_signal(item)
        self.assertEqual(result['decision'], 'REVIEW_REQUIRED')
        self.assertIsNone(result['total_score'])

    def test_hard_category_requires_evidence_urgency_and_confidence(self):
        base = {
            'category': 'security',
            'subject': 'Security advisory',
            'evidence': ['advisory:1'],
            'assessment': {
                'relevance': 0,
                'impact': 0,
                'urgency': 0,
                'actionability': 0,
                'confidence': 2,
            },
        }
        self.assertEqual(evaluate_signal(base)['decision'], 'WATCH')

        confident_but_no_evidence = dict(base, evidence=[])
        confident_but_no_evidence['assessment'] = dict(base['assessment'], urgency=1)
        self.assertEqual(evaluate_signal(confident_but_no_evidence)['decision'], 'WATCH')

        promoted = dict(base)
        promoted['assessment'] = dict(base['assessment'], urgency=1, confidence=1)
        result = evaluate_signal(promoted)
        self.assertEqual(result['decision'], 'PROMOTE')
        self.assertTrue(result['hard_gate'])

    def test_material_fingerprint_changes_for_material_change_only(self):
        item = {
            'category': 'supplier',
            'subject': 'Contractkans',
            'evidence': ['source:a'],
            'annual_saving_eur': 120,
            'payback_years': None,
            'compatible': True,
            'assessment': dict(SCORES_7),
            'updated_at': '2026-09-06T00:00:00+00:00',
        }
        first = material_fingerprint(item)
        same = dict(item, updated_at='2026-09-07T00:00:00+00:00')
        self.assertEqual(first, material_fingerprint(same))

        changed_impact = dict(item)
        changed_impact['assessment'] = dict(SCORES_7, impact=1)
        self.assertNotEqual(first, material_fingerprint(changed_impact))

        changed_evidence = dict(item, evidence=['source:b'])
        self.assertNotEqual(first, material_fingerprint(changed_evidence))

    def test_register_preserves_notification_history_across_upsert(self):
        with tempfile.TemporaryDirectory() as td:
            store = OpportunityRegister(Path(td) / 'register.json')
            first = store.upsert(
                'supplier:test',
                category='supplier',
                subject='Contractkans',
                evidence=['source:a'],
                annual_saving_eur=120,
                assessment=dict(SCORES_7),
                details={'phase': 1},
            )
            material = first['proactive_evaluation']['material_fingerprint']
            notified = store.mark_notified(
                'supplier:test', material_fingerprint=material
            )
            self.assertEqual(notified['last_notified_material_fingerprint'], material)

            second = store.upsert(
                'supplier:test',
                category='supplier',
                subject='Contractkans',
                evidence=['source:a'],
                annual_saving_eur=120,
                assessment=dict(SCORES_7),
                details={'phase': 2},
            )
            self.assertEqual(second['last_notified_material_fingerprint'], material)
            self.assertTrue(second.get('last_notified_at'))
            self.assertEqual(second['proactive_evaluation']['decision'], 'PROMOTE')
            self.assertEqual(len(store.all()), 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
