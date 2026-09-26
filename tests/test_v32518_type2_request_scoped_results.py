from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for path in (str(APP), str(PM), str(TOOLS)):
    if path not in sys.path:
        sys.path.insert(0, path)

import clearup_type2_service as service
import sideband_bridge


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _base(root: Path) -> None:
    _write(root / 'App/VERSIE.txt', '32.5.19\n')
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed'):
        (root / rel).mkdir(parents=True, exist_ok=True)
    (root / service.WATCHER_RESULT_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / service.WATCHER_RESULT_ROOT_REL).mkdir(parents=True, exist_ok=True)


def _completed(request_id: str, clearup_id: str = 'ClearUp_099') -> dict:
    return {
        'schema': service.TYPE2_RESULT_SCHEMA,
        'request_id': request_id,
        'status': 'completed',
        'result': {'status': 'GREEN', 'clearup_id': clearup_id},
    }


def test_request_scoped_mailbox_ignores_stale_canonical_result(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _base(root)
    plan = {'plan_sha256': 'a' * 64}
    canonical = root / service.WATCHER_RESULT_REL
    _write(canonical, json.dumps(_completed('stale-request', 'ClearUp_001')))
    stale_inode = canonical.stat().st_ino
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 2.0)

    observed = {}

    def watcher():
        request_path = root / service.WATCHER_REQUEST_REL
        deadline = time.monotonic() + 1.0
        while not request_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.005)
        request = json.loads(request_path.read_text(encoding='utf-8'))
        result_rel = request['result_path']
        observed['result_rel'] = result_rel
        assert result_rel == f"{service.WATCHER_RESULT_ROOT_REL.as_posix()}/{request['request_id']}.json"
        dynamic = root / result_rel
        assert not dynamic.exists()
        _write(dynamic, json.dumps(_completed(request['request_id'])))

    t = threading.Thread(target=watcher, daemon=True)
    t.start()
    got = service._watcher_call(root, operation='type2_refresh_recovery', clearup_id='ClearUp_099', plan=plan)
    t.join(timeout=1)

    assert got == {'status': 'GREEN', 'clearup_id': 'ClearUp_099'}
    assert observed['result_rel'].startswith(service.WATCHER_RESULT_ROOT_REL.as_posix() + '/')
    assert not (root / observed['result_rel']).exists(), 'successful scoped result must be cleaned after canonical audit copy'
    canonical_payload = json.loads(canonical.read_text(encoding='utf-8'))
    # PM completion is request-scoped and must not mutate the privileged canonical audit.
    assert canonical_payload['request_id'] == 'stale-request'
    assert canonical.stat().st_ino == stale_inode
    assert not (root / service.WATCHER_REQUEST_REL).exists()


def test_two_sequential_requests_use_distinct_result_paths(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _base(root)
    plan = {'plan_sha256': 'b' * 64}
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 2.0)
    seen = []

    def serve_one(expected_id: str):
        request_path = root / service.WATCHER_REQUEST_REL
        deadline = time.monotonic() + 1.0
        while not request_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.005)
        request = json.loads(request_path.read_text(encoding='utf-8'))
        dynamic = root / request['result_path']
        seen.append(request['result_path'])
        _write(dynamic, json.dumps(_completed(request['request_id'], expected_id)))

    for clearup_id in ('ClearUp_098', 'ClearUp_099'):
        t = threading.Thread(target=serve_one, args=(clearup_id,), daemon=True)
        t.start()
        got = service._watcher_call(root, operation='type2_refresh_recovery', clearup_id=clearup_id, plan=plan)
        t.join(timeout=1)
        assert got['clearup_id'] == clearup_id
        # Deliberately make the durable canonical result stale between calls.
        _write(root / service.WATCHER_RESULT_REL, json.dumps(_completed('stale-again', 'ClearUp_001')))

    assert len(seen) == 2
    assert seen[0] != seen[1]
    assert all(p.startswith(service.WATCHER_RESULT_ROOT_REL.as_posix() + '/') for p in seen)
    assert not any((root / p).exists() for p in seen)


def test_sideband_accepts_only_request_scoped_path_bound_to_request_id(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _base(root)
    request_id = '1' * 32
    result_rel = f'{service.WATCHER_RESULT_ROOT_REL.as_posix()}/{request_id}.json'
    request = {
        'schema': service.TYPE2_REQUEST_SCHEMA,
        'request_id': request_id,
        'result_path': result_rel,
    }
    _write(root / service.WATCHER_REQUEST_REL, json.dumps(request))
    observed = {}

    def fake_process(project_root: Path, request_path: Path, result_path: Path):
        observed['result_path'] = result_path.relative_to(project_root).as_posix()
        payload = _completed(request_id)
        _write(result_path, json.dumps(payload))
        return 0, payload

    monkeypatch.setattr(sideband_bridge.project_clearup_move_executor, 'process', fake_process)
    result = sideband_bridge.process_once(root)
    assert result['request_id'] == request_id
    assert observed['result_path'] == result_rel
    assert (root / result_rel).is_file()

    # Same root with a result name belonging to another request must fail closed.
    bad_id = '2' * 32
    _write(root / service.WATCHER_REQUEST_REL, json.dumps({
        'schema': service.TYPE2_REQUEST_SCHEMA,
        'request_id': bad_id,
        'result_path': result_rel,
    }))
    try:
        sideband_bridge.process_once(root)
    except RuntimeError as exc:
        assert 'outside allowlist' in str(exc)
    else:  # pragma: no cover
        raise AssertionError('mismatched request/result identity must be rejected')


def test_request_scoped_mailbox_refuses_symlink_collision(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _base(root)
    monkeypatch.setattr(service.secrets, 'token_hex', lambda n: 'a' * 32)
    target = root / 'outside.json'
    _write(target, '{}')
    scoped = root / service.WATCHER_RESULT_ROOT_REL / ('a' * 32 + '.json')
    scoped.symlink_to(target)
    try:
        service._watcher_call(
            root,
            operation='type2_refresh_recovery',
            clearup_id='ClearUp_099',
            plan={'plan_sha256': 'c' * 64},
        )
    except RuntimeError as exc:
        assert 'symlink refused' in str(exc)
    else:  # pragma: no cover
        raise AssertionError('request-scoped result symlink must be rejected')


def test_timeout_retains_scoped_result_only_for_forensics_if_it_arrives_wrong_identity(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _base(root)
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 0.05)
    monkeypatch.setattr(service.secrets, 'token_hex', lambda n: 'b' * 32)
    scoped = root / service.WATCHER_RESULT_ROOT_REL / ('b' * 32 + '.json')

    def watcher():
        request_path = root / service.WATCHER_REQUEST_REL
        deadline = time.monotonic() + 0.2
        while not request_path.is_file() and time.monotonic() < deadline:
            time.sleep(0.002)
        _write(scoped, json.dumps(_completed('c' * 32)))

    t = threading.Thread(target=watcher, daemon=True)
    t.start()
    try:
        service._watcher_call(
            root,
            operation='type2_refresh_recovery',
            clearup_id='ClearUp_099',
            plan={'plan_sha256': 'd' * 64},
        )
    except RuntimeError as exc:
        assert 'timeout' in str(exc)
    else:  # pragma: no cover
        raise AssertionError('wrong request identity must never satisfy waiter')
    t.join(timeout=1)
    assert scoped.is_file(), 'failed/timed-out scoped result is retained as forensic evidence'
    assert not (root / service.WATCHER_REQUEST_REL).exists()
