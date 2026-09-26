from __future__ import annotations

import hashlib
import json
import sys
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


def _setup(tmp_path: Path):
    root = tmp_path / 'project'
    source_rel = 'Inbox/projectmanager_v2/RuntimeV2'
    dest_rel = 'Data/03_Systeem/Projectmanager/RuntimeV2'
    source = root / source_rel
    dest = root / dest_rel
    source.mkdir(parents=True)
    dest.mkdir(parents=True)
    (source / 'stable.json').write_text('{"cutover":true}\n', encoding='utf-8')
    probe_rel = '.release_transition_permission_probe_20260914T1723Z/current.json'
    (source / Path(probe_rel).parent).mkdir(parents=True)
    (source / probe_rel).write_bytes(b'')
    # Destination starts as exact cutover copy, as migration would create it.
    (dest / 'stable.json').write_text('{"cutover":true}\n', encoding='utf-8')
    (dest / Path(probe_rel).parent).mkdir(parents=True)
    (dest / probe_rel).write_bytes(b'')

    (root / 'App').mkdir()
    (root / 'App/VERSIE.txt').write_text('32.5.16\n', encoding='utf-8')
    contract = root / 'App/tools/clearup_type2_path_contract.json'
    contract.parent.mkdir(parents=True)
    contract.write_text('{"ClearUp_002": "GREEN"}\n', encoding='utf-8')
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'):
        (root / rel).mkdir(parents=True, exist_ok=True)
    _write_json(root / 'Inbox/release_controller/current.json', {'status':'COMPLETE','phase':'COMPLETE'})

    plan = {
        'schema':'energie_clearup_type2_plan_v1','classification':'TYPE2','clearup_id':'ClearUp_002',
        'status':'READY','minimum_release':'32.5.7',
        'items':[{
            'source':source_rel,'destination':dest_rel,'path_key':'pm_runtime','reason':'test',
            'contract_checks':[{'path':'App/tools/clearup_type2_path_contract.json','must_contain':['"ClearUp_002": "GREEN"'],'must_not_contain':['"ClearUp_002": "RED"']}],
            'runtime_proof_paths':['heartbeat/manager.json'],
        }],
    }
    _write_json(root / service.PLAN_ROOT_REL / 'ClearUp_002.json', plan)
    loaded = service._load_plan(root, 'ClearUp_002')
    cutover_rows = executor._tree_rows(source, root)
    _write_json(root / service.STATE_ROOT_REL / 'ClearUp_002.json', {
        'status':'GREEN','clearup_id':'ClearUp_002','phase':'MIGRATED_PENDING_VALIDATION',
        'plan_sha256':loaded['plan_sha256'],'source_preserved':True,'deletion_performed':False,
        'cutover_rows':{source_rel:cutover_rows},
    })
    _write_json(root / service.VALIDATION_ROOT_REL / 'ClearUp_002.json', {
        'schema':'energie_clearup_type2_validation_v2','status':'GREEN','clearup_id':'ClearUp_002',
        'plan_sha256':loaded['plan_sha256'],'failures':[],
    })
    _write_json(root / 'Data/03_Systeem/Projectmanager/ClearUp/PathActivation/pm_runtime.json', {
        'schema':'energie_clearup_system_path_contract_v1','key':'pm_runtime','source':source_rel,'destination':dest_rel,
        'active':True,'clearup_id':'ClearUp_002','plan_sha256':loaded['plan_sha256'],
    })

    # Existing recovery ZIP: stable payload is correct; empty probe is corrupt.
    stage = root / service.STAGING_ROOT_REL / 'ClearUp_002'
    staged = stage / 'original' / source_rel
    staged.mkdir(parents=True)
    (staged / 'stable.json').write_text('{"cutover":true}\n', encoding='utf-8')
    (staged / Path(probe_rel).parent).mkdir(parents=True)
    (staged / probe_rel).write_bytes(b'CORRUPT')
    manifest = {
        'schema':'energie_clearup_type2_recovery_v1','classification':'TYPE2','clearup_id':'ClearUp_002',
        'plan_sha256':loaded['plan_sha256'],'created_at':datetime.now(timezone.utc).isoformat(),
        'deletion_performed':False,
        'items':[{'source':source_rel,'destination':dest_rel,'source_rows':cutover_rows,'reason':'test','path_key':'pm_runtime'}],
    }
    _write_json(stage / 'TYPE2_MANIFEST.json', manifest)
    export = root / service.EXPORT_ROOT_REL / 'ClearUp_002_Type2_recovery.zip'
    export.parent.mkdir(parents=True)
    with zipfile.ZipFile(export, 'w', zipfile.ZIP_DEFLATED) as z:
        for q in sorted(stage.rglob('*')):
            arc=q.relative_to(stage).as_posix()
            if q.is_dir(): z.writestr(arc.rstrip('/')+'/', b'')
            else: z.write(q, arc)
    return root, loaded, source, dest, export, probe_rel


