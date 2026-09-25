from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
EXEC = TOOLS / 'project_clearup_move_executor.py'

sys.path.insert(0, str(APP))
sys.path.insert(0, str(PM))
sys.path.insert(0, str(TOOLS))

import clearup_type2_service as type2
import clearup_chat_service as type1


def load_executor():
    spec = importlib.util.spec_from_file_location('clearup_exec_e2e_3259', EXEC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, text: str = 'seed\n') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _is_file_source(rel: str) -> bool:
    name = Path(rel).name
    return (
        '.' in name
        or name.startswith('.')
        or name.endswith('.jsonl')
        or name.endswith('.txt')
        or name.endswith('.yml')
    )


def seed_common(root: Path) -> None:
    _write(root / 'App/VERSIE.txt', '32.5.9\n')
    # The executor dynamically imports the service from the project root.
    pm = root / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2'
    pm.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PM / 'clearup_type2_service.py', pm / 'clearup_type2_service.py')
    shutil.copy2(PM / 'clearup_chat_service.py', pm / 'clearup_chat_service.py')
    app = root / 'App/slimmemeterportal_import/rootfs/app'
    shutil.copy2(APP / 'system_path_contract.py', app / 'system_path_contract.py')
    shutil.copy2(PM / 'system_path_contract.py', pm / 'system_path_contract.py')

    plans = root / 'App/tools/clearup_type2_plans'
    plans.mkdir(parents=True, exist_ok=True)
    for p in (TOOLS / 'clearup_type2_plans').glob('ClearUp_*.json'):
        shutil.copy2(p, plans / p.name)
    shutil.copy2(TOOLS / 'clearup_type2_path_contract.json', root / 'App/tools/clearup_type2_path_contract.json')

    _write(root / 'Inbox/release_controller/current.json', json.dumps({'status':'COMPLETE','phase':'COMPLETE'}))
    # All four mailboxes are deliberately non-empty.  This catches JSON
    # tuple/list round-trip defects and proves cleanup leaves release transport alone.
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'):
        _write(root / rel / 'KEEP.bin', f'{rel}:do-not-touch\n')


def request(root: Path, cid: str, op: str, approval: bool = False) -> dict:
    plan = type2._load_plan(root, cid)
    return {
        'schema':'energie_clearup_type2_request_v1',
        'request_id': os.urandom(16).hex(),
        'operation':op,
        'clearup_id':cid,
        'release_version':'32.5.9',
        'expires_at':'2099-01-01T00:00:00+00:00',
        'plan_sha256':plan['plan_sha256'],
        'explicit_user_approval':approval,
        'mailbox_snapshot_before':type2._snapshot_release_dirs(root),
    }


def seed_batch(root: Path, cid: str) -> dict:
    seed_common(root)
    plan = type2._load_plan(root, cid)
    for i, item in enumerate(plan['items']):
        src = root / item['source']
        if _is_file_source(item['source']):
            _write(src, f'{cid}:{i}:baseline\n')
        else:
            _write(src / 'state.json', json.dumps({'clearup':cid,'item':i,'generation':1}) + '\n')
            _write(src / 'nested' / 'payload.txt', f'{cid}:{i}:payload\n')
    return plan


def emit_runtime_proofs(root: Path, plan: dict) -> None:
    # Simulate the real long-lived writer after path activation.  The test uses
    # the same destination/proof paths declared by the production plan.
    for item in plan['items']:
        for rel in item.get('runtime_proof_paths') or []:
            p = root / item['destination'] / rel
            _write(p, json.dumps({'runtime':'fresh','ts':time.time()}) + '\n')
            now = time.time() + 0.2
            os.utime(p, (now, now))


def assert_mailboxes_unchanged(root: Path, before: dict) -> None:
    assert type2._snapshot_release_dirs(root) == before


