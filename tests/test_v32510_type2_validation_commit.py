from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'slimmemeterportal_import/rootfs/app'
PM=APP/'projectmanager_v2'

import sys
sys.path.insert(0,str(APP))
sys.path.insert(0,str(PM))

import clearup_type2_service as service


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')


def test_watcher_call_accepts_exact_result_in_deadline_grace(tmp_path, monkeypatch):
    _write(tmp_path/'App/VERSIE.txt','32.5.10\n')
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'):
        (tmp_path/rel).mkdir(parents=True,exist_ok=True)
    (tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Runtime').mkdir(parents=True,exist_ok=True)
    plan={'plan_sha256':'a'*64}
    monkeypatch.setattr(service,'WATCHER_TIMEOUT_SECONDS',0.05)

    def writer():
        req=tmp_path/'Inbox/project_clearup_move_request.json'
        deadline=time.monotonic()+1
        while not req.exists() and time.monotonic()<deadline:
            time.sleep(0.002)
        raw=json.loads(req.read_text(encoding='utf-8'))
        # Deliberately after the main timeout, inside the new grace window.
        time.sleep(0.07)
        result=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Runtime/project_clearup_move_result.json'
        result.write_text(json.dumps({
            'schema':'energie_clearup_type2_result_v1',
            'request_id':raw['request_id'],
            'status':'completed',
            'result':{'status':'GREEN','clearup_id':'ClearUp_099'}
        }),encoding='utf-8')
    th=threading.Thread(target=writer,daemon=True); th.start()
    got=service._watcher_call(tmp_path,operation='type2_prepare',clearup_id='ClearUp_099',plan=plan)
    th.join(timeout=1)
    assert got['status']=='GREEN'
    assert got['clearup_id']=='ClearUp_099'


def test_validate_routes_proof_to_privileged_commit_not_direct_atomic_write(tmp_path, monkeypatch):
    _write(tmp_path/'App/VERSIE.txt','32.5.10\n')
    _write(tmp_path/'Inbox/release_controller/current.json',json.dumps({'status':'COMPLETE','phase':'COMPLETE'}))
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'):
        (tmp_path/rel).mkdir(parents=True,exist_ok=True)
    _write(tmp_path/'Inbox/runtime_old/state.json','old\n')
    _write(tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new/state.json','old\n')
    _write(tmp_path/'App/contract.txt','destination-active\n')
    plans=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Plans'; plans.mkdir(parents=True)
    plan={
      'schema':'energie_clearup_type2_plan_v1','classification':'TYPE2','clearup_id':'ClearUp_099','status':'READY','minimum_release':'32.5.7',
      'items':[{'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','reason':'test','path_key':'',
                'contract_checks':[{'path':'App/contract.txt','must_contain':['destination-active'],'must_not_contain':['old-source-active']}]}]
    }
    (plans/'ClearUp_099.json').write_text(json.dumps(plan),encoding='utf-8')
    loaded=service._load_plan(tmp_path,'ClearUp_099')
    state=tmp_path/service.STATE_ROOT_REL/'ClearUp_099.json'; state.parent.mkdir(parents=True)
    cutover={'Inbox/runtime_old':service._tree_rows_for_validation(tmp_path,tmp_path/'Inbox/runtime_old')}
    state.write_text(json.dumps({
        'phase':'MIGRATED_PENDING_VALIDATION','plan_sha256':loaded['plan_sha256'],
        'cutover_rows':cutover,'activated_at_epoch':time.time()-1
    }),encoding='utf-8')
    export=tmp_path/service.EXPORT_ROOT_REL/'ClearUp_099_Type2_recovery.zip'
    export.parent.mkdir(parents=True)
    import zipfile
    with zipfile.ZipFile(export,'w') as z:
        z.writestr('TYPE2_MANIFEST.json',json.dumps({'clearup_id':'ClearUp_099','plan_sha256':loaded['plan_sha256'],'items':[]}))
    called={}
    def commit(root, *, operation, clearup_id, plan, explicit_user_text='', validation_proof=None):
        called['operation']=operation
        called['proof']=validation_proof
        return {'status':'GREEN','clearup_id':clearup_id,'phase':'VALIDATION_COMMITTED','validation_status':validation_proof['status']}
    monkeypatch.setattr(service,'_watcher_call',commit)
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS','0.01')
    proof=service.validate_type2(tmp_path,clearup_id='ClearUp_099',source='mcp_remote')
    assert proof['status']=='GREEN'
    assert called['operation']=='type2_validation_commit'
    assert called['proof']['schema']=='energie_clearup_type2_validation_v2'
    # No direct writer path is required from the embedded PM anymore.
    assert not (tmp_path/service.VALIDATION_ROOT_REL/'ClearUp_099.json').exists()
