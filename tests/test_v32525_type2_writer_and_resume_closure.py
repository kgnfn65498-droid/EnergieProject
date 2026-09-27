from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(TOOLS), str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import clearup_type2_service as service
import project_clearup_move_executor as executor
import sideband_bridge
from development_context_enforcement import evaluate_full_kb, build_development_context
from github_publisher_binding import binding_current, _desired_payload
from handover import cross_chat_contracts
from orchestrator import build_new_chat_preflight


def _w(path: Path, text: str = 'x\n') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _load_script(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _activation(root: Path, key: str, source: str, destination: str, clearup_id='ClearUp_003') -> None:
    p = root/'Data/03_Systeem/Projectmanager/ClearUp/PathActivation'/f'{key}.json'
    _w(p, json.dumps({
        'schema':'energie_clearup_system_path_contract_v1','active':True,'key':key,
        'source':source,'destination':destination,'clearup_id':clearup_id,'plan_sha256':'x'
    }))


def test_32525_native_mcp_hotfix_writers_resolve_canonical_logs(tmp_path, monkeypatch):
    root = tmp_path/'p'
    _w(root/'App/VERSIE.txt','32.5.25\n')
    _activation(root,'logs','Inbox/logs','Data/03_Systeem/Projectmanager/Logs/Runtime')
    old = root/'Inbox/logs'
    old.mkdir(parents=True, exist_ok=True)
    (root/'Data/03_Systeem/Projectmanager/Logs/Runtime').mkdir(parents=True, exist_ok=True)

    hotfix = _load_script('nmr_hotfix', 'tools/native_mcp_runtime_contract_hotfix.py')
    # Avoid unrelated source mutations; this assertion targets result routing.
    monkeypatch.setattr(hotfix, '_atomic_json', lambda path, value: _w(Path(path), json.dumps(value)))
    # Directly prove the production resolver used by the script selects canonical output.
    target = hotfix.project_system_path(root, hotfix.RESULT_REL.as_posix())
    assert target == root/'Data/03_Systeem/Projectmanager/Logs/Runtime/native_mcp_runtime_contract_hotfix_32.4.39.json'

    cr = _load_script('cr_hotfix', 'tools/cr_standard_native_mcp_hotfix.py')
    target2 = cr.project_system_path(root, cr.RESULT_REL)
    assert target2 == root/'Data/03_Systeem/Projectmanager/Logs/Runtime/cr_standard_native_mcp_hotfix_v32438.json'

    assert 'root / RESULT_REL' not in (ROOT/'tools/native_mcp_runtime_contract_hotfix.py').read_text(encoding='utf-8')
    assert 'result_path = root / RESULT_REL' not in (ROOT/'tools/cr_standard_native_mcp_hotfix.py').read_text(encoding='utf-8')


def _publisher_info(*, canonical: bool) -> dict:
    root='/share/CACHEDEV1_DATA/AI Projecten/EnergieProject'
    binds=[
        f'{root}/Inbox:/energy/Inbox:rw',
        f'{root}/Data/03_Systeem/Projectmanager/Private/github_publisher:/publisher-private:rw',
        f'{root}/App/tools/nas_github_publisher.sh:/usr/local/bin/nas_github_publisher.sh:ro',
    ]
    if canonical:
        binds.extend([
            f'{root}/Data/03_Systeem:/energy/Data/03_Systeem:rw',
            f'{root}/App/tools/system_path_contract.sh:/energy/App/tools/system_path_contract.sh:ro',
        ])
    return {
        'Id':'abc','Name':'/energie-github-publisher',
        'Config':{'Image':'alpine/git:2.47.2'},
        'HostConfig':{'Binds':binds,'NetworkMode':'bridge'},
        'State':{'Running':True},
    }


def test_32525_github_publisher_binding_requires_and_builds_canonical_type2_mounts():
    legacy=_publisher_info(canonical=False)
    assert binding_current(legacy) is False
    payload=_desired_payload(legacy)
    binds=payload['HostConfig']['Binds']
    assert any('/Data/03_Systeem:/energy/Data/03_Systeem:rw' in x for x in binds)
    assert any('/App/tools/system_path_contract.sh:/energy/App/tools/system_path_contract.sh:ro' in x for x in binds)
    assert binding_current(_publisher_info(canonical=True)) is True
    src=(ROOT/'tools/release_controller_service.py').read_text(encoding='utf-8')
    assert "publisher_binding_required=release_tuple >= (32,5,25)" in src
    assert 'ensure_github_publisher_binding_current(self.root)' in src


def test_32525_publisher_script_reports_remote_lookup_transport_failure_not_fake_missing_branch():
    src=(ROOT/'tools/nas_github_publisher.sh').read_text(encoding='utf-8')
    assert 'remote branch lookup failed' in src
    assert 'REMOTE_LIST="$(git ls-remote' in src
    assert ')" || fail "remote branch lookup failed"' in src


def _json(path: Path, value) -> None:
    _w(path, json.dumps(value, sort_keys=True)+'\n')


def _seed_one_finalize(root: Path, clearup_id='ClearUp_009'):
    (root/'App/tools/clearup_type2_plans').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'tools/clearup_type2_plans'/f'{clearup_id}.json', root/'App/tools/clearup_type2_plans'/f'{clearup_id}.json')
    _w(root/'App/VERSIE.txt','32.5.25\n')
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'):
        (root/rel).mkdir(parents=True, exist_ok=True)
    _json(root/'Inbox/release_controller/current.json', {'status':'COMPLETE','phase':'COMPLETE'})
    plan=service._load_plan(root,clearup_id)
    for item in plan['items']:
        src=root/item['source']; src.parent.mkdir(parents=True,exist_ok=True)
        src.write_text('old\n',encoding='utf-8')
        dst=root/item['destination']; dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_text('new\n',encoding='utf-8')
        key=str(item.get('path_key') or '').strip()
        if key:
            _json(executor._type2_activation_path(root,key),{
                'active':True,'destination':item['destination'],'source':item['source'],
                'clearup_id':clearup_id,'plan_sha256':plan['plan_sha256'],'key':key,
            })
    state={'phase':'MIGRATED_PENDING_VALIDATION','plan_sha256':plan['plan_sha256']}
    _json(root/service.STATE_ROOT_REL/f'{clearup_id}.json',state)
    # validation hashes must reflect current old sources
    checks=[]
    for item in plan['items']:
        rows=executor._tree_rows(root/item['source'],root)
        import hashlib
        h=hashlib.sha256(json.dumps(rows,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
        checks.append({'source':item['source'],'source_rows_sha256':h})
    _json(root/service.VALIDATION_ROOT_REL/f'{clearup_id}.json',{
        'status':'GREEN','plan_sha256':plan['plan_sha256'],'checks':checks,'evidence':['x']
    })
    # bypass export/gate verification in unit scope; dedicated suites cover them.
    return plan


def test_32525_finalize_post_delete_soak_detects_late_writer_reappearance(tmp_path, monkeypatch):
    root=tmp_path/'p'; plan=_seed_one_finalize(root)
    monkeypatch.setattr(executor,'_load_clearup_type2_service',lambda _root:service)
    monkeypatch.setattr(service,'_assert_external_recovery_confirmed',lambda _root:{'status':'EXTERNAL_COPY_CONFIRMED','delete_allowed':True})
    monkeypatch.setattr(service,'_verify_export',lambda *_a,**_k:{'status':'GREEN'})
    monkeypatch.setattr(service,'_contract_checks',lambda *_a,**_k:{'status':'GREEN'})
    monkeypatch.setattr(executor,'_type2_manifest',lambda *_a,**_k:{'items':plan['items']})
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_POST_DELETE_SOAK_SECONDS','0.20')
    request={
        'schema':'energie_clearup_type2_request_v1','request_id':'a'*32,'operation':'type2_finalize',
        'clearup_id':'ClearUp_009','release_version':'32.5.25','plan_sha256':plan['plan_sha256'],
        'explicit_user_approval':True,'mailbox_snapshot_before':service._snapshot_release_dirs(root),
        'expires_at':'2099-01-01T00:00:00+00:00',
    }
    source=root/plan['items'][0]['source']
    def recreate():
        deadline=time.monotonic()+2
        while time.monotonic()<deadline and source.exists(): time.sleep(0.002)
        time.sleep(0.05)
        source.parent.mkdir(parents=True,exist_ok=True); source.write_text('late-writer\n',encoding='utf-8')
    th=threading.Thread(target=recreate,daemon=True); th.start()
    try:
        executor.execute_type2(root,request)
    except RuntimeError as exc:
        assert 'reappeared after delete' in str(exc)
    else:
        raise AssertionError('late legacy writer escaped post-delete soak')
    th.join(timeout=1)



def test_32525_finalize_success_proves_source_absent_through_soak(tmp_path, monkeypatch):
    root=tmp_path/'p'; plan=_seed_one_finalize(root)
    monkeypatch.setattr(executor,'_load_clearup_type2_service',lambda _root:service)
    monkeypatch.setattr(service,'_assert_external_recovery_confirmed',lambda _root:{'status':'EXTERNAL_COPY_CONFIRMED','delete_allowed':True})
    monkeypatch.setattr(service,'_verify_export',lambda *_a,**_k:{'status':'GREEN'})
    monkeypatch.setattr(service,'_contract_checks',lambda *_a,**_k:{'status':'GREEN'})
    monkeypatch.setattr(executor,'_type2_manifest',lambda *_a,**_k:{'items':plan['items']})
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_POST_DELETE_SOAK_SECONDS','0.06')
    request={
        'schema':'energie_clearup_type2_request_v1','request_id':'b'*32,'operation':'type2_finalize',
        'clearup_id':'ClearUp_009','release_version':'32.5.25','plan_sha256':plan['plan_sha256'],
        'explicit_user_approval':True,'mailbox_snapshot_before':service._snapshot_release_dirs(root),
        'expires_at':'2099-01-01T00:00:00+00:00',
    }
    _request_id,result=executor.execute_type2(root,request)
    assert result['status']=='GREEN' and result['phase']=='COMPLETE'
    assert result['source_reappearance_proof']=='GREEN'
    assert result['post_delete_soak_seconds'] >= 0.05
    for item in plan['items']:
        assert not (root/item['source']).exists()
        assert (root/item['destination']).exists()

def test_32525_full_kb_and_cross_chat_contract_include_decisions_changelog_spock_and_verder(tmp_path):
    # Static contract must name the canonical governance sources.
    required={'decision_log','development_changelog','spock_context','ticket_issue_index','knowledgebase_inventory'}
    contract=cross_chat_contracts()['new_chat_preflight']
    assert required.issubset(set(contract['required_context']))
    assert 'verder' in contract['short_commands_supported']
    src=(PM/'self_audit.py').read_text(encoding='utf-8')
    for name in required:
        assert name in src
    context={
        'full_kb':{'status':'COMPLETE','complete':True,'checkpoint':{'path':'Data/03_Systeem/Projectmanager/ClearUp/State/CHECKPOINT.json'}},
        'truth_reconciliation':{'status':'GREEN','fail_closed':False},
        'requirements_count':36,
        'master_index':'master','active_context':'active','ledger':'ledger','ledger_current_truth':'truth',
        'decision_log':'decisions','development_changelog':'changes','spock_context':'spock',
        'ticket_issue_index':'issues','knowledgebase_inventory':'inventory',
    }
    preflight=build_new_chat_preflight({'release':{'version':'32.5.25'}},context,{'next_action':'finalize Type2'},[])
    assert preflight['ready'] is True
    assert preflight['manual_reexplanation_required'] is False
    assert preflight['resume_command']=='verder'
    assert preflight['live_release']=='32.5.25'
    assert preflight['highest_checkpoint'].endswith('CHECKPOINT.json')
    assert preflight['decision_log']=='decisions'
    assert preflight['development_changelog']=='changes'
    assert preflight['next_action']=='finalize Type2'
    bad=build_new_chat_preflight({'release':{'version':'32.5.25'}},{**context,'truth_reconciliation':{'status':'RED','fail_closed':True}},None,[])
    assert bad['ready'] is False and bad['manual_reexplanation_required'] is True


def test_32525_release_identity_pm_rc60():
    assert (ROOT/'VERSIE.txt').read_text(encoding='utf-8').strip()=='32.5.25'
    assert (PM/'VERSION.txt').read_text(encoding='utf-8').strip()=='2.0.0-rc60'
    contract=(ROOT/'release_test_contract.py').read_text(encoding='utf-8')
    assert 'CURRENT_RELEASE = "32.5.25"' in contract
    assert 'CURRENT_PM_VERSION = "2.0.0-rc60"' in contract


def _runtime_32525():
    return {
        'operating_mode': {'effective_mode': 'DEVELOPMENT', 'source': '/project/Inbox/operating_mode/operating_mode_state.json'},
        'release': {'version': '32.5.25', 'source': '/project/App/VERSIE.txt'},
        'release_chain': {'atomic_swap': {'state': 'ACCEPTED', 'source': '/project/Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json', 'raw': {'state': 'ACCEPTED', 'to_version': '32.5.25'}}},
    }


def _chat_switch_checkpoint(root: Path) -> Path:
    path = root/'Data/03_Systeem/Projectmanager/ClearUp/State/CHECKPOINT_32.5.25_CHAT_SWITCH_FINAL_20260927.json'
    _json(path, {
        'schema': 'energie_chat_switch_checkpoint_v2',
        'status': 'READY_FOR_NEW_CHAT',
        'live_release': '32.5.24',
        'target_release': '32.5.25',
        'target_kind': 'replacement_build',
        'type2': {
            'scope': 'ClearUp_002..012 durable legacy-source closure',
            'recovery': '11/11 GREEN and externally confirmed',
            'finalization_started': False,
        },
        'known_handover_gap': 'live runtime active_task is stale ClearUp_001 and must not override this checkpoint; 32.5.25 must reconcile this technically',
        'resume_instruction': "New chat: user may say 'verder'. Resume replacement 32.5.25 without repeating proven root-cause research.",
    })
    return path


def test_32525_target_reached_checkpoint_is_not_false_truth_conflict(tmp_path):
    from development_context_enforcement import current_truth_reconciliation
    root = tmp_path/'p'
    _w(root/'App/VERSIE.txt', '32.5.25\n')
    checkpoint = _chat_switch_checkpoint(root)
    # The pre-install checkpoint truth is not stale/conflicting once its exact target
    # became live; it is the handover bridge into post-live closure.
    os.utime(checkpoint, None)
    result = current_truth_reconciliation(root, {'release': {'version': '32.5.25'}})
    assert result['status'] == 'GREEN'
    assert result['fail_closed'] is False
    assert result['highest_checkpoint'].endswith('CHECKPOINT_32.5.25_CHAT_SWITCH_FINAL_20260927.json')


def test_32525_checkpoint_supersedes_stale_clearup001_and_creates_current_resume_task(tmp_path):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from handoff_queue import HandoffQueue
    from issue_store import IssueStore
    from state_reconciliation import StateReconciler
    from task_engine import TaskStore

    project = tmp_path/'project'
    _w(project/'App/VERSIE.txt', '32.5.25\n')
    checkpoint = _chat_switch_checkpoint(project)
    os.utime(checkpoint, None)
    rt = tmp_path/'runtime'
    tasks = TaskStore(rt/'tasks.json')
    decisions = DecisionQueue(rt/'decisions.json')
    commands = CommandStore(rt/'commands.json')
    handoffs = HandoffQueue(rt/'handoffs.json')
    issues = IssueStore(rt/'issues.json')
    stale = tasks.start(
        'ClearUp_001 TYPE1 recovery-export voorbereiden',
        'Maak de ClearUp_001 recovery export klaar',
        mode='MAINTENANCE', steps_total=3, priority=1,
    )
    reconciler = StateReconciler(tasks, decisions, commands, handoffs, issues, project_root=project)
    result = reconciler.reconcile(runtime=_runtime_32525(), release_validation={'active': False, 'validation_status': 'ok', '_source': '/project/release_validation.json'})
    row = next(item for item in result['items'] if item['id'] == stale['id'])
    assert row['disposition'] == 'SUPERSEDED'
    assert row['changed'] is True
    assert tasks.get(stale['id'])['status'] == 'SUPERSEDED'
    active = tasks.active()
    assert active is not None
    assert active['status'] == 'ACTIVE'
    assert active['mode'] == 'DEVELOPMENT'
    assert active['build_metadata']['release_version'] == '32.5.25'
    assert '32.5.25' in active['title']
    assert 'new_chat_verder_e2e' in active['next_action']
    assert any('CHECKPOINT_32.5.25_CHAT_SWITCH_FINAL_20260927.json' in ref for ref in active['evidence_refs'])
    # Idempotency: once the checkpoint-resume task is complete it must never be recreated.
    done_data = tasks._load()
    stored = next(item for item in done_data['tasks'] if item['id'] == active['id'])
    stored['status'] = 'DONE'
    tasks._save(done_data)
    second = reconciler.reconcile(runtime=_runtime_32525(), release_validation={'active': False, 'validation_status': 'ok', '_source': '/project/release_validation.json'})
    assert tasks.active() is None
    assert len([item for item in tasks.all() if item.get('title') == active['title']]) == 1
    assert not any(item.get('disposition') == 'RESUMED_FROM_CHECKPOINT' for item in second['items'])


def test_32525_unrelated_checkpoint_live_mismatch_remains_fail_closed(tmp_path):
    from development_context_enforcement import current_truth_reconciliation
    root = tmp_path/'p'
    _w(root/'App/VERSIE.txt', '32.5.26\n')
    _chat_switch_checkpoint(root)
    result = current_truth_reconciliation(root, {'release': {'version': '32.5.26'}})
    assert result['status'] == 'RED'
    assert result['fail_closed'] is True
    assert any(item['kind'] == 'checkpoint_live_release_conflict' for item in result['conflicts'])
