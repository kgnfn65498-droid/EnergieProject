from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import clearup_type2_service as service


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _base(root: Path) -> None:
    _write(root / 'App/VERSIE.txt', '32.5.17\n')
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed'):
        (root / rel).mkdir(parents=True, exist_ok=True)
    (root / service.WATCHER_RESULT_REL).parent.mkdir(parents=True, exist_ok=True)


def test_watcher_call_ignores_stale_canonical_result_via_request_scoped_mailbox(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _base(root)
    plan = {'plan_sha256': 'a' * 64}
    canonical = root / service.WATCHER_RESULT_REL
    _write(canonical, json.dumps({
        'schema': service.TYPE2_RESULT_SCHEMA,
        'request_id': 'old-request',
        'status': 'completed',
        'result': {'status': 'GREEN', 'clearup_id': 'ClearUp_001'},
    }))
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 2.0)

    observed = {}

    def watcher():
        request_path = root / service.WATCHER_REQUEST_REL
        deadline = time.monotonic() + 1.0
        while not request_path.exists() and time.monotonic() < deadline:
            time.sleep(0.005)
        assert request_path.is_file()
        request = json.loads(request_path.read_text(encoding='utf-8'))
        result_path = root / request['result_path']
        observed['result_path'] = request['result_path']
        assert not result_path.exists()
        _write(result_path, json.dumps({
            'schema': service.TYPE2_RESULT_SCHEMA,
            'request_id': request['request_id'],
            'status': 'completed',
            'result': {'status': 'GREEN', 'clearup_id': 'ClearUp_099'},
        }))

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    got = service._watcher_call(root, operation='type2_refresh_recovery', clearup_id='ClearUp_099', plan=plan)
    thread.join(timeout=1)

    assert got == {'status': 'GREEN', 'clearup_id': 'ClearUp_099'}
    assert observed['result_path'].startswith(service.WATCHER_RESULT_ROOT_REL.as_posix() + '/')
    assert not (root / observed['result_path']).exists()
    canonical_payload = json.loads(canonical.read_text(encoding='utf-8'))
    assert canonical_payload['request_id'] != 'old-request'
    assert canonical_payload['result']['clearup_id'] == 'ClearUp_099'
    assert not (root / service.WATCHER_REQUEST_REL).exists()

def test_watcher_call_refuses_symlink_result_mailbox(tmp_path):
    root = tmp_path / 'project'
    _base(root)
    target = root / 'outside.json'
    _write(target, '{}')
    result_path = root / service.WATCHER_RESULT_REL
    result_path.unlink(missing_ok=True)
    result_path.symlink_to(target)
    try:
        service._watcher_call(
            root,
            operation='type2_refresh_recovery',
            clearup_id='ClearUp_099',
            plan={'plan_sha256': 'a' * 64},
        )
    except RuntimeError as exc:
        assert 'symlink refused' in str(exc)
    else:  # pragma: no cover
        raise AssertionError('symlink result mailbox must be rejected')
