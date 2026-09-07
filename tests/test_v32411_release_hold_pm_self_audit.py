#!/usr/bin/env python
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
sys.path.insert(0, str(APP))

import operating_mode_runtime as mode_runtime


def _check(root):
    fn = getattr(mode_runtime, '_projectmanager_self_audit_check', None)
    if fn is None:
        raise AssertionError('_projectmanager_self_audit_check ontbreekt')
    return fn(root)


class ReleaseHoldPmSelfAuditTests(unittest.TestCase):
    def _write_runtime_release(self, root: Path, release='32.4.11'):
        version = root / 'App/VERSIE.txt'
        version.parent.mkdir(parents=True, exist_ok=True)
        version.write_text(release + '\n', encoding='utf-8')
        status = root / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
        status.parent.mkdir(parents=True, exist_ok=True)
        status.write_text(json.dumps({
            'release': {'version': release},
            'updated_at': '2026-09-07T07:00:00+00:00',
        }), encoding='utf-8')
        return status

    def _write(self, root: Path, payload, *, release='32.4.11'):
        status = self._write_runtime_release(root, release=release)
        path = root / 'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding='utf-8')
        status_mtime = status.stat().st_mtime
        os.utime(path, (status_mtime + 1.0, status_mtime + 1.0))
        return path

    def test_green_pm_self_audit_allows_check(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, {'status': 'GREEN', 'invalid': [], 'warnings': []})
            result = _check(root)
            self.assertTrue(result['ok'])
            self.assertIn('GREEN', result['detail'])

    def test_red_pm_self_audit_blocks_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, {'status': 'RED', 'invalid': [{'path': 'x'}]})
            result = _check(root)
            self.assertFalse(result['ok'])
            self.assertIn('RED', result['detail'])

    def test_missing_pm_self_audit_blocks_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write_runtime_release(root)
            result = _check(root)
            self.assertFalse(result['ok'])
            self.assertIn('missing', result['detail'])

    def test_malformed_pm_self_audit_blocks_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            status = self._write_runtime_release(root)
            path = root / 'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{broken', encoding='utf-8')
            os.utime(path, (status.stat().st_mtime + 1.0, status.stat().st_mtime + 1.0))
            result = _check(root)
            self.assertFalse(result['ok'])
            self.assertIn('invalid', result['detail'])

    def test_old_green_audit_cannot_validate_new_release(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = self._write(root, {'status': 'GREEN', 'invalid': [], 'warnings': []}, release='32.4.10')
            (root / 'App/VERSIE.txt').write_text('32.4.11\n', encoding='utf-8')
            result = _check(root)
            self.assertFalse(result['ok'])
            self.assertIn('release mismatch', result['detail'])
            self.assertTrue(audit.is_file())

    def test_green_audit_older_than_current_status_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            audit = self._write(root, {'status': 'GREEN', 'invalid': [], 'warnings': []})
            status = root / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
            newer = max(time.time(), audit.stat().st_mtime + 2.0)
            os.utime(status, (newer, newer))
            result = _check(root)
            self.assertFalse(result['ok'])
            self.assertIn('stale', result['detail'])

    def test_release_validation_contract_calls_pm_self_audit_gate(self):
        source = (APP / 'operating_mode_runtime.py').read_text(encoding='utf-8')
        validation = source.split('def validate_release_hold(', 1)[1].split('\ndef ', 1)[0]
        self.assertIn('projectmanager_self_audit', validation)
        self.assertIn('_projectmanager_self_audit_check(root)', validation)


if __name__ == '__main__':
    unittest.main(verbosity=2)