def _request(root: Path, plan: dict) -> dict:
    return {
        'schema':'energie_clearup_type2_request_v1','request_id':'b'*32,
        'operation':'type2_refresh_recovery','clearup_id':'ClearUp_002','release_version':'32.5.16',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
        'plan_sha256':plan['plan_sha256'],'explicit_user_approval':False,
        'mailbox_snapshot_before':service._snapshot_release_dirs(root),
    }


def test_refresh_reconstructs_cutover_when_preserved_runtime_drifted(tmp_path, monkeypatch):
    root, plan, source, dest, export, probe_rel = _setup(tmp_path)
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    source_before_files = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    dest_before_files = {p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob('*') if p.is_file()}

    # Live old runtime continues after cutover: both files now drift in source.
    (source / 'stable.json').write_text('{"runtime":"new"}\n', encoding='utf-8')
    (source / probe_rel).write_bytes(b'NEW-PROBE')
    # Also drift the destination copy of the empty probe so the only safe reconstruction is
    # the cryptographically proven empty-file identity.
    (dest / probe_rel).write_bytes(b'DEST-PROBE-DRIFT')
    source_drifted = {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    dest_drifted = {p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob('*') if p.is_file()}

    with pytest.raises(RuntimeError, match='payload size mismatch'):
        service.export_info(root, clearup_id='ClearUp_002', source='mcp_remote')

    _, result = executor.execute_type2(root, _request(root, plan))
    assert result['status'] == 'GREEN'
    assert result['post_migrate_recovery_refresh'] is True
    assert result['deletion_performed'] is False
    assert result['source_preserved'] is True
    assert result['destination_untouched'] is True
    assert result['reconstruction_sources']['existing_recovery_zip'] >= 1
    assert result['reconstruction_sources']['proven_empty_identity'] >= 1
    assert service.export_info(root, clearup_id='ClearUp_002', source='mcp_remote')['status'] == 'GREEN'

    # Refresh must not rewrite either live tree.
    assert {p.relative_to(source).as_posix(): p.read_bytes() for p in source.rglob('*') if p.is_file()} == source_drifted
    assert {p.relative_to(dest).as_posix(): p.read_bytes() for p in dest.rglob('*') if p.is_file()} == dest_drifted
    assert source_before_files != source_drifted


def test_refresh_falls_back_to_quiescent_preserved_source_when_cutover_payload_is_lost(tmp_path, monkeypatch):
    root, plan, source, dest, export, probe_rel = _setup(tmp_path)
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)

    (source / 'stable.json').write_text('{"source":"drift"}\n', encoding='utf-8')
    (dest / 'stable.json').write_text('{"dest":"drift"}\n', encoding='utf-8')
    # Corrupt the archived non-empty payload too, while retaining manifest cutover identity.
    stage = root / service.STAGING_ROOT_REL / 'ClearUp_002'
    (stage / 'original' / 'Inbox/projectmanager_v2/RuntimeV2/stable.json').write_text('{"zip":"drift"}\n', encoding='utf-8')
    with zipfile.ZipFile(export, 'w', zipfile.ZIP_DEFLATED) as z:
        for q in sorted(stage.rglob('*')):
            arc=q.relative_to(stage).as_posix()
            if q.is_dir(): z.writestr(arc.rstrip('/')+'/', b'')
            else: z.write(q, arc)

    _, result = executor.execute_type2(root, _request(root, plan))
    assert result['status'] == 'GREEN'
    assert result['recovery_basis'] == 'quiescent_preserved_source'
    assert result['reconstruction_sources']['quiescent_preserved_source'] >= 1
    with zipfile.ZipFile(export) as z:
        manifest = json.loads(z.read('TYPE2_MANIFEST.json'))
        assert manifest['recovery_basis'] == 'quiescent_preserved_source'
        assert manifest['legacy_cutover_reconstruction_unavailable'] is True
        assert z.read('original/Inbox/projectmanager_v2/RuntimeV2/stable.json') == b'{"source":"drift"}\n'
    assert service.export_info(root, clearup_id='ClearUp_002', source='mcp_remote')['status'] == 'GREEN'