@pytest.mark.parametrize('cid', [f'ClearUp_{n:03d}' for n in range(2,13)])
def test_every_concrete_type2_batch_executes_prepare_migrate_validate_finalize_restore(tmp_path, monkeypatch, cid):
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS','0.05')
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_PROOF_TIMEOUT_SECONDS','0.3')
    plan = seed_batch(tmp_path, cid)
    mod = load_executor()
    mailbox_before = type2._snapshot_release_dirs(tmp_path)

    _, prepared = mod.execute_type2(tmp_path, request(tmp_path,cid,'type2_prepare'))
    assert prepared['phase'] == 'PREPARED'
    assert prepared['deletion_performed'] is False
    assert (tmp_path / f'Data/03_Systeem/Projectmanager/ClearUp/Exports/{cid}_Type2_recovery.zip').is_file()
    assert_mailboxes_unchanged(tmp_path, mailbox_before)

    _, migrated = mod.execute_type2(tmp_path, request(tmp_path,cid,'type2_migrate',True))
    assert migrated['phase'] == 'MIGRATED_PENDING_VALIDATION'
    assert migrated['source_preserved'] is True
    emit_runtime_proofs(tmp_path, plan)
    assert_mailboxes_unchanged(tmp_path, mailbox_before)

    proof = type2.validate_type2(tmp_path, clearup_id=cid, source='mcp_remote')
    assert proof['status'] == 'GREEN', proof
    assert not proof['failures']

    # Destination is the active location and is allowed to keep changing after validation.
    first = plan['items'][0]
    dst = tmp_path / first['destination']
    if dst.is_dir():
        _write(dst / 'post_validation_writer_event.txt', 'new writer activity\n')
    else:
        dst.write_text(dst.read_text(encoding='utf-8') + 'new writer activity\n', encoding='utf-8')

    _, done = mod.execute_type2(tmp_path, request(tmp_path,cid,'type2_finalize',True))
    assert done['phase'] == 'COMPLETE'
    assert done['delete_performed'] is True
    assert all(not (tmp_path / item['source']).exists() for item in plan['items'])
    assert all((tmp_path / item['destination']).exists() for item in plan['items'])
    assert_mailboxes_unchanged(tmp_path, mailbox_before)

    _, restored = mod.execute_type2(tmp_path, request(tmp_path,cid,'type2_restore',True))
    assert restored['phase'] == 'RESTORED'
    assert all((tmp_path / item['source']).exists() for item in plan['items'])
    assert all((tmp_path / item['destination']).exists() for item in plan['items'])
    assert_mailboxes_unchanged(tmp_path, mailbox_before)


