import json, os, sys, hashlib
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import' / 'rootfs' / 'app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM)); sys.path.insert(0, str(APP))


def _root(tmp_path, release='32.4.54'):
    root=tmp_path/'energy'; (root/'App').mkdir(parents=True); (root/'Inbox/operating_mode').mkdir(parents=True)
    (root/'Inbox/projectmanager_v2/RuntimeV2').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text(release+'\n')
    return root


def _j(path, data):
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(data))


def test_legacy_bootstrap_requires_exact_hold_and_atomic(tmp_path):
    from release_transition import ReleaseTransitionCoordinator, TransitionBlocked
    root=_root(tmp_path)
    _j(root/'Inbox/operating_mode/release_validation_hold.json', {'active':True,'release_version':'32.4.54','activated_reason':'release_install','artifact_sha256':'abc'})
    _j(root/'Inbox/atomic_app_swap_state.json', {'state':'LIVE_ACCEPTANCE','from_version':'32.4.53','to_version':'32.4.54','artifact_sha256':'abc'})
    c=ReleaseTransitionCoordinator(root)
    s=c.bootstrap_legacy_if_needed()
    assert s['bootstrap_origin']=='legacy_pre_transition_fence_v1'
    assert s['phase']=='APP_PROMOTED' and s['revision']==1 and s['generation_id']
    root2=_root(tmp_path/'bad')
    _j(root2/'Inbox/operating_mode/release_validation_hold.json', {'active':True,'release_version':'32.4.53','activated_reason':'release_install'})
    _j(root2/'Inbox/atomic_app_swap_state.json', {'state':'LIVE_ACCEPTANCE','from_version':'32.4.53','to_version':'32.4.54'})
    with pytest.raises(TransitionBlocked): ReleaseTransitionCoordinator(root2).bootstrap_legacy_if_needed()


def test_revision_generation_and_result_fencing(tmp_path):
    from release_transition import ReleaseTransitionCoordinator, StaleRevision, InvalidTransitionResult
    root=_root(tmp_path); c=ReleaseTransitionCoordinator(root)
    s=c.create_prepared('32.4.53','32.4.54',previous_base_mode='DEVELOPMENT')
    with pytest.raises(StaleRevision): c.advance(expected_revision=s['revision']+1, expected_generation=s['generation_id'], phase='APP_PROMOTED')
    s=c.advance(expected_revision=s['revision'], expected_generation=s['generation_id'], phase='APP_PROMOTED')
    ticket=c.issue_executor_ticket('native_mcp_reload', expected_revision=s['revision'], expected_generation=s['generation_id'])
    with pytest.raises(InvalidTransitionResult): c.accept_executor_result({**ticket,'generation_id':'old','status':'GREEN'})
    s2=c.accept_executor_result({**ticket,'status':'GREEN','side_effect_state':'PROVEN'})
    assert s2['phase_status']=='GREEN'


def test_unknown_post_crash_side_effect_blocks_not_retries(tmp_path):
    from release_transition import ReleaseTransitionCoordinator
    root=_root(tmp_path); c=ReleaseTransitionCoordinator(root)
    s=c.create_prepared('32.4.53','32.4.54',previous_base_mode='DEVELOPMENT')
    s=c.advance(expected_revision=s['revision'], expected_generation=s['generation_id'], phase='APP_PROMOTED')
    ticket=c.issue_executor_ticket('project_cr', expected_revision=s['revision'], expected_generation=s['generation_id'])
    blocked=c.recover_waiting_result(ticket['request_id'], readback={'state':'UNKNOWN'})
    assert blocked['lifecycle_state']=='BLOCKED'
    assert blocked['blocker']=='executor_side_effect_unknown'
    assert blocked['attempts'][ticket['request_id']]['reissue_allowed'] is False


