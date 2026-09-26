import importlib.util
import json
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'slimmemeterportal_import/rootfs/app'
PM=APP/'projectmanager_v2'
EXEC=ROOT/'tools/project_clearup_move_executor.py'
sys.path.insert(0,str(APP))
sys.path.insert(0,str(PM))
import clearup_type2_service as service


def load_executor():
    spec=importlib.util.spec_from_file_location('type2_exec_test',EXEC)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod


def seed(tmp_path: Path):
    (tmp_path/'App/slimmemeterportal_import/rootfs/app/projectmanager_v2').mkdir(parents=True)
    shutil.copy2(PM/'clearup_type2_service.py', tmp_path/'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_type2_service.py')
    (tmp_path/'App/VERSIE.txt').write_text('32.5.7\n')
    (tmp_path/'Inbox/release_controller').mkdir(parents=True)
    (tmp_path/'Inbox/release_controller/current.json').write_text(json.dumps({'status':'COMPLETE','phase':'COMPLETE'}))
    for d in ('Inbox/incoming','Inbox/processing','Inbox/logs'):(tmp_path/d).mkdir(parents=True,exist_ok=True)
    src=tmp_path/'Inbox/runtime_old'; src.mkdir(); (src/'state.json').write_text('{"x":1}\n'); (src/'status').mkdir(); (src/'status/current.json').write_text('{"status":"GREEN"}\n')
    contract=tmp_path/'App/contract.txt'; contract.write_text('Data/03_Systeem/Projectmanager/Runtime/runtime_new\n')
    plans=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Plans'; plans.mkdir(parents=True)
    plan={
      'schema':'energie_clearup_type2_plan_v1','classification':'TYPE2','clearup_id':'ClearUp_002','status':'READY','minimum_release':'32.5.7',
      'items':[{'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','reason':'move runtime state','contract_checks':[{'path':'App/contract.txt','must_contain':['Data/03_Systeem/Projectmanager/Runtime/runtime_new'],'must_not_contain':['Inbox/runtime_old']}]}]
    }
    (plans/'ClearUp_002.json').write_text(json.dumps(plan))
    return plan


def request(root,op,approval=False):
    plan=service._load_plan(root,'ClearUp_002')
    return {'schema':'energie_clearup_type2_request_v1','request_id':'a'*32,'operation':op,'clearup_id':'ClearUp_002','release_version':'32.5.7','expires_at':'2099-01-01T00:00:00+00:00','plan_sha256':plan['plan_sha256'],'explicit_user_approval':approval,'mailbox_snapshot_before':service._snapshot_release_dirs(root)}


