import importlib
import json
import os
import sys
import tempfile
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'slimmemeterportal_import' / 'rootfs' / 'app'
PM = APP / 'projectmanager_v2'
for p in (str(APP), str(PM)):
    if p not in sys.path:
        sys.path.insert(0, p)

import operating_mode_runtime as mode_runtime
from self_audit import SelfAuditor


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _project(status_updated_at='2026-09-09T10:46:49+00:00', audit_status_updated_at=None):
    root = Path(tempfile.mkdtemp())
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.21\n', encoding='utf-8')
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    status = {
        'updated_at': status_updated_at,
        'release': {'version': '32.4.21'},
        'health': {
            'status': 'RED',
            'checks': [
                {
                    'name': 'release_validation_hold', 'status': 'ORANGE',
                    'reason': 'missing_active_or_unvalidated',
                    'details': {'active': True, 'validation_status': 'blocked'},
                },
                {
                    'name': 'release_atomic_state', 'status': 'RED',
                    'reason': 'live_acceptance_blocks_release_ingress',
                    'details': {},
                },
            ],
        },
    }
    _write_json(runtime / 'status/current.json', status)
    audit = {
        'status': 'GREEN', 'missing': [], 'invalid': [], 'warnings': [],
        'required_files': ['status/current.json', 'heartbeat/manager.json', 'handover/current.json', 'audit/events.jsonl'],
    }
    if audit_status_updated_at is not None:
        audit['status_updated_at'] = audit_status_updated_at
    _write_json(runtime / 'self_audit/current.json', audit)
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.20', 'to_version': '32.4.21'
    })
    return root, runtime


def test_matching_provenance_allows_audit_even_when_audit_mtime_is_older_than_status():
    root, runtime = _project(audit_status_updated_at='2026-09-09T10:46:49+00:00')
    audit_path = runtime / 'self_audit/current.json'
    status_path = runtime / 'status/current.json'
    old = time.time() - 10
    os.utime(audit_path, (old, old))
    os.utime(status_path, None)
    result = mode_runtime._projectmanager_self_audit_check(root)
    assert result['ok'] is True, result


def test_mismatched_provenance_blocks_even_when_audit_mtime_is_newer():
    root, runtime = _project(audit_status_updated_at='2026-09-09T10:45:00+00:00')
    audit_path = runtime / 'self_audit/current.json'
    status_path = runtime / 'status/current.json'
    old = time.time() - 10
    os.utime(status_path, (old, old))
    os.utime(audit_path, None)
    result = mode_runtime._projectmanager_self_audit_check(root)
    assert result['ok'] is False
    assert 'provenance' in result['detail']


def test_self_auditor_records_status_updated_at_it_actually_audited():
    root = Path(tempfile.mkdtemp())
    runtime = root / 'runtime'
    runtime.mkdir(parents=True)
    updated_at = '2026-09-09T10:46:49+00:00'
    _write_json(runtime / 'status/current.json', {
        'updated_at': updated_at,
        'mode': 'DEVELOPMENT',
        'health': {'status': 'GREEN'},
        'release': {'version': '32.4.21'},
    })
    _write_json(runtime / 'heartbeat/manager.json', {
        'heartbeat_at': updated_at, 'mode': 'DEVELOPMENT', 'health': 'GREEN'
    })
    _write_json(runtime / 'handover/current.json', {
        'mode': 'DEVELOPMENT', 'release': {'version': '32.4.21'}
    })
    (runtime / 'audit').mkdir(parents=True, exist_ok=True)
    (runtime / 'audit/events.jsonl').write_text(json.dumps({'event_type': 'manager.run'}) + '\n', encoding='utf-8')
    result = SelfAuditor(runtime).run()
    assert result['status_updated_at'] == updated_at