def test_ownership_hash_invalidates_legacy_classification_and_global_text_survives(tmp_path):
    from release_ownership import LegacyOwnershipIndex
    root=_root(tmp_path); idx=LegacyOwnershipIndex(root)
    record={'id':'a','title':'32.4.52 tijdelijke maintenance','goal':'release closure'}
    entry=idx.classify('tasks',record,current_release='32.4.54')
    assert entry['scope']=='RELEASE' and entry['release_owner']=='32.4.52'
    assert idx.resolve('tasks',record)['ownership_status']=='MIGRATED'
    changed={**record,'goal':'ordinary global note'}
    assert idx.resolve('tasks',changed)['ownership_status']=='LEGACY_AMBIGUOUS'
    global_record={'id':'g','scope':'GLOBAL','release_owner':None,'lifecycle_class':'USER','created_generation':'x','title':'remember 32.4.52'}
    assert idx.ownership(global_record,current_release='32.4.54')['scope']=='GLOBAL'


def test_series_324_is_projection_only_and_orchestrator_does_not_queue_it():
    series=(PM/'series_324_live_closure.py').read_text()
    orch=(PM/'orchestrator.py').read_text()
    assert 'Compatibility projection only' in series
    assert '_queue_324_action_once' not in orch
    assert "closure['automation']" not in orch


def test_handover_prefers_transition_truth(tmp_path):
    from handover_snapshot import HandoverSnapshotService
    root=_root(tmp_path); rt=root/'Inbox/projectmanager_v2/RuntimeV2'
    _j(rt/'status/current.json', {'schema':'energie_projectmanager_status_v2','mode':'MAINTENANCE','release':{'version':'32.4.54'},'progress':{},'release_chain':{},'active_task':{'title':'32.4.52 temporary','next_action':'old'}})
    _j(rt/'release_transition/current.json', {'schema_version':1,'generation_id':'gen54','revision':7,'from_release':'32.4.53','to_release':'32.4.54','lifecycle_state':'ACTIVE','phase':'NATIVE_RUNTIME_CURRENT','phase_status':'WAITING_RESULT','blocker':'','next_action':'wait native readback'})
    (root/'App/slimmemeterportal_import/rootfs/app/projectmanager_v2').mkdir(parents=True)
    (root/'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt').write_text('2.0.0-rc41')
    snap=HandoverSnapshotService(rt,project_root=root).create(source_channel='chatgpt',trigger_text='verder')
    assert snap['release_transition']['generation_id']=='gen54'
    assert snap['next_step']=='wait native readback'
    assert snap['release_transition']['phase']=='NATIVE_RUNTIME_CURRENT'


def test_startup_timing_module_uses_monotonic_and_records_required_phases(tmp_path, monkeypatch):
    from startup_timing import StartupTiming
    root=_root(tmp_path); t=StartupTiming(root)
    for name in ('PROCESS_STARTED','INGRESS_READY','FIRST_STATUS_READY','PM_CURRENT','BACKGROUND_AUDIT_COMPLETE'): t.mark(name)
    data=json.loads((root/'Inbox/projectmanager_v2/RuntimeV2/startup_timing/current.json').read_text())
    assert [x['phase'] for x in data['phases']]==['PROCESS_STARTED','INGRESS_READY','FIRST_STATUS_READY','PM_CURRENT','BACKGROUND_AUDIT_COMPLETE']
    assert all('elapsed_monotonic_seconds' in x for x in data['phases'])

def test_new_installer_prepares_transition_before_swap():
    src=(Path(__file__).resolve().parents[1]/'tools/release_installer.sh').read_text()
    prep=src.index('release_transition_prepare.py')
    swap=src.index('prepare-and-swap', prep)
    assert prep < swap


def test_watcher_bootstraps_transition_before_maintenance_side_effects():
    src=(Path(__file__).resolve().parents[1]/'tools/release_watcher.sh').read_text()
    boot=src.index('release_transition_bootstrap.py')
    clear=src.index('CLEARUP-root startup-preflight')
    assert boot < clear


