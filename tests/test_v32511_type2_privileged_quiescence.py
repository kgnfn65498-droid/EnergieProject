from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(text,encoding='utf-8')

def test_privileged_validation_commit_owns_quiescence_hash(tmp_path, monkeypatch):
    import tools.project_clearup_move_executor as executor

    source = tmp_path/'Inbox/runtime_old'
    destination = tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new'
    _write(source/'state.json', 'stable\n')
    _write(destination/'state.json', 'stable\n')
    validation_root = tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Validation'
    validation_root.mkdir(parents=True)

    class DummyService:
        STAGING_ROOT_REL=Path('Data/03_Systeem/Projectmanager/ClearUp/Staging')
        EXPORT_ROOT_REL=Path('Data/03_Systeem/Projectmanager/ClearUp/Exports')
        STATE_ROOT_REL=Path('Data/03_Systeem/Projectmanager/ClearUp/State')
        VALIDATION_ROOT_REL=Path('Data/03_Systeem/Projectmanager/ClearUp/Validation')
        @staticmethod
        def _snapshot_release_dirs(root):
            return {'incoming': [], 'processing': [], 'processed': [], 'failed': []}

    plan={'plan_sha256':'b'*64,'items':[{
        'source':'Inbox/runtime_old',
        'destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new',
        'path_key':'',
    }]}
    monkeypatch.setattr(executor,'_type2_validate_request',lambda root,request:('a'*32,'type2_validation_commit','ClearUp_099',plan,DummyService))
    monkeypatch.setattr(executor,'_type2_manifest',lambda *args,**kwargs:{'items':plan['items']})
    proof={
        'schema':'energie_clearup_type2_validation_v2',
        'status':'GREEN','clearup_id':'ClearUp_099','plan_sha256':plan['plan_sha256'],
        'failures':[], 'old_source_quiescence_seconds':0.01,
        'checks':[{'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','source_rows_sha256':'pm-snapshot-different','destination_rows_sha256':'unused'}],
        'evidence':['Data/03_Systeem/Projectmanager/Runtime/runtime_new'],
    }
    request={'validation_proof':proof,'mailbox_snapshot_before':DummyService._snapshot_release_dirs(tmp_path)}
    _, result=executor.execute_type2(tmp_path,request)
    assert result['status']=='GREEN'
    committed=json.loads((validation_root/'ClearUp_099.json').read_text(encoding='utf-8'))
    check=committed['checks'][0]
    assert check['pm_observed_source_rows_sha256']=='pm-snapshot-different'
    assert check['source_rows_sha256']!='pm-snapshot-different'
    assert check['source_quiescence_authority']=='privileged_watcher_double_snapshot'
    assert committed['source_quiescence_authority']=='privileged_watcher_double_snapshot'


def test_privileged_validation_commit_rejects_real_source_mutation(tmp_path, monkeypatch):
    import tools.project_clearup_move_executor as executor

    source = tmp_path/'Inbox/runtime_old'
    destination = tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new'
    _write(source/'state.json', 'before\n')
    _write(destination/'state.json', 'before\n')
    (tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Validation').mkdir(parents=True)

    class DummyService:
        STAGING_ROOT_REL=Path('Data/03_Systeem/Projectmanager/ClearUp/Staging')
        EXPORT_ROOT_REL=Path('Data/03_Systeem/Projectmanager/ClearUp/Exports')
        STATE_ROOT_REL=Path('Data/03_Systeem/Projectmanager/ClearUp/State')
        VALIDATION_ROOT_REL=Path('Data/03_Systeem/Projectmanager/ClearUp/Validation')
        @staticmethod
        def _snapshot_release_dirs(root):
            return {'incoming': [], 'processing': [], 'processed': [], 'failed': []}

    plan={'plan_sha256':'c'*64,'items':[{'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','path_key':''}]}
    monkeypatch.setattr(executor,'_type2_validate_request',lambda root,request:('d'*32,'type2_validation_commit','ClearUp_098',plan,DummyService))
    monkeypatch.setattr(executor,'_type2_manifest',lambda *args,**kwargs:{'items':plan['items']})
    proof={
        'schema':'energie_clearup_type2_validation_v2','status':'GREEN','clearup_id':'ClearUp_098','plan_sha256':plan['plan_sha256'],
        'failures':[],'old_source_quiescence_seconds':0.08,
        'checks':[{'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','source_rows_sha256':'anything','destination_rows_sha256':'unused'}],
        'evidence':['Data/03_Systeem/Projectmanager/Runtime/runtime_new'],
    }
    def mutate():
        time.sleep(0.03)
        _write(source/'state.json','after\n')
    th=threading.Thread(target=mutate,daemon=True); th.start()
    with pytest.raises(executor.RequestRejected,match='old source still mutating during validation commit'):
        executor.execute_type2(tmp_path,{'validation_proof':proof,'mailbox_snapshot_before':DummyService._snapshot_release_dirs(tmp_path)})
    th.join(timeout=1)
