from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import types
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup_migrated_root(tmp_path: Path):
    root = tmp_path / 'project'
    source_rel = 'Inbox/projectmanager_v2/RuntimeV2'
    dest_rel = 'Data/03_Systeem/Projectmanager/RuntimeV2'
    source = root / source_rel
    destination = root / dest_rel
    source.mkdir(parents=True)
    destination.mkdir(parents=True)
    (source / 'current.json').write_text('{"stable":true}\n', encoding='utf-8')
    (source / '.release_transition_permission_probe_20260914T1723Z').mkdir()
    (source / '.release_transition_permission_probe_20260914T1723Z/current.json').write_bytes(b'')
    (destination / 'current.json').write_text('{"live":true}\n', encoding='utf-8')

    (root / 'App').mkdir()
    (root / 'App/VERSIE.txt').write_text('32.5.15\n', encoding='utf-8')
    contract = root / 'App/tools/clearup_type2_path_contract.json'
    contract.parent.mkdir(parents=True)
    contract.write_text('{"ClearUp_002": "GREEN"}\n', encoding='utf-8')
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed'):
        (root / rel).mkdir(parents=True, exist_ok=True)
    _write_json(root / 'Inbox/release_controller/current.json', {'status':'COMPLETE','phase':'COMPLETE'})

    plan = {
        'schema':'energie_clearup_type2_plan_v1', 'classification':'TYPE2', 'clearup_id':'ClearUp_002',
        'status':'READY', 'minimum_release':'32.5.7',
        'items':[{
            'source':source_rel, 'destination':dest_rel, 'path_key':'pm_runtime',
            'reason':'test',
            'contract_checks':[{'path':'App/tools/clearup_type2_path_contract.json','must_contain':['"ClearUp_002": "GREEN"'],'must_not_contain':['"ClearUp_002": "RED"']}],
            'runtime_proof_paths':['heartbeat/manager.json'],
        }],
    }
    _write_json(root / 'Data/03_Systeem/Projectmanager/ClearUp/Plans/ClearUp_002.json', plan)
    loaded = service._load_plan(root, 'ClearUp_002')
    rows = executor._tree_rows(source, root)
    state = {
        'status':'GREEN','clearup_id':'ClearUp_002','phase':'MIGRATED_PENDING_VALIDATION',
        'plan_sha256':loaded['plan_sha256'],'source_preserved':True,'deletion_performed':False,
        'cutover_rows':{source_rel:rows},
    }
    _write_json(root / service.STATE_ROOT_REL / 'ClearUp_002.json', state)
    _write_json(root / service.VALIDATION_ROOT_REL / 'ClearUp_002.json', {
        'schema':'energie_clearup_type2_validation_v2','status':'GREEN','clearup_id':'ClearUp_002',
        'plan_sha256':loaded['plan_sha256'],'failures':[],
    })
    _write_json(root / 'Data/03_Systeem/Projectmanager/ClearUp/PathActivation/pm_runtime.json', {
        'schema':'energie_clearup_system_path_contract_v1','key':'pm_runtime','source':source_rel,'destination':dest_rel,
        'active':True,'clearup_id':'ClearUp_002','plan_sha256':loaded['plan_sha256'],
    })

    # Existing stage/ZIP is deliberately internally inconsistent: manifest says probe is zero bytes,
    # while the archived probe contains bytes. This mirrors the live 32.5.14 failure class.
    stage = root / service.STAGING_ROOT_REL / 'ClearUp_002'
    staged_source = stage / 'original' / source_rel
    staged_source.mkdir(parents=True)
    (staged_source / 'current.json').write_text('{"stable":true}\n', encoding='utf-8')
    (staged_source / '.release_transition_permission_probe_20260914T1723Z').mkdir()
    (staged_source / '.release_transition_permission_probe_20260914T1723Z/current.json').write_bytes(b'NOT-ZERO')
    bad_manifest = {
        'schema':'energie_clearup_type2_recovery_v1','classification':'TYPE2','clearup_id':'ClearUp_002',
        'plan_sha256':loaded['plan_sha256'],'created_at':datetime.now(timezone.utc).isoformat(),
        'deletion_performed':False,
        'items':[{'source':source_rel,'destination':dest_rel,'source_rows':rows,'reason':'test','path_key':'pm_runtime'}],
    }
    _write_json(stage / 'TYPE2_MANIFEST.json', bad_manifest)
    export = root / service.EXPORT_ROOT_REL / 'ClearUp_002_Type2_recovery.zip'
    export.parent.mkdir(parents=True)
    with zipfile.ZipFile(export, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob('*')):
            arc=p.relative_to(stage).as_posix()
            if p.is_dir(): z.writestr(arc.rstrip('/')+'/', b'')
            else: z.write(p, arc)
    return root, loaded, source, destination, export


def _request(root: Path, plan: dict) -> dict:
    return {
        'schema':'energie_clearup_type2_request_v1','request_id':'a'*32,
        'operation':'type2_refresh_recovery','clearup_id':'ClearUp_002','release_version':'32.5.15',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat(),
        'plan_sha256':plan['plan_sha256'],'explicit_user_approval':False,
        'mailbox_snapshot_before':service._snapshot_release_dirs(root),
    }