def test_hold_worker_cannot_release_active_transition(tmp_path):
    import operating_mode_auto_release as mod
    root=_root(tmp_path)
    _j(root/'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json', {'generation_id':'g','to_release':'32.4.54','lifecycle_state':'ACTIVE','phase':'HOLD_VALID'})
    class App: pass
    result=mod.automatic_release_hold_once(App(),root,'32.4.54')
    assert result['status']=='coordinator_owned'


def test_post_release_mode_helper_refuses_out_of_band_mode_mutation_during_transition(tmp_path):
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
    from post_release_mode_transition import apply
    root=_root(tmp_path)
    _j(root/'Inbox/operating_mode/post_release_maintenance_required.json', {'schema':'energie_post_release_maintenance_v1','release_version':'32.4.54','status':'REQUIRED'})
    _j(root/'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json', {'generation_id':'g','to_release':'32.4.54','lifecycle_state':'ACTIVE','phase':'PM_CURRENT'})
    result=apply(root)
    assert result['status']=='COORDINATOR_OWNED' and result['changed'] is False

def test_new_tasks_have_explicit_global_ownership(tmp_path):
    from task_engine import TaskStore
    t=TaskStore(tmp_path/'tasks.json').start('ordinary','ordinary user work',mode='USER',steps_total=1)
    assert t['scope']=='GLOBAL' and t['release_owner'] is None
    assert t['lifecycle_class']=='USER' and t['created_generation']


def test_legacy_release_task_migrates_and_supersedes_without_touching_global(tmp_path):
    from task_engine import TaskStore
    from release_ownership import migrate_legacy_tasks
    store=TaskStore(tmp_path/'tasks.json')
    old=store.start('32.4.52 tijdelijke maintenance','release closure',mode='MAINTENANCE',steps_total=1)
    # emulate pre-32.4.54 record lacking machine ownership
    data=json.loads((tmp_path/'tasks.json').read_text()); item=data['tasks'][0]
    for key in ('scope','release_owner','lifecycle_class','created_generation'): item.pop(key,None)
    (tmp_path/'tasks.json').write_text(json.dumps(data))
    result=migrate_legacy_tasks(store, project_root=tmp_path, current_release='32.4.54', evidence_ref='App/VERSIE.txt')
    assert result['superseded']==1
    assert store.get(old['id'])['status']=='SUPERSEDED'

def test_transition_planner_never_skips_closure_phases():
    from release_transition_worker import plan_transition_step
    base={'generation_id':'g','to_release':'32.4.54','lifecycle_state':'ACTIVE','phase':'APP_PROMOTED','phase_status':'GREEN'}
    facts={'pm_green':False,'native_green':False,'atomic_committed':False,'project_cr_green':False,'nas_cr_green':False,'clearup_green':False,'hygiene_green':False,'development_restored':False}
    assert plan_transition_step(base,facts)['action']=='RECONCILE_OLD_STATE'
    base['phase']='PM_CURRENT'; assert plan_transition_step(base,facts)['action']=='WAIT_PM_CURRENT'
    facts['pm_green']=True; assert plan_transition_step(base,facts)['action']=='ADVANCE_NATIVE_RUNTIME_CURRENT'
    base['phase']='NATIVE_RUNTIME_CURRENT'; assert plan_transition_step(base,facts)['action']=='QUEUE_NATIVE_MCP_RELOAD'
    facts['native_green']=True; assert plan_transition_step(base,facts)['action']=='ADVANCE_HOLD_VALID'
    base['phase']='HOLD_VALID'; assert plan_transition_step(base,facts)['action']=='COMMIT_ATOMIC_ACCEPTANCE'
    facts['atomic_committed']=True; assert plan_transition_step(base,facts)['action']=='ADVANCE_ATOMIC_ACCEPTANCE_COMMITTED'
    base['phase']='ATOMIC_ACCEPTANCE_COMMITTED'; assert plan_transition_step(base,facts)['action']=='ADVANCE_PROJECT_CR'
    base['phase']='PROJECT_CR'; assert plan_transition_step(base,facts)['action']=='QUEUE_PROJECT_CR'
    facts['project_cr_green']=True; assert plan_transition_step(base,facts)['action']=='ADVANCE_NAS_CR'
    base['phase']='NAS_CR'; assert plan_transition_step(base,facts)['action']=='QUEUE_NAS_CR'
    facts['nas_cr_green']=True; assert plan_transition_step(base,facts)['action']=='ADVANCE_CLEARUP'
    base['phase']='CLEARUP'; assert plan_transition_step(base,facts)['action']=='WAIT_CLEARUP'
    facts['clearup_green']=True; assert plan_transition_step(base,facts)['action']=='ADVANCE_HYGIENE'
    base['phase']='HYGIENE'; assert plan_transition_step(base,facts)['action']=='WAIT_HYGIENE'
    facts['hygiene_green']=True; assert plan_transition_step(base,facts)['action']=='ADVANCE_LIVE_PROVEN'
    base['phase']='LIVE_PROVEN'; assert plan_transition_step(base,facts)['action']=='RESTORE_DEVELOPMENT'
    facts['development_restored']=True; assert plan_transition_step(base,facts)['action']=='RESTORE_DEVELOPMENT'
    base['phase']='RESTORE_DEVELOPMENT'; assert plan_transition_step(base,facts)['action']=='COMPLETE'