def test_type2_prepare_migrate_finalize_restore(tmp_path, monkeypatch):
    seed(tmp_path); mod=load_executor()
    rid,prepared=mod.execute_type2(tmp_path,request(tmp_path,'type2_prepare'))
    assert prepared['phase']=='PREPARED' and prepared['deletion_performed'] is False
    assert (tmp_path/'Inbox/runtime_old').is_dir()
    assert (tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Exports/ClearUp_002_Type2_recovery.zip').is_file()

    rid,migrated=mod.execute_type2(tmp_path,request(tmp_path,'type2_migrate',True))
    assert migrated['phase']=='MIGRATED_PENDING_VALIDATION'
    assert (tmp_path/'Inbox/runtime_old/state.json').is_file()
    assert (tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new/state.json').read_text()=='{"x":1}\n'

    def _commit(root, *, operation, clearup_id, plan, explicit_user_text='', validation_proof=None):
        assert operation == 'type2_validate'
        src_rows=service._tree_rows_for_validation(Path(root),Path(root)/'Inbox/runtime_old')
        dst_rows=service._tree_rows_for_validation(Path(root),Path(root)/'Data/03_Systeem/Projectmanager/Runtime/runtime_new')
        proof={
            'schema':'energie_clearup_type2_validation_v2','status':'GREEN','clearup_id':clearup_id,
            'plan_sha256':plan['plan_sha256'],'checks':[{
                'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','path_key':None,
                'source_rows_sha256':service._json_sha(src_rows),'destination_rows_sha256':service._json_sha(dst_rows),
            }],
            'failures':[],'evidence':['Data/03_Systeem/Projectmanager/Runtime/runtime_new'],
            'old_source_quiescence_seconds':0.01,'validation_authority':'privileged_watcher_full_validation',
        }
        path=Path(root)/service.VALIDATION_ROOT_REL/f'{clearup_id}.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(proof),encoding='utf-8')
        return proof
    monkeypatch.setattr(service,'_watcher_call',_commit)

    proof=service.validate_type2(tmp_path,clearup_id='ClearUp_002',source='mcp_remote')
    assert proof['status']=='GREEN' and proof['checks'][0]['source_rows_sha256'] and proof['checks'][0]['destination_rows_sha256']
    rid,done=mod.execute_type2(tmp_path,request(tmp_path,'type2_finalize',True))
    assert done['phase']=='COMPLETE' and done['delete_performed'] is True
    assert not (tmp_path/'Inbox/runtime_old').exists()
    assert (tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new/state.json').is_file()

    rid,restored=mod.execute_type2(tmp_path,request(tmp_path,'type2_restore',True))
    assert restored['phase']=='RESTORED'
    assert (tmp_path/'Inbox/runtime_old/state.json').read_text()=='{"x":1}\n'
    assert (tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new/state.json').is_file()


def test_type2_protects_release_mailboxes(tmp_path):
    seed(tmp_path)
    p=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Plans/ClearUp_002.json'
    plan=json.loads(p.read_text()); plan['items'][0]['source']='Inbox/processing'; p.write_text(json.dumps(plan))
    try: service._load_plan(tmp_path,'ClearUp_002')
    except RuntimeError as exc: assert 'bounded Inbox scope' in str(exc)
    else: raise AssertionError('protected mailbox accepted')


def test_type2_requires_contract_checks(tmp_path):
    seed(tmp_path)
    p=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Plans/ClearUp_002.json'
    plan=json.loads(p.read_text()); plan['items'][0]['contract_checks']=[]; p.write_text(json.dumps(plan))
    try: service._load_plan(tmp_path,'ClearUp_002')
    except RuntimeError as exc: assert 'contract_checks' in str(exc)
    else: raise AssertionError('missing contract checks accepted')


def test_type2_migrate_requires_approval(tmp_path):
    seed(tmp_path); mod=load_executor(); mod.execute_type2(tmp_path,request(tmp_path,'type2_prepare'))
    try: mod.execute_type2(tmp_path,request(tmp_path,'type2_migrate',False))
    except mod.RequestRejected as exc: assert 'goedkeuring' in str(exc)
    else: raise AssertionError('migration without approval accepted')


def test_projectmanager_admin_transport_routes_type2_prepare(tmp_path, monkeypatch):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from task_engine import TaskStore
    from command_processor import CommandProcessor
    class _Mode:
        def set(self, mode, *, reason='', source=''): return {'mode':mode}
    monkeypatch.setattr(service,'prepare_type2',lambda project_root,clearup_id,source:{'status':'GREEN','clearup_id':clearup_id,'deletion_performed':False})
    commands=CommandStore(tmp_path/'cmd.json'); decisions=DecisionQueue(tmp_path/'dec.json'); tasks=TaskStore(tmp_path/'tasks.json')
    command=commands.enqueue({'intent':'admin_update','classification_hint':'clearup_type2_prepare','artifact_path':'ClearUp_002','source':'mcp_remote','text':'prepare'})
    processor=CommandProcessor(commands,decisions,_Mode(),tasks,project_root=tmp_path)
    finished=processor.process_next()
    assert finished['status']=='DONE'
    assert finished['result']['action']=='clearup_type2_prepare'
    assert finished['result']['transport_intent']=='admin_update'


def test_type2_prepare_precedes_code_switch_but_migrate_requires_new_contract(tmp_path):
    seed(tmp_path); mod=load_executor()
    (tmp_path/'App/contract.txt').write_text('Inbox/runtime_old\n')
    rid,prepared=mod.execute_type2(tmp_path,request(tmp_path,'type2_prepare'))
    assert prepared['phase']=='PREPARED'
    try: mod.execute_type2(tmp_path,request(tmp_path,'type2_migrate',True))
    except RuntimeError as exc: assert 'contract' in str(exc).lower() or 'old reference' in str(exc).lower()
    else: raise AssertionError('migration accepted before active contract switch')