def test_post_migrate_refresh_rebuilds_bad_002_without_mutating_source_or_destination(tmp_path, monkeypatch):
    root, plan, source, destination, export = _setup_migrated_root(tmp_path)
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    source_before = executor._tree_rows(source, root)
    destination_before = executor._tree_rows(destination, root)
    bad_sha = _sha(export)
    with pytest.raises(RuntimeError, match='payload size mismatch'):
        service.export_info(root, clearup_id='ClearUp_002', source='mcp_remote')

    _, result = executor.execute_type2(root, _request(root, plan))
    assert result['status'] == 'GREEN'
    assert result['post_migrate_recovery_refresh'] is True
    assert result['deletion_performed'] is False
    assert result['source_preserved'] is True
    assert result['destination_untouched'] is True
    assert _sha(export) != bad_sha
    assert executor._tree_rows(source, root) == source_before
    assert executor._tree_rows(destination, root) == destination_before
    info = service.export_info(root, clearup_id='ClearUp_002', source='mcp_remote')
    assert info['status'] == 'GREEN'
    assert info['sha256'] == _sha(export)
    state = json.loads((root / service.STATE_ROOT_REL / 'ClearUp_002.json').read_text(encoding='utf-8'))
    assert state['phase'] == 'MIGRATED_PENDING_VALIDATION'
    assert state['recovery_refresh']['status'] == 'GREEN'


def test_post_migrate_refresh_refuses_changed_preserved_source(tmp_path, monkeypatch):
    root, plan, source, destination, export = _setup_migrated_root(tmp_path)
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    old_export = export.read_bytes()
    (source / 'current.json').write_text('{"changed":true}\n', encoding='utf-8')
    with pytest.raises(executor.RequestRejected, match='preserved source differs'):
        executor.execute_type2(root, _request(root, plan))
    assert export.read_bytes() == old_export
    assert destination.exists()


def _load_hotfix():
    spec = importlib.util.spec_from_file_location('hotfix_32515', ROOT / 'tools/native_mcp_runtime_contract_hotfix.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _MCP:
    def custom_route(self, *args, **kwargs):
        return lambda fn: fn


def test_bad_002_does_not_block_valid_003_through_012_download_descriptors(tmp_path, monkeypatch):
    hotfix = _load_hotfix()
    project = tmp_path / 'project'; project.mkdir()
    system = tmp_path / 'system'; (system / 'Projectmanager/ClearUp/State').mkdir(parents=True)
    _write_json(system / 'Projectmanager/ClearUp/State/TYPE2_EXTERNAL_RECOVERY_GATE.json', {
        'status':'BLOCK_DELETE_UNTIL_EXTERNAL_COPY_CONFIRMED','delete_allowed':False,
        'required_exports':[f'ClearUp_{i:03d}_Type2_recovery.zip' for i in range(2,13)],
    })
    monkeypatch.setenv('ENERGIE_SYSTEM_ROOT', str(system))
    monkeypatch.setenv('ENERGIE_ROOT', str(project))
    fake=types.ModuleType('tools_clearup_export')
    def info(cid):
        if cid == 'ClearUp_002':
            raise ValueError('payload size mismatch')
        return {'status':'GREEN','clearup_id':cid,'artifact':f'{cid}_Type2_recovery.zip','size':1,'sha256':hashlib.sha256(cid.encode()).hexdigest(),'plan_sha256':'a'*64,'item_count':1,'deletion_performed':False}
    fake.clearup_type2_recovery_export_info=info
    sys.modules['tools_clearup_export']=fake
    ns={'Path':Path,'os':os,'json':json,'Any':Any,'mcp':_MCP()}
    exec(hotfix.TYPE2_DOWNLOAD_BRIDGE_BLOCK, ns)
    payload=ns['_attach_type2_recovery_downloads']({'status':'COMPLETE'})['type2_external_recovery']
    assert payload['status']=='PARTIAL_BLOCKED'
    assert payload['delete_allowed'] is False
    assert payload['required_count']==11 and payload['verified_count']==10
    assert len(payload['downloads'])==10
    assert {x['clearup_id'] for x in payload['downloads']} == {f'ClearUp_{i:03d}' for i in range(3,13)}
    assert payload['failures'][0]['clearup_id']=='ClearUp_002'


def test_native_mcp_runtime_root_retires_old_inbox_alias_and_updates_compose(tmp_path):
    hotfix=_load_hotfix()
    old=hotfix.PM_RUNTIME_ROOT_OLD + '\nrest = 1\n'
    patched, changed, reason=hotfix._ensure_pm_runtime_root(old)
    assert changed is True and reason=='pm_runtime_root_canonicalized'
    assert hotfix.PM_RUNTIME_ROOT_MARKER in patched
    assert "_pm_runtime_env = '/system/Projectmanager/RuntimeV2'" in patched
    root=tmp_path/'project'; compose=root/'Infra/docker-compose.yml'; compose.parent.mkdir(parents=True)
    compose.write_text('environment:\n  PM_SYSTEM_ROOT: /project/Inbox/projectmanager_v2/RuntimeV2\n',encoding='utf-8')
    changed2, reason2=hotfix._ensure_native_compose_runtime_root(root)
    assert changed2 is True and reason2=='native_compose_runtime_root_canonicalized'
    text=compose.read_text(encoding='utf-8')
    assert 'PM_SYSTEM_ROOT: /system/Projectmanager/RuntimeV2' in text
    assert '/project/Inbox/projectmanager_v2/RuntimeV2' not in text
