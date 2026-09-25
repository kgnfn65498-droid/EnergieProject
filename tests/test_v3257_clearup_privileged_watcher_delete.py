from __future__ import annotations
import importlib.util, json, shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXEC=ROOT/'tools/project_clearup_move_executor.py'
SERVICE=ROOT/'slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_chat_service.py'
spec=importlib.util.spec_from_file_location('clearup_exec_3257',EXEC); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)


def seed(tmp_path: Path):
    app=tmp_path/'App'; app.mkdir(); (app/'VERSIE.txt').write_text('32.5.7\n')
    pm=app/'slimmemeterportal_import/rootfs/app/projectmanager_v2'; pm.mkdir(parents=True)
    shutil.copy2(SERVICE,pm/'clearup_chat_service.py')
    rc=tmp_path/'Inbox/release_controller'; rc.mkdir(parents=True); (rc/'current.json').write_text(json.dumps({'status':'COMPLETE','phase':'COMPLETE'}))
    (tmp_path/'Inbox/processing').mkdir(parents=True)
    (tmp_path/'Inbox/incoming').mkdir(parents=True); (tmp_path/'Inbox/incoming/KEEP.txt').write_text('safe')
    roots=mod.TYPE1_ROOTS
    for rel in roots:
        q=tmp_path/rel
        if rel.endswith('1812Z'): q.parent.mkdir(parents=True,exist_ok=True); q.write_bytes(b'')
        else: q.mkdir(parents=True,exist_ok=True); (q/'payload.txt').write_text(rel)
    stage=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Staging/ClearUp_001'; stage.mkdir(parents=True)
    for rel in roots:
        src=tmp_path/rel; dst=stage/src.name
        if src.is_dir(): shutil.copytree(src,dst)
        else: shutil.copy2(src,dst)
    sys_path=str(pm)
    import sys
    sys.path.insert(0,sys_path)
    try:
        import clearup_chat_service as service
        rows=service._collect(tmp_path)
    finally:
        sys.path.remove(sys_path)
        sys.modules.pop('clearup_chat_service',None)
    return rows


def test_privileged_executor_exact_type1_delete_preserves_incoming(tmp_path):
    rows=seed(tmp_path)
    request=tmp_path/'Inbox/project_clearup_move_request.json'; result=tmp_path/'Inbox/logs/project_clearup_move_result.json'; result.parent.mkdir(parents=True)
    rid='a'*32
    request.write_text(json.dumps({
        'schema':mod.TYPE1_DELETE_SCHEMA,'request_id':rid,'operation':'clearup_001_delete','clearup_id':'ClearUp_001',
        'release_version':'32.5.7','created_at':datetime.now(timezone.utc).isoformat(),
        'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat(),
        'roots':list(mod.TYPE1_ROOTS),'expected_rows':rows,
        'staging_relative':'Data/03_Systeem/Projectmanager/ClearUp/Staging/ClearUp_001'}))
    code,payload=mod.process(tmp_path,request,result)
    assert code==0 and payload['schema']==mod.TYPE1_DELETE_RESULT_SCHEMA and payload['delete_performed'] is True
    assert payload['result']['status']=='GREEN' and payload['result']['removed_count']==4
    assert all(not (tmp_path/x).exists() for x in mod.TYPE1_ROOTS)
    assert (tmp_path/'Inbox/incoming/KEEP.txt').read_text()=='safe'


def test_type1_delete_refuses_tampered_live_tree(tmp_path):
    rows=seed(tmp_path)
    (tmp_path/mod.TYPE1_ROOTS[0]/'payload.txt').write_text('tampered')
    request=tmp_path/'Inbox/project_clearup_move_request.json'; result=tmp_path/'Inbox/logs/project_clearup_move_result.json'; result.parent.mkdir(parents=True)
    request.write_text(json.dumps({
        'schema':mod.TYPE1_DELETE_SCHEMA,'request_id':'b'*32,'operation':'clearup_001_delete','clearup_id':'ClearUp_001',
        'release_version':'32.5.7','expires_at':(datetime.now(timezone.utc)+timedelta(minutes=1)).isoformat(),
        'roots':list(mod.TYPE1_ROOTS),'expected_rows':rows}))
    code,payload=mod.process(tmp_path,request,result)
    assert code!=0 and payload['delete_performed'] is False
    assert all((tmp_path/x).exists() for x in mod.TYPE1_ROOTS)