def test_mode_entry_bootstraps_transition_before_hold_and_workers():
    src=(APP/'mode_entrypoint.py').read_text()
    boot=src.index('bootstrap_legacy_if_needed()')
    hold=src.index('ensure_release_hold_state(',boot)
    workers=src.index('_supervise_background_workers(',boot)
    assert boot < hold < workers
    assert 'release_transition_daemon' in src


def test_command_processor_requires_transition_ticket_for_release_side_effects(tmp_path):
    from command_store import CommandStore
    from command_processor import CommandProcessor
    # static contract is sufficient here: guard runs before side-effect branches.
    src=(PM/'command_processor.py').read_text()
    assert '_guard_transition_ticket' in src
    assert src.index('_guard_transition_ticket') < src.index("elif action == 'project_cr_create':")

def test_protected_executor_rejects_stale_approved_restart_during_transition():
    src=(PM/'protected_action_executor.py').read_text()
    assert '_validate_transition_command' in src
    assert src.index('_validate_transition_command(command') < src.index("if action.get('action') == 'production_deploy':")

def test_transition_coordinator_uses_permanent_flock_and_never_unlinks_lock():
    src=(PM/'release_transition.py').read_text()
    assert 'fcntl.LOCK_EX | fcntl.LOCK_NB' in src
    assert '.release-transition.operation.lock' in src
    lock_section=src[src.index('def _lease'):src.index('def load')]
    assert '.unlink(' not in lock_section and 'os.replace' not in lock_section


def test_failed_transition_executor_blocks_instead_of_reissue(tmp_path):
    from release_transition_worker import ReleaseTransitionWorker
    root=_root(tmp_path)
    _j(root/'Inbox/operating_mode/release_validation_hold.json', {'active':True,'release_version':'32.4.54','activated_reason':'release_install'})
    _j(root/'Inbox/atomic_app_swap_state.json', {'state':'LIVE_ACCEPTANCE','from_version':'32.4.53','to_version':'32.4.54'})
    worker=ReleaseTransitionWorker(root, object())
    s=worker.coord.bootstrap_legacy_if_needed()
    for phase,status in (
        ('RECONCILE_OLD_STATE','GREEN'),('PM_CURRENT','GREEN'),('NATIVE_RUNTIME_CURRENT','PENDING')
    ):
        s=worker.coord.advance(expected_revision=s['revision'],expected_generation=s['generation_id'],phase=phase,phase_status=status)
    cmd=worker._queue_once('native_mcp_reload',s)
    worker.commands.fail(cmd['id'],error='crash after request')
    current=worker.coord.load()
    worker._queue_once('native_mcp_reload',current)
    blocked=worker.coord.load()
    assert blocked['lifecycle_state']=='BLOCKED'
    assert blocked['blocker']=='executor_side_effect_unknown'
    assert len([x for x in worker.commands.all() if x.get('intent')=='native_mcp_reload'])==1

