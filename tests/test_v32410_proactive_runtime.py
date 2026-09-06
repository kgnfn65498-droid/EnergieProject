import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from alert_policy import AlertState
from manager_service import ManagerService
from notification_router import notification_route
from notification_transport import NotificationOutbox
from opportunity_register import OpportunityRegister


SCORES_HIGH = {
    'relevance': 2,
    'impact': 2,
    'urgency': 1,
    'actionability': 2,
    'confidence': 2,
}
SCORES_LOW = {
    'relevance': 1,
    'impact': 1,
    'urgency': 1,
    'actionability': 1,
    'confidence': 1,
}


class _Audit:
    def __init__(self):
        self.events = []

    def write(self, event_type, **kwargs):
        self.events.append((event_type, kwargs))


class _Notifier:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    def send(self, title, message, *, severity, notification_id):
        self.calls.append({
            'title': title,
            'message': message,
            'severity': severity,
            'notification_id': notification_id,
        })
        if self.ok:
            return {'ok': True, 'transport': 'test'}
        return {'ok': False, 'reason': 'test_failure'}


def _service(root: Path, *, notifier_ok=True):
    service = ManagerService.__new__(ManagerService)
    service.opportunities = OpportunityRegister(root / 'opportunities.json')
    service.outbox = NotificationOutbox(root / 'outbox')
    service.alerts = AlertState(root / 'alerts.json', cooldown_seconds=21600)
    service.audit = _Audit()
    service.notifier = _Notifier(ok=notifier_ok)
    return service


class ProactiveRuntimeTests(unittest.TestCase):
    def test_proactive_direct_is_an_explicit_direct_route(self):
        self.assertEqual(notification_route('GREEN', False, True), 'DIRECT')
        self.assertEqual(notification_route('ORANGE', False, True), 'DIRECT')
        self.assertEqual(notification_route('GREEN', False, False), 'LOG_ONLY')

    def test_high_value_actionable_signal_queues_one_direct_notification(self):
        with tempfile.TemporaryDirectory() as td:
            service = _service(Path(td))
            item = service.opportunities.upsert(
                'saving:1',
                category='saving',
                subject='Besparing mogelijk',
                evidence=['evidence:saving:1'],
                annual_saving_eur=120,
                assessment=SCORES_HIGH,
            )
            now = datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
            result = service._reconcile_proactive(now=now)
            self.assertEqual(len(result['promoted']), 1)
            pending = service.outbox.pending()
            self.assertEqual(len(pending), 1)
            payload = pending[0][1]
            self.assertTrue(payload['proactive_direct'])
            self.assertEqual(payload['opportunity_fingerprint'], 'saving:1')
            self.assertEqual(
                payload['material_fingerprint'],
                item['proactive_evaluation']['material_fingerprint'],
            )

    def test_same_material_fingerprint_does_not_queue_again_pending_or_delivered(self):
        with tempfile.TemporaryDirectory() as td:
            service = _service(Path(td))
            service.opportunities.upsert(
                'saving:dedupe',
                category='saving',
                subject='Zelfde signaal',
                evidence=['evidence:dedupe'],
                annual_saving_eur=100,
                assessment=SCORES_HIGH,
            )
            now = datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
            service._reconcile_proactive(now=now)
            service._reconcile_proactive(now=now + timedelta(minutes=5))
            self.assertEqual(len(service.outbox.pending()), 1)

            delivered = service._dispatch_outbox()
            self.assertEqual(len(delivered), 1)
            self.assertEqual(len(service.outbox.pending()), 0)
            stored = service.opportunities.all()[0]
            material = stored['proactive_evaluation']['material_fingerprint']
            self.assertEqual(stored['last_notified_material_fingerprint'], material)

            service._reconcile_proactive(now=now + timedelta(hours=7))
            self.assertEqual(len(service.outbox.pending()), 0)

    def test_failed_delivery_stays_pending_and_never_duplicates_after_cooldown(self):
        with tempfile.TemporaryDirectory() as td:
            service = _service(Path(td), notifier_ok=False)
            service.opportunities.upsert(
                'saving:failed',
                category='saving',
                subject='Tijdelijke notifierfout',
                evidence=['evidence:failed'],
                annual_saving_eur=80,
                assessment=SCORES_HIGH,
            )
            now = datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
            service._reconcile_proactive(now=now)
            service._dispatch_outbox()
            self.assertEqual(len(service.outbox.pending()), 1)
            service._reconcile_proactive(now=now + timedelta(hours=7))
            self.assertEqual(len(service.outbox.pending()), 1)

    def test_material_change_can_queue_again_after_confirmed_delivery(self):
        with tempfile.TemporaryDirectory() as td:
            service = _service(Path(td))
            service.opportunities.upsert(
                'saving:change',
                category='saving',
                subject='Materiele wijziging',
                evidence=['evidence:v1'],
                annual_saving_eur=100,
                assessment=SCORES_HIGH,
            )
            now = datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
            service._reconcile_proactive(now=now)
            service._dispatch_outbox()
            first = service.opportunities.all()[0]['last_notified_material_fingerprint']

            changed = service.opportunities.upsert(
                'saving:change',
                category='saving',
                subject='Materiele wijziging',
                evidence=['evidence:v1', 'evidence:v2'],
                annual_saving_eur=160,
                assessment=SCORES_HIGH,
            )
            second = changed['proactive_evaluation']['material_fingerprint']
            self.assertNotEqual(first, second)
            service._reconcile_proactive(now=now + timedelta(minutes=10))
            self.assertEqual(len(service.outbox.pending()), 1)
            self.assertEqual(service.outbox.pending()[0][1]['material_fingerprint'], second)

    def test_low_score_stays_watching_without_outbox_item(self):
        with tempfile.TemporaryDirectory() as td:
            service = _service(Path(td))
            service.opportunities.upsert(
                'saving:low',
                category='saving',
                subject='Lage waarde',
                evidence=['evidence:low'],
                annual_saving_eur=10,
                assessment=SCORES_LOW,
            )
            result = service._reconcile_proactive(
                now=datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
            )
            self.assertEqual(result['watching_count'], 1)
            self.assertEqual(result['promoted'], [])
            self.assertEqual(len(service.outbox.pending()), 0)

    def test_unscheduled_later_return_is_visible_but_not_direct(self):
        with tempfile.TemporaryDirectory() as td:
            service = _service(Path(td))
            service.opportunities.upsert(
                'intake:later',
                category='follow_up',
                subject='Kom hier later op terug',
                evidence=['intake:item:1'],
                details={
                    'follow_up_policy': 'open_until_reviewed',
                    'intake_id': 'item-1',
                },
            )
            result = service._reconcile_proactive(
                now=datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
            )
            self.assertEqual(len(result['followups_open']), 1)
            self.assertEqual(result['followups_open'][0]['fingerprint'], 'intake:later')
            self.assertEqual(len(service.outbox.pending()), 0)

    def test_proactive_signal_only_queues_notification_never_protected_execution(self):
        with tempfile.TemporaryDirectory() as td:
            service = _service(Path(td))
            service.protected_executor = object()
            service.opportunities.upsert(
                'risk:protected',
                category='contract_risk',
                subject='Contractactie vereist Peter',
                evidence=['contract:evidence'],
                assessment=SCORES_HIGH,
                details={'protected_action': 'production_deploy'},
            )
            result = service._reconcile_proactive(
                now=datetime(2026, 9, 6, 13, 0, tzinfo=timezone.utc)
            )
            self.assertEqual(len(result['promoted']), 1)
            self.assertEqual(len(service.outbox.pending()), 1)
            self.assertFalse(hasattr(service, 'commands'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
