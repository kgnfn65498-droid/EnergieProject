from __future__ import annotations
import json, shutil
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'slimmemeterportal_import/rootfs/app'
import sys
sys.path.insert(0,str(APP/'projectmanager_v2'))
from clearup_chat_service import apply_clearup_001, ROOTS
from command_gateway import plan_command


def seed(tmp_path: Path):
    p=tmp_path/'App'; p.mkdir(); (p/'VERSIE.txt').write_text('32.5.6\n')
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


def test_gateway_exposes_clearup_apply():
    assert plan_command({'intent':'clearup_apply'})['action']=='clearup_apply'

def test_akkoord_deletes_only_allowlisted_after_recovery_reverify(tmp_path):
    root=seed(tmp_path); keep=root/'Inbox/incoming'; keep.mkdir(); marker=keep/'KEEP.txt'; marker.write_text('safe')
    result=apply_clearup_001(root,explicit_user_text='akkoord',source='mcp_remote')
    assert result['status']=='GREEN' and result['removed_count']==4 and result['processing_untouched'] is True
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
    root=seed(tmp_path); (root/'Inbox/processing/EnergieProject_v32.5.7.zip').write_bytes(b'x')
    with pytest.raises(RuntimeError,match='processing active'):
        apply_clearup_001(root,explicit_user_text='akkoord',source='mcp_remote')
    assert all((root/x).exists() for x in ROOTS)
