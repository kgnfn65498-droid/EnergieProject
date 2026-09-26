from __future__ import annotations

import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(TOOLS), str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import clearup_type2_service as service
import project_clearup_move_executor as executor
import sideband_bridge

IDS = [f'ClearUp_{i:03d}' for i in range(2, 13)]
FILE_SOURCES = {
    'Inbox/github_publisher_history.jsonl',
    'Inbox/latest_release_status.txt',
    'Inbox/energie-control-plane.containerstation-v3.yml',
    'Inbox/.watcher.heartbeat',
    'Inbox/watcher_container_contract.json',
    'Inbox/atomic_app_swap_state.json',
    'Inbox/github_publication_state.json',
    'Inbox/github_publisher_state.json',
    'Inbox/.nas-container-cr.operation.lock',
    'Inbox/.release-controller.lock',
    'Inbox/.release-transition.operation.lock',
    'Inbox/watcher_heartbeat.v2',
}


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')


def _watch(root: Path, monkeypatch):
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 5.0)
    request_path = root / service.WATCHER_REQUEST_REL

    def run():
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and not request_path.is_file():
            time.sleep(0.005)
        assert request_path.is_file()
        # Exercise the actual release-controller sideband bridge. It validates
        # the request-scoped result path and invokes the privileged Type2 executor.
        payload = sideband_bridge.process_once(root)
        assert isinstance(payload, dict)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread


def _call(root: Path, monkeypatch, fn, /, **kwargs):
    thread = _watch(root, monkeypatch)
    result = fn(root, source='mcp_remote', **kwargs)
    thread.join(timeout=3)
    assert not thread.is_alive()
    return result


def _seed_project(root: Path) -> None:
    (root / 'App/tools/clearup_type2_plans').mkdir(parents=True, exist_ok=True)
    (root / 'App/VERSIE.txt').write_text('32.5.16\n', encoding='utf-8')
    for cid in IDS:
        shutil.copy2(ROOT / 'tools/clearup_type2_plans' / f'{cid}.json', root / 'App/tools/clearup_type2_plans' / f'{cid}.json')
    contract = {'release': '32.5.16', **{cid: 'GREEN' for cid in IDS}}
    (root / 'App/tools/clearup_type2_path_contract.json').write_text(json.dumps(contract, indent=2) + '\n', encoding='utf-8')
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed'):
        (root / rel).mkdir(parents=True, exist_ok=True)

    plans = [json.loads((ROOT / 'tools/clearup_type2_plans' / f'{cid}.json').read_text()) for cid in IDS]
    for plan in plans:
        for item in plan['items']:
            source = root / item['source']
            if item['source'] in FILE_SOURCES:
                source.parent.mkdir(parents=True, exist_ok=True)
                if source.name.endswith('.lock'):
                    source.write_bytes(b'')
                else:
                    source.write_text(f"seed:{item['source']}\n", encoding='utf-8')
            else:
                source.mkdir(parents=True, exist_ok=True)
                (source / 'seed.txt').write_text(f"seed:{item['source']}\n", encoding='utf-8')

    # The Type2 service itself requires this state to remain COMPLETE throughout.
    _json(root / 'Inbox/release_controller/current.json', {'status': 'COMPLETE', 'phase': 'COMPLETE'})
    _json(root / 'Inbox/release_controller/runtime.json', {'status': 'IDLE'})
    _json(root / 'Inbox/projectmanager_v2/RuntimeV2/heartbeat/manager.json', {'state': 'green'})
    _json(root / 'Inbox/native_mcp_runtime/runtime_guard.json', {'status': 'GREEN'})
    _json(root / 'Inbox/control_plane/runtime.json', {'status': 'GREEN'})


def _touch_runtime_proofs(root: Path, clearup_id: str) -> None:
    plan = service._load_plan(root, clearup_id)
    for item in plan['items']:
        dest = root / item['destination']
        if not dest.is_dir():
            continue
        for rel in item.get('runtime_proof_paths') or []:
            proof = dest / rel
            proof.parent.mkdir(parents=True, exist_ok=True)
            if proof.suffix == '.json':
                _json(proof, {'written_after_activation': time.time()})
            else:
                proof.write_text(str(time.time()), encoding='utf-8')


def test_all_type2_batches_prepare_migrate_validate_confirm_finalize_end_to_end(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _seed_project(root)
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS', '0.05')
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_PROOF_TIMEOUT_SECONDS', '1')
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)

    # Prepare every recovery export while no destructive action is possible.
    for cid in IDS:
        result = _call(root, monkeypatch, service.prepare_type2, clearup_id=cid)
        assert result['status'] == 'GREEN' and result['deletion_performed'] is False
        assert service.export_info(root, clearup_id=cid, source='mcp_remote')['status'] == 'GREEN'

    # Migrate and validate all batches while every old source remains preserved.
    for cid in IDS:
        result = _call(root, monkeypatch, service.migrate_type2, clearup_id=cid, explicit_user_text='akkoord')
        assert result['phase'] == 'MIGRATED_PENDING_VALIDATION'
        assert result['source_preserved'] is True and result['deletion_performed'] is False
        _touch_runtime_proofs(root, cid)
        proof = _call(root, monkeypatch, service.validate_type2, clearup_id=cid)
        assert proof['status'] == 'GREEN', proof
        assert not proof['failures']
        assert service.export_info(root, clearup_id=cid, source='mcp_remote')['status'] == 'GREEN'

    assert all((root / service.STATE_ROOT_REL / f'{cid}.json').is_file() for cid in IDS)
    assert all((root / service.EXPORT_ROOT_REL / f'{cid}_Type2_recovery.zip').is_file() for cid in IDS)
    assert all((root / service._load_plan(root, cid)['items'][0]['source']).exists() for cid in IDS)

    # Deletion remains fail-closed until the complete externally delivered set is confirmed.
    try:
        service.finalize_type2(root, clearup_id='ClearUp_002', explicit_user_text='akkoord', source='mcp_remote')
    except RuntimeError as exc:
        assert 'external recovery' in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError('finalize unexpectedly bypassed external recovery gate')

    confirmed = _call(root, monkeypatch, service.confirm_external_recovery_type2, explicit_user_text='ontvangen')
    assert confirmed['status'] == 'GREEN'
    assert confirmed['verified_count'] == len(IDS)
    assert confirmed['delete_allowed'] is True

    # Only now may old sources be finalized. Destinations remain authoritative.
    for cid in IDS:
        result = _call(root, monkeypatch, service.finalize_type2, clearup_id=cid, explicit_user_text='akkoord')
        assert result['phase'] == 'COMPLETE' and result['deletion_performed'] is True
        plan = service._load_plan(root, cid)
        for item in plan['items']:
            assert not (root / item['source']).exists()
            assert (root / item['destination']).exists()

    gate = json.loads((root / service.EXTERNAL_GATE_REL).read_text(encoding='utf-8'))
    assert gate['status'] == 'EXTERNAL_COPY_CONFIRMED'
    assert gate['delete_allowed'] is True
    assert len(gate['confirmed_exports']) == len(IDS)
