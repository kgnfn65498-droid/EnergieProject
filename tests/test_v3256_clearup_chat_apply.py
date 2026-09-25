from __future__ import annotations
import json, shutil
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'slimmemeterportal_import/rootfs/app'
import sys
sys.path.insert(0,str(APP))
sys.path.insert(0,str(APP/'projectmanager_v2'))
import clearup_chat_service as clearup_service
from clearup_chat_service import apply_clearup_001, ROOTS
from command_gateway import plan_command


def seed(tmp_path: Path):
    p=tmp_path/'App'; p.mkdir(); (p/'VERSIE.txt').write_text('32.5.7\n')
    rc=tmp_path/'Inbox/release_controller'; rc.mkdir(parents=True); (rc/'current.json').write_text(json.dumps({'status':'COMPLETE','phase':'COMPLETE'}))
    (tmp_path/'Inbox/processing').mkdir(parents=True)
    for rel in ROOTS:
        q=tmp_path/rel
        if rel.endswith('1812Z'): q.parent.mkdir(parents=True,exist_ok=True); q.write_bytes(b'')
        else: q.mkdir(parents=True,exist_ok=True); (q/'payload.txt').write_text(rel)
    stage=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Staging/ClearUp_001'; stage.mkdir(parents=True)
    for rel in ROOTS:
        src=tmp_path/rel; dst=stage/src.name
        if src.is_dir(): shutil.copytree(src,dst)
        else: shutil.copy2(src,dst)
    return tmp_path


def _successful_watcher(root: Path, **kwargs):
    for rel in ROOTS:
        p=root/rel
        if p.is_dir(): shutil.rmtree(p)
        else: p.unlink()
    return {'status':'GREEN','delete_performed':True,'removed':list(ROOTS),'removed_count':4}


def test_gateway_keeps_clearup_apply_and_admin_update_transport_available():
    assert plan_command({'intent':'clearup_apply'})['action']=='clearup_apply'
    assert plan_command({'intent':'admin_update'})['action']=='admin_update'


def test_akkoord_deletes_only_allowlisted_after_recovery_reverify(tmp_path, monkeypatch):
    root=seed(tmp_path); keep=root/'Inbox/incoming'; keep.mkdir(); marker=keep/'KEEP.txt'; marker.write_text('safe')
    monkeypatch.setattr(clearup_service,'_watcher_delete',lambda project_root,**kwargs:_successful_watcher(project_root,**kwargs))
    result=apply_clearup_001(root,explicit_user_text='akkoord',source='mcp_remote')
    assert result['status']=='GREEN' and result['removed_count']==4 and result['processing_untouched'] is True
    assert result['incoming_untouched'] is True and result['watcher_privileged_executor'] is True
    assert all(not (root/x).exists() for x in ROOTS)
    assert marker.read_text()=='safe'


def test_refuses_without_explicit_approval(tmp_path):
    root=seed(tmp_path)
    with pytest.raises(RuntimeError,match='approval'):
        apply_clearup_001(root,explicit_user_text='verder',source='mcp_remote')
    assert all((root/x).exists() for x in ROOTS)


def test_refuses_if_recovery_differs(tmp_path):
    root=seed(tmp_path)
    (root/ROOTS[0]/'payload.txt').write_text('changed')
    with pytest.raises(RuntimeError,match='mismatch'):
        apply_clearup_001(root,explicit_user_text='akkoord',source='mcp_remote')
    assert all((root/x).exists() for x in ROOTS)


def test_refuses_during_processing(tmp_path):
    root=seed(tmp_path); (root/'Inbox/processing/EnergieProject_v32.5.8.zip').write_bytes(b'x')
    with pytest.raises(RuntimeError,match='processing active'):
        apply_clearup_001(root,explicit_user_text='akkoord',source='mcp_remote')
    assert all((root/x).exists() for x in ROOTS)

from command_store import CommandStore
from decision_queue import DecisionQueue
from task_engine import TaskStore
from command_processor import CommandProcessor

class _Mode:
    def set(self, mode, *, reason='', source=''):
        return {'mode':mode}


def test_projectmanager_admin_update_transport_executes_clearup_without_new_mcp_intent(tmp_path, monkeypatch):
    root=seed(tmp_path)
    incoming=root/'Inbox/incoming'; incoming.mkdir(); keep=incoming/'KEEP.zip'; keep.write_bytes(b'keep')
    monkeypatch.setattr(clearup_service,'_watcher_delete',lambda project_root,**kwargs:_successful_watcher(project_root,**kwargs))
    commands=CommandStore(tmp_path/'cmd.json'); decisions=DecisionQueue(tmp_path/'dec.json'); tasks=TaskStore(tmp_path/'tasks.json')
    command=commands.enqueue({'intent':'admin_update','classification_hint':'clearup_apply','source':'mcp_remote','text':'akkoord','title':'ClearUp_001 apply'})
    processor=CommandProcessor(commands,decisions,_Mode(),tasks,project_root=root)
    finished=processor.process_next()
    assert finished['status']=='DONE'
    assert finished['result']['action']=='clearup_apply'
    assert finished['result']['transport_intent']=='admin_update'
    assert finished['result']['status']=='GREEN'
    assert finished['result']['delete_performed'] is True
    assert keep.read_bytes()==b'keep'
    assert all(not (root/x).exists() for x in ROOTS)