def test_public_mode_commands_are_consumed_but_blocked_during_active_transition(tmp_path):
    from operating_modes import process_mode_command, load_mode_state, save_mode_state, set_base_mode, Mode, command_path
    root=_root(tmp_path)
    save_mode_state(root, set_base_mode(load_mode_state(root), Mode.DEVELOPMENT, confirmed_by_user=True))
    _j(root/'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json', {'generation_id':'g','to_release':'32.4.54','lifecycle_state':'ACTIVE','phase':'PROJECT_CR'})
    _j(command_path(root), {'schema_version':1,'request_id':'public-1','action':'set_base','requested_mode':'USER','reason':'gui','issued_by':'gui','confirmed_by_user':True,'created_at':'2026-09-14T00:00:00+00:00'})
    state=process_mode_command(root)
    assert state.base_mode.value=='DEVELOPMENT'
    assert state.last_processed_request_id=='public-1'
    assert any('release_transition_active_normal_mutation_blocked' in x for x in state.drift)


def test_command_processor_has_general_transition_mutation_gate():
    src=(PM/'command_processor.py').read_text()
    assert '_guard_active_transition_mutation' in src
    call=src.index('self._guard_active_transition_mutation(item, action)')
    side=src.index("elif action == 'project_cr_create':")
    assert call < side


def test_startup_timing_waits_for_real_status_and_audit_files():
    src=(APP/'mode_entrypoint.py').read_text()
    assert '_observe_startup_phases' in src
    assert 'status/current.json' in src and 'self_audit/current.json' in src
    assert 'BACKGROUND_AUDIT_COMPLETE' in src and 'PM_CURRENT' in src


def test_orchestrator_no_longer_syncs_release_closure_task():
    src=(PM/'orchestrator.py').read_text()
    run=src[src.index('def _run_once'): ]
    assert 'self._sync_324_closure_task(' not in run

def test_32454_release_identity_is_consistent():
    assert (ROOT/'VERSIE.txt').read_text().strip() == '32.4.54'
    assert (PM/'VERSION.txt').read_text().strip() == '2.0.0-rc41'
    assert 'CURRENT_RELEASE = "32.4.54"' in (ROOT/'release_test_contract.py').read_text()
    assert 'CURRENT_PM_VERSION = "2.0.0-rc41"' in (ROOT/'release_test_contract.py').read_text()
    assert 'version: "32.4.54"' in (ROOT/'slimmemeterportal_import/config.yaml').read_text()
    assert 'APP_VERSION = "32.4.54"' in (APP/'main.py').read_text()
    assert 'TARGET_RELEASE_VERSION = "32.4.54"' in (APP/'mode_entrypoint.py').read_text()


def test_transition_advance_rejects_non_direct_successor(tmp_path):
    from release_transition import ReleaseTransitionCoordinator, InvalidTransitionResult
    root=_root(tmp_path); c=ReleaseTransitionCoordinator(root)
    s=c.create_prepared('32.4.53','32.4.54',previous_base_mode='DEVELOPMENT')
    with pytest.raises(InvalidTransitionResult):
        c.advance(expected_revision=s['revision'],expected_generation=s['generation_id'],phase='COMPLETE')


def test_executor_result_requires_exact_ticket_phase_owner_and_revision(tmp_path):
    from release_transition import ReleaseTransitionCoordinator, InvalidTransitionResult
    root=_root(tmp_path); c=ReleaseTransitionCoordinator(root)
    s=c.create_prepared('32.4.53','32.4.54',previous_base_mode='DEVELOPMENT')
    s=c.advance(expected_revision=s['revision'],expected_generation=s['generation_id'],phase='APP_PROMOTED')
    ticket=c.issue_executor_ticket('native_mcp_reload',expected_revision=s['revision'],expected_generation=s['generation_id'])
    current=c.load()
    assert ticket['revision']==current['revision']==current['current_ticket']['revision']
    for field,bad in (
        ('phase','PROJECT_CR'),('release_owner','32.4.99'),('revision',ticket['revision']+1)
    ):
        result={**ticket,'status':'GREEN','side_effect_state':'PROVEN',field:bad}
        with pytest.raises(InvalidTransitionResult):
            c.accept_executor_result(result)