def test_quiescent_preserved_source_fallback_fails_closed_when_old_source_mutates(tmp_path, monkeypatch):
    root, plan, source, dest, export, _probe_rel = _setup(tmp_path)
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    (source / 'stable.json').write_text('{"source":"drift"}\n', encoding='utf-8')
    (dest / 'stable.json').write_text('{"dest":"drift"}\n', encoding='utf-8')
    stage = root / service.STAGING_ROOT_REL / 'ClearUp_002'
    (stage / 'original' / 'Inbox/projectmanager_v2/RuntimeV2/stable.json').write_text('{"zip":"drift"}\n', encoding='utf-8')
    with zipfile.ZipFile(export, 'w', zipfile.ZIP_DEFLATED) as z:
        for q in sorted(stage.rglob('*')):
            arc=q.relative_to(stage).as_posix()
            if q.is_dir(): z.writestr(arc.rstrip('/')+'/', b'')
            else: z.write(q, arc)

    original_tree_rows = executor._tree_rows
    calls = {'n': 0}
    def mutating_rows(path, project_root):
        rows = original_tree_rows(path, project_root)
        if Path(path).resolve() == source.resolve():
            calls['n'] += 1
            if calls['n'] == 2:
                (source / 'late-write.txt').write_text('writer still active\n', encoding='utf-8')
                rows = original_tree_rows(path, project_root)
        return rows
    monkeypatch.setattr(executor, '_tree_rows', mutating_rows)

    with pytest.raises(executor.RequestRejected, match='old source still mutating during recovery fallback'):
        executor.execute_type2(root, _request(root, plan))

def test_service_to_watcher_to_executor_refresh_path_is_green(tmp_path, monkeypatch):
    import threading
    import time

    root, plan, source, dest, export, probe_rel = _setup(tmp_path)
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 5.0)

    # Recreate the live failure shape: old RuntimeV2 continues changing after cutover.
    (source / 'stable.json').write_text('{"runtime":"continued"}\n', encoding='utf-8')
    (source / probe_rel).write_bytes(b'OLD-RUNTIME-CONTINUED')
    (dest / probe_rel).write_bytes(b'DEST-PROBE-DRIFT')

    request_path = root / service.WATCHER_REQUEST_REL
    result_path = root / service.WATCHER_RESULT_REL

    def watcher():
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline and not request_path.is_file():
            time.sleep(0.01)
        assert request_path.is_file(), 'service never emitted watcher request'
        request = json.loads(request_path.read_text(encoding='utf-8'))
        try:
            request_id, result = executor.execute_type2(root, request)
            payload = {
                'schema': service.TYPE2_RESULT_SCHEMA,
                'request_id': request_id,
                'status': 'completed',
                'result': result,
            }
        except Exception as exc:
            payload = {
                'schema': service.TYPE2_RESULT_SCHEMA,
                'request_id': request.get('request_id'),
                'status': 'rejected',
                'error': f'{type(exc).__name__}: {exc}',
            }
        _write_json(result_path, payload)

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    result = service.refresh_recovery_type2(root, clearup_id='ClearUp_002', source='mcp_remote')
    thread.join(timeout=2)

    assert result['status'] == 'GREEN'
    assert result['post_migrate_recovery_refresh'] is True
    assert result['deletion_performed'] is False
    assert result['reconstruction_sources']['existing_recovery_zip'] >= 1
    assert result['reconstruction_sources']['proven_empty_identity'] >= 1
    assert service.export_info(root, clearup_id='ClearUp_002', source='mcp_remote')['status'] == 'GREEN'
