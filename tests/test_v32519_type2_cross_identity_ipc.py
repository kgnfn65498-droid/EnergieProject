from __future__ import annotations

import json
import os
import stat
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for p in (str(APP), str(PM), str(TOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import clearup_type2_service as service
import sideband_bridge


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _base_without_results(root: Path) -> None:
    _write(root / 'App/VERSIE.txt', '32.5.19\n')
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed'):
        (root / rel).mkdir(parents=True, exist_ok=True)
    # Live 32.5.18 situation: ClearUp Runtime exists, request-scoped child does not,
    # and the embedded PM identity cannot create that privileged child.
    (root / service.WATCHER_RESULT_REL).parent.mkdir(parents=True, exist_ok=True)


def _completed(request_id: str) -> dict:
    return {
        'schema': service.TYPE2_RESULT_SCHEMA,
        'request_id': request_id,
        'status': 'completed',
        'result': {'status': 'GREEN', 'clearup_id': 'ClearUp_002', 'deletion_performed': False},
        'delete_performed': False,
    }


def test_live_32518_permission_failure_is_removed_by_privileged_bridge_owner(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _base_without_results(root)
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 2.0)

    original_mkdir = Path.mkdir
    dynamic_root = root / service.WATCHER_RESULT_ROOT_REL

    def guarded_mkdir(self, *args, **kwargs):
        if self == dynamic_root and threading.current_thread() is threading.main_thread():
            raise PermissionError('simulated live 32.5.18 PM mkdir denial')
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', guarded_mkdir)

    original_atomic = service._atomic_json
    canonical = root / service.WATCHER_RESULT_REL

    def pm_atomic_guard(path, payload):
        if path == canonical:
            raise AssertionError('embedded PM must not write privileged canonical Type2 audit')
        return original_atomic(path, payload)

    monkeypatch.setattr(service, '_atomic_json', pm_atomic_guard)

    def fake_process(project_root: Path, request_path: Path, result_path: Path):
        assert result_path.parent == dynamic_root
        assert dynamic_root.is_dir(), 'privileged sideband must create shared IPC root before executor'
        assert stat.S_IMODE(dynamic_root.stat().st_mode) == 0o777
        request = json.loads(request_path.read_text(encoding='utf-8'))
        payload = _completed(request['request_id'])
        result_path.write_text(json.dumps(payload), encoding='utf-8')
        return 0, payload

    monkeypatch.setattr(sideband_bridge.project_clearup_move_executor, 'process', fake_process)

    def watcher():
        request = root / service.WATCHER_REQUEST_REL
        deadline = time.monotonic() + 1.0
        while not request.is_file() and time.monotonic() < deadline:
            time.sleep(0.005)
        sideband_bridge.process_once(root)

    t = threading.Thread(target=watcher, daemon=True)
    t.start()
    result = service._watcher_call(
        root,
        operation='type2_refresh_recovery',
        clearup_id='ClearUp_002',
        plan={'plan_sha256': 'a' * 64},
    )
    t.join(timeout=1)

    assert result['status'] == 'GREEN'
    assert canonical.is_file(), 'privileged sideband must publish durable canonical audit copy'
    canonical_payload = json.loads(canonical.read_text(encoding='utf-8'))
    assert canonical_payload['result']['clearup_id'] == 'ClearUp_002'
    assert stat.S_IMODE(dynamic_root.stat().st_mode) == 0o777


def test_sideband_rejects_symlinked_dynamic_result_root(tmp_path):
    root = tmp_path / 'project'
    _base_without_results(root)
    outside = root / 'outside'
    outside.mkdir()
    dynamic_root = root / service.WATCHER_RESULT_ROOT_REL
    dynamic_root.symlink_to(outside, target_is_directory=True)
    request_id = '1' * 32
    _write(root / service.WATCHER_REQUEST_REL, json.dumps({
        'schema': service.TYPE2_REQUEST_SCHEMA,
        'request_id': request_id,
        'result_path': f'{service.WATCHER_RESULT_ROOT_REL.as_posix()}/{request_id}.json',
    }))
    try:
        sideband_bridge.process_once(root)
    except RuntimeError as exc:
        assert 'result root symlink refused' in str(exc)
    else:
        raise AssertionError('symlinked shared result root must fail closed')


def test_current_release_and_pm_identity():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.5.20'
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == '2.0.0-rc53'