def test_completed_generation_rolls_to_history_and_next_release_can_start(tmp_path):
    from release_transition import ReleaseTransitionCoordinator
    root=_root(tmp_path); c=ReleaseTransitionCoordinator(root)
    s=c.create_prepared('32.4.53','32.4.54',previous_base_mode='DEVELOPMENT')
    # Walk legal successors to terminal state.
    for phase in ('APP_PROMOTED','RECONCILE_OLD_STATE','PM_CURRENT','NATIVE_RUNTIME_CURRENT','HOLD_VALID',
                  'ATOMIC_ACCEPTANCE_COMMITTED','PROJECT_CR','NAS_CR','CLEARUP','HYGIENE','LIVE_PROVEN',
                  'RESTORE_DEVELOPMENT','COMPLETE'):
        s=c.advance(expected_revision=s['revision'],expected_generation=s['generation_id'],phase=phase)
    old_gen=s['generation_id']
    n=c.create_prepared('32.4.54','32.4.55',previous_base_mode='DEVELOPMENT')
    assert n['to_release']=='32.4.55' and n['generation_id']!=old_gen and n['revision']==1
    hist=c.runtime/'history'/f'{old_gen}.json'
    assert hist.is_file()
    assert json.loads(hist.read_text())['lifecycle_state']=='COMPLETE'


def test_dangling_symlink_lock_fails_closed_without_creating_target(tmp_path):
    from release_transition import ReleaseTransitionCoordinator, TransitionBlocked
    root=_root(tmp_path)
    lock=root/'Inbox/.release-transition.operation.lock'
    target=root/'outside-lock-target'
    lock.symlink_to(target)
    with pytest.raises(TransitionBlocked):
        ReleaseTransitionCoordinator(root)
    assert not target.exists()


def test_mode_restore_uses_ticket_and_restores_previous_base_mode(tmp_path):
    from release_transition_worker import ReleaseTransitionWorker
    from operating_modes import load_mode_state, save_mode_state, set_base_mode, Mode
    root=_root(tmp_path)
    save_mode_state(root,set_base_mode(load_mode_state(root),Mode.DEVELOPMENT,confirmed_by_user=True))
    worker=ReleaseTransitionWorker(root,object())
    s=worker.coord.create_prepared('32.4.53','32.4.54',previous_base_mode='USER')
    # Put coordinator at LIVE_PROVEN legally.
    for phase in ('APP_PROMOTED','RECONCILE_OLD_STATE','PM_CURRENT','NATIVE_RUNTIME_CURRENT','HOLD_VALID',
                  'ATOMIC_ACCEPTANCE_COMMITTED','PROJECT_CR','NAS_CR','CLEARUP','HYGIENE','LIVE_PROVEN'):
        s=worker.coord.advance(expected_revision=s['revision'],expected_generation=s['generation_id'],phase=phase)
    result=worker._restore_previous_mode(s)
    current=worker.coord.load()
    assert load_mode_state(root).base_mode.value=='USER'
    assert current['phase']=='RESTORE_DEVELOPMENT'
    assert current['phase_status']=='GREEN'
    assert current['current_ticket'] is None
    assert result['status']=='GREEN'


def test_gui_validate_release_hold_is_blocked_during_active_transition():
    src=(APP/'operating_mode_web.py').read_text()
    start=src.index('elif endpoint == "validate-release-hold"')
    end=src.index('else:\n                if live_app is None', start) + 400
    endpoint=src[start:end]
    assert '_active_release_transition' in endpoint and 'coordinator_owned' in endpoint
    assert endpoint.index('coordinator_owned') < endpoint.index('attempt_release_hold')
