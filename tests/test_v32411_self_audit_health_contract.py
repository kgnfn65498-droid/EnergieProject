#!/usr/bin/env python
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

import health_engine
from self_audit import SelfAuditor


def _write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _runtime(root: Path, *, task_status='SUPERSEDED', decision_status='SUPERSEDED'):
    now = datetime.now(timezone.utc).isoformat()
    _write_json(root / 'status/current.json', {
        'mode': 'DEVELOPMENT', 'health': {'status': 'GREEN'},
        'updated_at': now, 'release': {'version': '32.4.11'},
    })
    _write_json(root / 'heartbeat/manager.json', {
        'mode': 'DEVELOPMENT', 'health': 'GREEN', 'heartbeat_at': now,
    })
    _write_json(root / 'handover/current.json', {
        'mode': 'DEVELOPMENT', 'release': {'version': '32.4.11'},
    })
    (root / 'audit').mkdir(parents=True, exist_ok=True)
    (root / 'audit/events.jsonl').write_text(json.dumps({'event_type': 'test'}) + '\n', encoding='utf-8')
    _write_json(root / 'state/tasks.json', {'schema': 1, 'tasks': [{'id': 't1', 'status': task_status}]})
    _write_json(root / 'decisions/queue.json', {'schema': 1, 'items': [{'id': 'd1', 'status': decision_status}]})
    version = root.parent / 'VERSIE.txt'
    version.write_text('32.4.11\n', encoding='utf-8')
    return version


def _composite(checks, self_audit):
    fn = getattr(health_engine, 'summarize_health_with_self_audit', None)
    if fn is None:
        raise AssertionError('summarize_health_with_self_audit ontbreekt')
    return fn(checks, self_audit)


class SelfAuditHealthContractTests(unittest.TestCase):
    def test_superseded_task_and_decision_are_valid_self_audit_states(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'RuntimeV2'
            version = _runtime(root)
            result = SelfAuditor(root, production_version_path=version).run()
            self.assertEqual(result['status'], 'GREEN', result)

    def test_unknown_lifecycle_status_remains_red(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / 'RuntimeV2'
            version = _runtime(root, task_status='FROZEN')
            result = SelfAuditor(root, production_version_path=version).run()
            self.assertEqual(result['status'], 'RED')
            self.assertIn({'path': 'state/tasks.json', 'reason': 'invalid_item_status'}, result['invalid'])

    def test_self_audit_red_makes_composite_health_red(self):
        result = _composite(
            [{'name': 'energy', 'status': 'GREEN', 'reason': 'ok'}],
            {'status': 'RED', 'invalid': [{'path': 'x', 'reason': 'broken'}]},
        )
        self.assertEqual(result['status'], 'RED')
        self.assertEqual(result['attention_count'], 1)
        self.assertEqual(result['checks'][-1]['name'], 'projectmanager_self_audit')
        self.assertEqual(result['checks'][-1]['status'], 'RED')

    def test_self_audit_green_preserves_all_green_health(self):
        result = _composite(
            [{'name': 'energy', 'status': 'GREEN', 'reason': 'ok'}],
            {'status': 'GREEN', 'invalid': [], 'warnings': []},
        )
        self.assertEqual(result['status'], 'GREEN')
        self.assertEqual(result['attention_count'], 0)

    def test_manager_service_final_status_and_heartbeat_use_composite_health(self):
        source = (PM / 'manager_service.py').read_text(encoding='utf-8')
        run_once = source.split('    def run_once(self, *, now=None) -> dict:', 1)[1].split('\n    def _reconcile_mode', 1)[0]
        required = [
            'self_audit = self.self_auditor.run(now=now)',
            'composite_health = summarize_health_with_self_audit(checks, self_audit)',
            "heartbeat['health'] = composite_health['status']",
            "status['health'] = composite_health",
        ]
        for token in required:
            self.assertIn(token, run_once)
        audit_at = run_once.index(required[0])
        composite_at = run_once.index(required[1])
        heartbeat_at = run_once.index(required[2])
        final_status_at = run_once.rindex("atomic_write_json(self.root / 'status' / 'current.json', status)")
        self.assertLess(audit_at, composite_at)
        self.assertLess(composite_at, heartbeat_at)
        self.assertLess(heartbeat_at, final_status_at)


if __name__ == '__main__':
    unittest.main(verbosity=2)
