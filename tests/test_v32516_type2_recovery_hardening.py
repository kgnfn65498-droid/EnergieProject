from __future__ import annotations

import json
import sys
import threading
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
for path in (str(TOOLS), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import clearup_type2_service as service
import project_clearup_move_executor as executor


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _setup(root: Path, *, clearup_id: str = 'ClearUp_099'):
    (root / 'App').mkdir(parents=True, exist_ok=True)
    (root / 'App/VERSIE.txt').write_text('32.5.16\n', encoding='utf-8')
    contract = root / 'App/contract.txt'
    contract.write_text('Data/03_Systeem/Projectmanager/Runtime/new\n', encoding='utf-8')
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed'):
        (root / rel).mkdir(parents=True, exist_ok=True)
    _write_json(root / 'Inbox/release_controller/current.json', {'status': 'COMPLETE', 'phase': 'COMPLETE'})

    source_rel = 'Inbox/runtime_old'
    dest_rel = 'Data/03_Systeem/Projectmanager/Runtime/new'
    source = root / source_rel
    source.mkdir(parents=True, exist_ok=True)
    (source / 'state.bin').write_bytes(b'v1-cutover-candidate')

    plan = {
        'schema': 'energie_clearup_type2_plan_v1',
        'classification': 'TYPE2',
        'clearup_id': clearup_id,
        'status': 'READY',
        'minimum_release': '32.5.7',
        'items': [{
            'source': source_rel,
            'destination': dest_rel,
            'path_key': '',
            'reason': 'recovery hardening test',
            'contract_checks': [{
                'path': 'App/contract.txt',
                'must_contain': ['Data/03_Systeem/Projectmanager/Runtime/new'],
                'must_not_contain': ['Inbox/runtime_old'],
            }],
        }],
    }
    _write_json(root / service.PLAN_ROOT_REL / f'{clearup_id}.json', plan)
    return service._load_plan(root, clearup_id), source, root / dest_rel


def _request(root: Path, plan: dict, operation: str, *, approval: bool = False, request_id: str = 'a' * 32) -> dict:
    return {
        'schema': 'energie_clearup_type2_request_v1',
        'request_id': request_id,
        'operation': operation,
        'clearup_id': plan['clearup_id'],
        'release_version': '32.5.16',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'expires_at': (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        'plan_sha256': plan['plan_sha256'],
        'explicit_user_approval': approval,
        'mailbox_snapshot_before': service._snapshot_release_dirs(root),
    }


def _start_watcher(root: Path, monkeypatch):
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 5.0)
    request_path = root / service.WATCHER_REQUEST_REL

    def watcher():
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and not request_path.is_file():
            time.sleep(0.01)
        assert request_path.is_file(), 'service never emitted watcher request'
        request = json.loads(request_path.read_text(encoding='utf-8'))
        result_path = root / request['result_path']
        try:
            request_id, result = executor.execute_type2(root, request)
            payload = {
                'schema': service.TYPE2_RESULT_SCHEMA,
                'request_id': request_id,
                'status': 'completed',
                'result': result,
            }
        except Exception as exc:  # pragma: no cover - surfaced by service assertion
            payload = {
                'schema': service.TYPE2_RESULT_SCHEMA,
                'request_id': request.get('request_id'),
                'status': 'rejected',
                'error': f'{type(exc).__name__}: {exc}',
            }
        _write_json(result_path, payload)

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    return thread


def test_prepared_refresh_repairs_corrupt_recovery_and_uses_current_source(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    plan, source, _dest = _setup(root, clearup_id='ClearUp_099')
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)

    executor.execute_type2(root, _request(root, plan, 'type2_prepare'))
    # PREPARED source is still authoritative and may change before migration.
    (source / 'state.bin').write_bytes(b'v2-current-before-migrate')

    # Recreate the live 012 class: ZIP payload no longer matches its own manifest.
    stage = root / service.STAGING_ROOT_REL / plan['clearup_id']
    staged_file = stage / 'original' / 'Inbox/runtime_old/state.bin'
    staged_file.write_bytes(b'BROKEN')
    export = root / service.EXPORT_ROOT_REL / f"{plan['clearup_id']}_Type2_recovery.zip"
    with zipfile.ZipFile(export, 'w', zipfile.ZIP_DEFLATED) as z:
        for q in sorted(stage.rglob('*')):
            arc = q.relative_to(stage).as_posix()
            if q.is_dir():
                z.writestr(arc.rstrip('/') + '/', b'')
            else:
                z.write(q, arc)
    with pytest.raises(RuntimeError, match='payload size mismatch|payload hash mismatch'):
        service.export_info(root, clearup_id=plan['clearup_id'], source='mcp_remote')

    thread = _start_watcher(root, monkeypatch)
    result = service.refresh_recovery_type2(root, clearup_id=plan['clearup_id'], source='mcp_remote')
    thread.join(timeout=2)

    assert result['status'] == 'GREEN'
    assert result['prepared_recovery_refresh'] is True
    assert result['post_migrate_recovery_refresh'] is False
    info = service.export_info(root, clearup_id=plan['clearup_id'], source='mcp_remote')
    assert info['status'] == 'GREEN'
    with zipfile.ZipFile(export) as z:
        assert z.read('original/Inbox/runtime_old/state.bin') == b'v2-current-before-migrate'
    state = json.loads((root / service.STATE_ROOT_REL / f"{plan['clearup_id']}.json").read_text())
    assert state['phase'] == 'PREPARED'
    assert state['recovery_refresh']['mode'] == 'prepared_resnapshot'
    assert state['deletion_performed'] is False


def test_migrate_freezes_exact_cutover_before_activation_and_survives_later_drift(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    plan, source, dest = _setup(root, clearup_id='ClearUp_098')
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)

    executor.execute_type2(root, _request(root, plan, 'type2_prepare'))
    # Source changes between prepare and migrate: cutover must preserve v2, not v1.
    (source / 'state.bin').write_bytes(b'v2-exact-cutover')
    _, migrated = executor.execute_type2(root, _request(root, plan, 'type2_migrate', approval=True, request_id='b' * 32))
    assert migrated['cutover_recovery_refreshed'] is True
    assert dest.joinpath('state.bin').read_bytes() == b'v2-exact-cutover'

    export = root / service.EXPORT_ROOT_REL / f"{plan['clearup_id']}_Type2_recovery.zip"
    with zipfile.ZipFile(export) as z:
        assert z.read('original/Inbox/runtime_old/state.bin') == b'v2-exact-cutover'
        manifest = json.loads(z.read('TYPE2_MANIFEST.json'))
    assert manifest['reconstructed_from_cutover_evidence'] is True

    state_path = root / service.STATE_ROOT_REL / f"{plan['clearup_id']}.json"
    state = json.loads(state_path.read_text())
    assert state['recovery_refresh']['mode'] == 'cutover_freeze_before_activation'

    # Both live trees can drift later; the immutable cutover ZIP remains sufficient.
    (source / 'state.bin').write_bytes(b'old-source-drift')
    (dest / 'state.bin').write_bytes(b'active-destination-drift')
    _write_json(root / service.VALIDATION_ROOT_REL / f"{plan['clearup_id']}.json", {
        'schema': 'energie_clearup_type2_validation_v2',
        'status': 'GREEN',
        'clearup_id': plan['clearup_id'],
        'plan_sha256': plan['plan_sha256'],
        'failures': [],
        'checks': [],
    })
    _, refreshed = executor.execute_type2(root, _request(root, plan, 'type2_refresh_recovery', request_id='c' * 32))
    assert refreshed['status'] == 'GREEN'
    assert refreshed['post_migrate_recovery_refresh'] is True
    assert refreshed['reconstruction_sources']['existing_recovery_zip'] >= 1
    with zipfile.ZipFile(export) as z:
        assert z.read('original/Inbox/runtime_old/state.bin') == b'v2-exact-cutover'


def test_migrate_recovery_freeze_failure_rolls_back_without_partial_activation(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    plan, _source, dest = _setup(root, clearup_id='ClearUp_097')
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)

    executor.execute_type2(root, _request(root, plan, 'type2_prepare'))
    export = root / service.EXPORT_ROOT_REL / f"{plan['clearup_id']}_Type2_recovery.zip"
    old_export = export.read_bytes()
    state_path = root / service.STATE_ROOT_REL / f"{plan['clearup_id']}.json"
    old_state = json.loads(state_path.read_text())

    def fail_freeze(*_args, **_kwargs):
        raise RuntimeError('simulated cutover freeze failure')

    monkeypatch.setattr(executor, '_build_type2_recovery_from_cutover', fail_freeze)
    with pytest.raises(RuntimeError, match='simulated cutover freeze failure'):
        executor.execute_type2(root, _request(root, plan, 'type2_migrate', approval=True, request_id='d' * 32))

    assert not dest.exists()
    assert export.read_bytes() == old_export
    assert json.loads(state_path.read_text()) == old_state
    assert (root / service.STAGING_ROOT_REL / plan['clearup_id']).is_dir()
    assert not any((root / executor.TYPE2_ACTIVATION_ROOT).glob('*.json')) if (root / executor.TYPE2_ACTIVATION_ROOT).exists() else True


def test_external_recovery_gate_blocks_32516_finalize_until_explicit_confirmation(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    plan, source, dest = _setup(root, clearup_id='ClearUp_096')
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    monkeypatch.setattr(service, 'TYPE2_REQUIRED_IDS', ('ClearUp_096',))

    executor.execute_type2(root, _request(root, plan, 'type2_prepare', request_id='1' * 32))
    executor.execute_type2(root, _request(root, plan, 'type2_migrate', approval=True, request_id='2' * 32))
    rows = executor._tree_rows(source, root)
    _write_json(root / service.VALIDATION_ROOT_REL / 'ClearUp_096.json', {
        'schema': 'energie_clearup_type2_validation_v2',
        'status': 'GREEN',
        'clearup_id': 'ClearUp_096',
        'plan_sha256': plan['plan_sha256'],
        'failures': [],
        'checks': [{
            'source': 'Inbox/runtime_old',
            'destination': 'Data/03_Systeem/Projectmanager/Runtime/new',
            'source_rows_sha256': executor._rows_fingerprint(rows),
        }],
        'evidence': ['Data/03_Systeem/Projectmanager/Runtime/new'],
    })

    with pytest.raises(RuntimeError, match='external recovery gate missing|explicitly confirmed'):
        executor.execute_type2(root, _request(root, plan, 'type2_finalize', approval=True, request_id='3' * 32))

    thread = _start_watcher(root, monkeypatch)
    confirmation = service.confirm_external_recovery_type2(root, explicit_user_text='ontvangen', source='mcp_remote')
    thread.join(timeout=2)
    assert confirmation['status'] == 'GREEN'
    assert confirmation['confirmed'] is True
    assert confirmation['delete_allowed'] is True

    _, finalized = executor.execute_type2(root, _request(root, plan, 'type2_finalize', approval=True, request_id='4' * 32))
    assert finalized['phase'] == 'COMPLETE'
    assert not source.exists()
    assert dest.exists()


def test_recovery_change_invalidates_prior_external_confirmation(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    plan, source, _dest = _setup(root, clearup_id='ClearUp_095')
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    monkeypatch.setattr(service, 'TYPE2_REQUIRED_IDS', ('ClearUp_095',))

    executor.execute_type2(root, _request(root, plan, 'type2_prepare', request_id='5' * 32))
    thread = _start_watcher(root, monkeypatch)
    confirmed = service.confirm_external_recovery_type2(root, explicit_user_text='bevestigd', source='mcp_remote')
    thread.join(timeout=2)
    assert confirmed['delete_allowed'] is True

    (source / 'state.bin').write_bytes(b'changed-after-confirmation')
    thread = _start_watcher(root, monkeypatch)
    refreshed = service.refresh_recovery_type2(root, clearup_id='ClearUp_095', source='mcp_remote')
    thread.join(timeout=2)
    assert refreshed['status'] == 'GREEN'

    gate = json.loads((root / service.EXTERNAL_GATE_REL).read_text(encoding='utf-8'))
    assert gate['status'] == 'BLOCK_DELETE_UNTIL_EXTERNAL_COPY_CONFIRMED'
    assert gate['delete_allowed'] is False
    assert gate['invalidated_by_clearup_id'] == 'ClearUp_095'
    with pytest.raises(RuntimeError, match='explicitly confirmed'):
        service._assert_external_recovery_confirmed(root)