def test_type2_accepts_live_source_change_after_recovery_prepare_and_copies_cutover_state(tmp_path, monkeypatch):
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS','0.05')
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_PROOF_TIMEOUT_SECONDS','0.2')
    # Use a simple external plan with no runtime proof requirement.
    seed_common(tmp_path)
    src = tmp_path/'Inbox/runtime_old'; _write(src/'state.json','v1\n')
    contract=tmp_path/'App/contract.txt'; _write(contract,'Data/03_Systeem/Projectmanager/Runtime/runtime_new\n')
    plans=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Plans'; plans.mkdir(parents=True)
    plan={'schema':'energie_clearup_type2_plan_v1','classification':'TYPE2','clearup_id':'ClearUp_099','status':'READY','minimum_release':'32.5.7',
          'items':[{'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','path_key':'',
                    'reason':'mutable runtime','contract_checks':[{'path':'App/contract.txt','must_contain':['Runtime/runtime_new'],'must_not_contain':['Inbox/runtime_old']}]}]}
    (plans/'ClearUp_099.json').write_text(json.dumps(plan))
    mod=load_executor()
    mod.execute_type2(tmp_path,request(tmp_path,'ClearUp_099','type2_prepare'))
    _write(src/'state.json','v2-after-prepare\n')
    mod.execute_type2(tmp_path,request(tmp_path,'ClearUp_099','type2_migrate',True))
    assert (tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new/state.json').read_text() == 'v2-after-prepare\n'
    proof=type2.validate_type2(tmp_path,clearup_id='ClearUp_099',source='mcp_remote')
    assert proof['status']=='GREEN', proof


def test_type2_validation_blocks_if_old_source_keeps_mutating_after_activation(tmp_path, monkeypatch):
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS','0.15')
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_PROOF_TIMEOUT_SECONDS','0.2')
    seed_common(tmp_path)
    src=tmp_path/'Inbox/runtime_old'; _write(src/'state.json','v1\n')
    _write(tmp_path/'App/contract.txt','Data/03_Systeem/Projectmanager/Runtime/runtime_new\n')
    plans=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Plans'; plans.mkdir(parents=True)
    plan={'schema':'energie_clearup_type2_plan_v1','classification':'TYPE2','clearup_id':'ClearUp_098','status':'READY','minimum_release':'32.5.7',
          'items':[{'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','path_key':'',
                    'reason':'mutable runtime','contract_checks':[{'path':'App/contract.txt','must_contain':['Runtime/runtime_new'],'must_not_contain':['Inbox/runtime_old']}]}]}
    (plans/'ClearUp_098.json').write_text(json.dumps(plan))
    mod=load_executor(); mod.execute_type2(tmp_path,request(tmp_path,'ClearUp_098','type2_prepare')); mod.execute_type2(tmp_path,request(tmp_path,'ClearUp_098','type2_migrate',True))

    def mutate():
        time.sleep(0.05); _write(src/'state.json','stale-writer\n')
    th=threading.Thread(target=mutate); th.start()
    proof=type2.validate_type2(tmp_path,clearup_id='ClearUp_098',source='mcp_remote'); th.join()
    assert proof['status']=='RED'
    assert any(x.startswith('old_source_still_mutating:') for x in proof['failures'])
    with pytest.raises(Exception):
        mod.execute_type2(tmp_path,request(tmp_path,'ClearUp_098','type2_finalize',True))
    assert src.exists()


def test_type2_sideband_result_is_outside_clearup_003_logs_source():
    assert type2.WATCHER_RESULT_REL.as_posix() == 'Data/03_Systeem/Projectmanager/ClearUp/Runtime/project_clearup_move_result.json'
    bridge=(TOOLS/'sideband_bridge.py').read_text(encoding='utf-8')
    assert 'Data/03_Systeem/Projectmanager/ClearUp/Runtime/project_clearup_move_result.json' in bridge
    assert 'Never mirror a Type2 result back into Inbox/logs' in bridge


def test_type1_mailbox_snapshot_is_json_roundtrip_safe_and_covers_all_four(tmp_path):
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'):
        _write(tmp_path/rel/'KEEP.bin', rel+'\n')
    snap=type1._snapshot_release_dirs(tmp_path)
    assert set(snap)=={'Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'}
    assert json.loads(json.dumps(snap)) == snap


def test_type2_mailbox_snapshot_is_json_roundtrip_safe_and_covers_all_four(tmp_path):
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'):
        _write(tmp_path/rel/'KEEP.bin', rel+'\n')
    snap=type2._snapshot_release_dirs(tmp_path)
    assert set(snap)=={'Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'}
    assert json.loads(json.dumps(snap)) == snap


def _sideband_worker(root: Path, stop: threading.Event):
    import sideband_bridge
    while not stop.is_set():
        try:
            sideband_bridge.process_once(root)
        except Exception:
            # The service side will read the structured result/error; keep the
            # worker alive so a later operation can still run.
            pass
        time.sleep(0.01)


def test_type1_real_commandprocessor_to_sideband_to_privileged_delete(tmp_path, monkeypatch):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from task_engine import TaskStore
    from command_processor import CommandProcessor

    seed_common(tmp_path)
    # Type1 live candidates + exact recovery staging.
    for rel in type1.ROOTS:
        q=tmp_path/rel
        if rel.endswith('1812Z'):
            q.parent.mkdir(parents=True,exist_ok=True); q.write_bytes(b'')
        else:
            _write(q/'payload.txt',rel+'\n')
    stage=tmp_path/type1.STAGING_REL; stage.mkdir(parents=True,exist_ok=True)
    for rel in type1.ROOTS:
        src=tmp_path/rel; dst=stage/src.name
        if src.is_dir(): shutil.copytree(src,dst)
        else: shutil.copy2(src,dst)
    mailbox_before=type1._snapshot_release_dirs(tmp_path)
    monkeypatch.setattr(type1,'WATCHER_TIMEOUT_SECONDS',3.0)

    class _Mode:
        def set(self, mode, *, reason='', source=''): return {'mode':mode}
    commands=CommandStore(tmp_path/'runtime/cmd.json'); decisions=DecisionQueue(tmp_path/'runtime/dec.json'); tasks=TaskStore(tmp_path/'runtime/tasks.json')
    commands.enqueue({'intent':'admin_update','classification_hint':'clearup_apply','source':'mcp_remote','text':'akkoord','title':'type1 e2e'})
    processor=CommandProcessor(commands,decisions,_Mode(),tasks,project_root=tmp_path)
    stop=threading.Event(); th=threading.Thread(target=_sideband_worker,args=(tmp_path,stop),daemon=True); th.start()
    try:
        finished=processor.process_next()
    finally:
        stop.set(); th.join(timeout=1)
    assert finished['status']=='DONE', finished
    assert finished['result']['action']=='clearup_apply'
    assert finished['result']['delete_performed'] is True
    assert all(not (tmp_path/rel).exists() for rel in type1.ROOTS)
    assert type1._snapshot_release_dirs(tmp_path)==mailbox_before


def test_type2_real_commandprocessor_full_route_prepare_migrate_validate_finalize_restore(tmp_path, monkeypatch):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from task_engine import TaskStore
    from command_processor import CommandProcessor

    seed_common(tmp_path)
    src=tmp_path/'Inbox/runtime_old'; _write(src/'state.json','v1\n')
    _write(tmp_path/'App/contract.txt','Data/03_Systeem/Projectmanager/Runtime/runtime_new\n')
    plans=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/Plans'; plans.mkdir(parents=True)
    plan={'schema':'energie_clearup_type2_plan_v1','classification':'TYPE2','clearup_id':'ClearUp_097','status':'READY','minimum_release':'32.5.7',
          'items':[{'source':'Inbox/runtime_old','destination':'Data/03_Systeem/Projectmanager/Runtime/runtime_new','path_key':'',
                    'reason':'command route e2e','contract_checks':[{'path':'App/contract.txt','must_contain':['Runtime/runtime_new'],'must_not_contain':['Inbox/runtime_old']}]}]}
    (plans/'ClearUp_097.json').write_text(json.dumps(plan))
    mailbox_before=type2._snapshot_release_dirs(tmp_path)
    monkeypatch.setattr(type2,'WATCHER_TIMEOUT_SECONDS',3.0)
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS','0.05')
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_PROOF_TIMEOUT_SECONDS','0.2')

    class _Mode:
        def set(self, mode, *, reason='', source=''): return {'mode':mode}
    commands=CommandStore(tmp_path/'runtime/cmd.json'); decisions=DecisionQueue(tmp_path/'runtime/dec.json'); tasks=TaskStore(tmp_path/'runtime/tasks.json')
    processor=CommandProcessor(commands,decisions,_Mode(),tasks,project_root=tmp_path)
    stop=threading.Event(); th=threading.Thread(target=_sideband_worker,args=(tmp_path,stop),daemon=True); th.start()
    try:
        def run(hint,text=''):
            commands.enqueue({'intent':'admin_update','classification_hint':hint,'artifact_path':'ClearUp_097','source':'mcp_remote','text':text,'title':hint})
            out=processor.process_next(); assert out['status']=='DONE', out; return out
        assert run('clearup_type2_prepare')['result']['phase']=='PREPARED'
        # Prove prepare is a recovery snapshot, not a frozen live-source gate.
        _write(src/'state.json','v2-after-prepare\n')
        assert run('clearup_type2_migrate','akkoord')['result']['phase']=='MIGRATED_PENDING_VALIDATION'
        assert (tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new/state.json').read_text()=='v2-after-prepare\n'
        assert run('clearup_type2_validate')['result']['status']=='GREEN'
        _write(tmp_path/'Data/03_Systeem/Projectmanager/Runtime/runtime_new/new-writer.txt','writer continues\n')
        assert run('clearup_type2_finalize','akkoord')['result']['phase']=='COMPLETE'
        assert not src.exists()
        assert run('clearup_type2_restore','akkoord')['result']['phase']=='RESTORED'
        assert src.exists()
    finally:
        stop.set(); th.join(timeout=1)
    assert type2._snapshot_release_dirs(tmp_path)==mailbox_before


def test_native_mcp_forwarding_functionally_preserves_clearup_routing_fields(tmp_path):
    import importlib.util
    spec=importlib.util.spec_from_file_location('nmcp_hotfix_e2e_3259',TOOLS/'native_mcp_runtime_contract_hotfix.py')
    hotfix=importlib.util.module_from_spec(spec); spec.loader.exec_module(hotfix)
    project=tmp_path/'project'; (project/'App').mkdir(parents=True); _write(project/'App/VERSIE.txt','32.5.9\n')
    native=project/'Infra/Docker/native-mcp'; native.mkdir(parents=True)
    _write(native/'server.py','from registry import mcp\nimport tools_projectmanager  # noqa: F401\nif __name__ == "__main__":\n    pass\n')
    # Minimal legacy bridge with the exact patch anchors and a real immutable
    # envelope writer.  After hotfix, executing the function must write all
    # ClearUp routing fields, not merely accept them in its signature.
    old='''from pathlib import Path\nimport json, os\nfrom uuid import uuid4\nCOMMAND_INGRESS_ROOT = Path(os.environ.get("PM_COMMAND_INGRESS_ROOT", "."))\ndef _write_command(payload):\n    ingress_id=uuid4().hex\n    envelope={"schema":"energie_pmv2_command_ingress_v1","id":ingress_id,"command":payload}\n    COMMAND_INGRESS_ROOT.mkdir(parents=True,exist_ok=True)\n    (COMMAND_INGRESS_ROOT/f"{ingress_id}.json").write_text(json.dumps(envelope))\n    return {"ingress_id":ingress_id}\ndef projectmanager_submit_command(intent: str, text: str='', title: str='', goal: str='', steps_total: int=1, priority: int=2, next_action: str='', artifact_path: str='', artifact_sha256: str='', release_version: str='', verification_report: str='', source_channel: str='', source_ref: str='', occurred_at: str='', classification_hint: str=''):\n    payload = {\n        'intent': intent, 'text': text, 'title': title, 'goal': goal,\n        'steps_total': steps_total, 'priority': priority, 'next_action': next_action,\n    }\n    if intent == 'conversation_intake':\n        payload.update({'source_channel': source_channel, 'source_ref': source_ref, 'occurred_at': occurred_at, 'classification_hint': classification_hint})\n    if intent == 'production_deploy':\n        payload.update({'artifact_path': artifact_path, 'artifact_sha256': artifact_sha256, 'release_version': release_version, 'verification_report': verification_report})\n    return _write_command(payload)\n\n# Remote decision resolution, direct deploy/purchase/payment and arbitrary\n# RuntimeV2 writes are deliberately absent. Protected approval stays local HA.\n'''
    _write(native/'tools_projectmanager.py',old)
    result=hotfix.apply(project); assert result['status']=='GREEN'
    patched=(native/'tools_projectmanager.py').read_text(encoding='utf-8')
    # Isolate the submit bridge from the optional approval block/decorators; the
    # function itself is what writes immutable CommandIngress.
    start=patched.index('def projectmanager_submit_command(')
    end=patched.index('\n\n# PM_APPROVAL_TOOL_VERSION',start)
    prefix=patched[:start]
    # legacy source has no external mcp imports, so prefix is executable.
    ns={}; old_env=os.environ.get('PM_COMMAND_INGRESS_ROOT'); ingress=tmp_path/'ingress'
    os.environ['PM_COMMAND_INGRESS_ROOT']=str(ingress)
    try:
        exec(prefix+patched[start:end],ns)
        out=ns['projectmanager_submit_command'](
            'admin_update', text='akkoord', classification_hint='clearup_type2_prepare',
            artifact_path='ClearUp_002', release_version='32.5.9',
            source_channel='chatgpt', source_ref='e2e-clearup-route')
    finally:
        if old_env is None: os.environ.pop('PM_COMMAND_INGRESS_ROOT',None)
        else: os.environ['PM_COMMAND_INGRESS_ROOT']=old_env
    env=json.loads((ingress/f"{out['ingress_id']}.json").read_text())
    cmd=env['command']
    assert cmd['classification_hint']=='clearup_type2_prepare'
    assert cmd['artifact_path']=='ClearUp_002'
    assert cmd['release_version']=='32.5.9'
    assert cmd['source_channel']=='chatgpt'
    assert cmd['source_ref']=='e2e-clearup-route'
