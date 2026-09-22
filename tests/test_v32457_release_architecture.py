from pathlib import Path
import hashlib
import json
import sys
import zipfile
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(PM))

from release_controller import ReleaseController, Phase, Status
from atomic_release_adapter import AtomicReleaseAdapter
import atomic_app_swap
import control_plane_bootstrap
from minimal_release_preflight import verify_candidate
from legacy_install_adoption import adopt_exact_pre57_install
from state_store import StateStore
from release_controller_service import should_reexec
from release_runtime_adapter import NativeRuntimeCoordinator
from release_controller_state import load_release_controller_state

CPTOOLS = TOOLS / "control_plane"
if str(CPTOOLS) not in sys.path:
    sys.path.insert(0, str(CPTOOLS))
_cp_spec = importlib.util.spec_from_file_location("energie_cp57_test", CPTOOLS / "control_plane.py")
assert _cp_spec is not None and _cp_spec.loader is not None
control_plane57 = importlib.util.module_from_spec(_cp_spec)
_cp_spec.loader.exec_module(control_plane57)


def _text(path):
    return Path(path).read_text(encoding="utf-8")


def _zip(path, version="32.4.57"):
    payload = {"VERSIE.txt": (version+"\n").encode(), "README.md": b"ok\n"}
    manifest = {k: hashlib.sha256(v).hexdigest() for k,v in payload.items()}
    with zipfile.ZipFile(path, "w") as z:
        for k,v in payload.items(): z.writestr(k,v)
        z.writestr("MANIFEST.sha256", "".join(f"{v}  {k}\n" for k,v in manifest.items()))
        z.writestr("SHA256SUMS.json", json.dumps({"files":[{"path":k,"sha256":v} for k,v in manifest.items()]}))


def test_32457_identity_is_consistent():
    legacy = ROOT / "tests/fixtures/legacy57"
    assert _text(legacy/"VERSIE.txt").strip() == "32.4.57"
    assert _text(legacy/"PM_VERSION.txt").strip() == "2.0.0-rc45"
    assert 'version: "32.4.57"' in _text(legacy/"config_legacy57.yaml")
    assert 'APP_VERSION = "32.4.57"' in _text(legacy/"main.py")


def test_32457_has_exact_nine_release_phases_and_separate_status():
    assert [p.value for p in Phase] == [
        "DETECTED","VERIFIED","PUBLISHING","INSTALLING","INSTALLED",
        "RUNTIME_ALIGNING","VERIFYING","ACCEPTED","COMPLETE",
    ]
    assert [s.value for s in Status] == ["ACTIVE","WAITING","BLOCKED","COMPLETE","ROLLED_BACK"]


def test_32457_watcher_is_thin_single_owner_launcher():
    watcher=_text(TOOLS/"release_watcher.sh")
    assert "release_controller_service.py" in watcher
    for forbidden in ("release_installer.sh","release_transition_bootstrap","project_cr","nas_cr","clearup","MODE_GATE"):
        assert forbidden not in watcher


def test_32457_legacy_installer_is_retired_not_second_orchestrator():
    installer=_text(TOOLS/"release_installer.sh")
    assert "retired" in installer and "release_controller_service" in installer
    assert "prepare-and-swap" not in installer
    assert "release_validation_hold" not in installer
    assert "release_transition" not in installer


def test_32457_minimal_preflight_has_no_runtime_or_maintenance_gates():
    source=_text(TOOLS/"minimal_release_preflight.py")
    for forbidden in ("release_validation_hold","operating_mode","release_transition","project_cr","nas_container","self_audit","watcher_container_contract","command_ingress"):
        assert forbidden not in source
    assert "rollback_collision" in source and "candidate_collision" in source


def test_32457_controller_service_has_no_old_orchestrator_dependencies():
    source=_text(ROOT/"tests/fixtures/legacy57/release_controller_service.py")
    for forbidden in ("release_validation_hold","release_transition_worker","project_cr","nas_cr","clearup","mode_allows"):
        assert forbidden not in source
    assert "adopt_exact_pre57_install" in source
    assert "ensure_control_plane_current" in source


def test_32457_mode_entrypoint_does_not_start_release_workers():
    source=_text(APP/"mode_entrypoint.py")
    for forbidden in ("release_transition_daemon","automatic_release_hold_worker","ensure_release_hold_state","ReleaseTransitionCoordinator"):
        assert forbidden not in source


def test_32457_mode_entrypoint_has_no_automatic_pm_supervisor_restart():
    source=_text(APP/"mode_entrypoint.py")
    assert "startup_recovery_daemon" not in source
    assert "pm-startup-recovery" not in source
    assert "/addons/self/restart" not in source


def test_32457_projectmanager_declares_controller_ownership():
    source=_text(PM/"orchestrator.py")
    assert "self.release_controller_enabled" in source
    assert "CONTROLLER_OWNED" in source
    assert "release_scoped_native_mcp_alignment_is_owned_by_release_controller" in source


def test_32457_release_recover_is_same_controller_not_rescue_service():
    source=_text(PM/"command_processor.py")
    assert "same_generation_resume_is_built_into_release_controller" in source
    assert "release_controller_active_competing_release_mutation_blocked" in source


def test_32457_handover_and_health_read_controller_state():
    handover=_text(PM/"handover_snapshot.py")
    health=_text(PM/"energy_health_collector.py")
    assert "release_controller" in handover
    assert "release_controller_state" in health
    assert "release_controller_runtime" in health
    assert "heartbeat_required=_numeric_release(version) < (32, 4, 57)" in health
    assert "runtime_heartbeat_stale_on_demand_actuator" in health


def test_32457_control_plane_release_auth_is_exactly_fenced():
    auth=_text(TOOLS/"control_plane/release_scoped_auth.py")
    for field in ("release_id","generation","release_version","artifact_sha256","expected_fingerprint"):
        assert field in auth
    assert "energie-filesystem-mcp" in auth
    assert "RUNTIME_ALIGNING" in auth


def test_32457_native_mcp_restart_attempt_is_fenced_and_reconciled_without_second_restart(tmp_path):
    expected='d'*64
    inbox=tmp_path/'Inbox'
    request_dir=inbox/'control_plane/requests';request_dir.mkdir(parents=True)
    state_dir=inbox/'release_controller';state_dir.mkdir(parents=True)
    guard_dir=inbox/'native_mcp_runtime';guard_dir.mkdir(parents=True)
    version_path=tmp_path/'App/VERSIE.txt';version_path.parent.mkdir(parents=True);version_path.write_text('32.4.57')
    runtime_evidence=tmp_path/'runtime-evidence';runtime_evidence.mkdir()
    approved=tmp_path/'approved.json';approved.write_text(json.dumps({'items':[]}))

    request={
        'schema':'energie_control_plane_release_request_v1',
        'authorization':'release_controller',
        'action':'native_mcp_reload',
        'container':'energie-filesystem-mcp',
        'request_id':'a'*32,
        'release_id':'32.4.57:test',
        'generation':'g57',
        'release_version':'32.4.57',
        'artifact_sha256':'b'*64,
        'expected_fingerprint':expected,
    }
    (request_dir/'native_mcp_reload.json').write_text(json.dumps(request))
    (state_dir/'current.json').write_text(json.dumps({
        'phase':'RUNTIME_ALIGNING','release_id':request['release_id'],'generation':request['generation'],
        'to_version':'32.4.57','artifact_sha256':request['artifact_sha256'],
    }))
    (guard_dir/'runtime_guard.json').write_text(json.dumps({
        'status':'RELOAD_REQUIRED','reload_required':True,'expected_fingerprint':expected,
    }))
    (runtime_evidence/'native_mcp_runtime_fingerprint.json').write_text(json.dumps({
        'schema':'energie_native_mcp_runtime_v3','fingerprint':'e'*64,
    }))

    class Docker:
        def __init__(self):self.restarts=0
        def ping(self):return {'ok':True}
        def inspect_container(self,name):return {'State':{'Running':True}}
        def restart_container(self,name,timeout=30):self.restarts+=1;return {'ok':True}

    docker=Docker()
    cp=control_plane57.ControlPlane(
        inbox=inbox,approved_queue=approved,version_path=version_path,
        runtime_evidence=runtime_evidence,host_project_root='/share/Energie_NAS/EnergieProject',
        docker=docker,
    )
    cp._wait_json=lambda *args,**kwargs: (_ for _ in ()).throw(RuntimeError('readback timeout'))

    first=cp.reload_native_mcp()
    assert first['status']=='RED'
    assert first['retry_allowed'] is False
    assert first['restart_performed'] is True
    assert first['side_effect_state']=='RESTART_PERFORMED_UNPROVEN'
    assert docker.restarts==1

    cp.process_once()
    assert docker.restarts==1
    still=json.loads((inbox/'control_plane/results/native_mcp_reload.json').read_text())
    assert still['status']=='RED'

    (runtime_evidence/'native_mcp_runtime_fingerprint.json').write_text(json.dumps({
        'schema':'energie_native_mcp_runtime_v3','fingerprint':expected,
    }))
    reconciled=cp.process_once()
    assert docker.restarts==1
    assert reconciled and reconciled[0]['status']=='GREEN'
    final=json.loads((inbox/'control_plane/results/native_mcp_reload.json').read_text())
    assert final['status']=='GREEN'
    assert final['side_effect_state']=='PROVEN_BY_READBACK'
    assert final['request_id']==request['request_id']


def test_32457_control_plane_source_sync_evidence_is_controller_owned_not_version_named():
    source=_text(TOOLS/'control_plane_source_sync.py')
    assert "Inbox/release_controller/control_plane_source_sync.json" in source
    assert "control_plane_source_sync_32.4.44" not in source


def test_32457_control_plane_bootstrap_restarts_only_existing_exact_service():
    source=_text(TOOLS/"control_plane_bootstrap.py")
    assert "energie-control-plane" in source
    assert "/restart?t=30" in source
    assert "/containers/create" not in source
    assert "/containers/" in source


def test_32457_ha_bootstrap_reuses_existing_publisher_rebuild_chain():
    main=_text(ROOT/"tests/fixtures/legacy57/main.py")
    delivery=_text(TOOLS/"ha_delivery_adapter.py")
    assert "ha_publication_required.json" in delivery
    assert "def publish_github_release" in main
    assert '("/addons/reload", "/addons/self/rebuild")' in main
    assert "github_publication_state.json" in main
    assert "ha_runtime/current.json" in _text(APP/"ha_runtime_marker.py")


def test_32457_ha_runtime_has_direct_version_marker():
    main=_text(APP/"main.py")
    marker=_text(APP/"ha_runtime_marker.py")
    assert "write_ha_runtime_marker" in main
    assert "Inbox/ha_runtime/current.json" in marker


def test_32457_delivery_occurs_after_atomic_acceptance_without_rollback_path():
    controller=_text(TOOLS/"release_controller.py")
    delivery=_text(TOOLS/"ha_delivery_adapter.py")
    assert "atomic_accept" in controller and "delivery" in controller
    assert controller.index("atomic_accept") < controller.index("delivery")
    assert "def rollback" not in delivery.lower()
    assert "rollback=True" not in delivery
    assert "rollback_after_activation_failure" not in delivery


def test_32457_preflight_accepts_clean_candidate_without_mode_cr_or_hold(tmp_path):
    root=tmp_path/"energy"
    (root/"App").mkdir(parents=True)
    (root/"App/VERSIE.txt").write_text("32.4.56")
    incoming=root/"Inbox/incoming";incoming.mkdir(parents=True)
    candidate=incoming/"EnergieProject_v32.4.57.zip";_zip(candidate)
    result=verify_candidate(root,candidate)
    assert result["ready"] is True and result["blockers"] == []


def test_32457_exact_legacy_install_adoption(tmp_path):
    root=tmp_path/"energy";(root/"App").mkdir(parents=True)
    (root/"App/VERSIE.txt").write_text("32.4.57")
    (root/"Inbox/processed").mkdir(parents=True)
    artifact=root/"Inbox/processed/EnergieProject_v32.4.57.zip"
    artifact.write_bytes(b"exact-artifact")
    sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
    (root/"Inbox").mkdir(exist_ok=True)
    (root/"Inbox/atomic_app_swap_state.json").write_text(json.dumps({
        "state":"LIVE_ACCEPTANCE","from_version":"32.4.56","to_version":"32.4.57","artifact_sha256":sha
    }))
    controller=ReleaseController()
    store=StateStore(root/"Inbox/release_controller/current.json")
    state=adopt_exact_pre57_install(root,controller,store)
    assert state is not None
    assert state.phase == "INSTALLED" and state.status == "ACTIVE"
    assert state.artifact_sha256 == sha


def test_32457_legacy_adoption_is_exactly_56_to_57_only(tmp_path):
    root=tmp_path/'energy';(root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.4.58')
    (root/'Inbox/processed').mkdir(parents=True)
    artifact=root/'Inbox/processed/EnergieProject_v32.4.58.zip'
    artifact.write_bytes(b'exact')
    sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
    (root/'Inbox/atomic_app_swap_state.json').write_text(json.dumps({
        'state':'LIVE_ACCEPTANCE','from_version':'32.4.57','to_version':'32.4.58','artifact_sha256':sha
    }))
    controller=ReleaseController();store=StateStore(root/'Inbox/release_controller/current.json')
    assert adopt_exact_pre57_install(root,controller,store) is None
    assert store.load() is None


def test_32457_legacy_adoption_rejects_symlink_atomic_authority(tmp_path):
    root=tmp_path/'energy';(root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.4.57')
    (root/'Inbox').mkdir(parents=True,exist_ok=True)
    external=tmp_path/'atomic-outside.json'
    external.write_text(json.dumps({
        'state':'LIVE_ACCEPTANCE','from_version':'32.4.56','to_version':'32.4.57','artifact_sha256':'a'*64
    }))
    (root/'Inbox/atomic_app_swap_state.json').symlink_to(external)
    controller=ReleaseController();store=StateStore(root/'Inbox/release_controller/current.json')
    assert adopt_exact_pre57_install(root,controller,store) is None
    assert store.load() is None


def test_32457_adoption_rejects_wrong_processed_artifact(tmp_path):
    root=tmp_path/"energy";(root/"App").mkdir(parents=True)
    (root/"App/VERSIE.txt").write_text("32.4.57")
    (root/"Inbox/processed").mkdir(parents=True)
    artifact=root/"Inbox/processed/EnergieProject_v32.4.57.zip"
    artifact.write_bytes(b"wrong")
    (root/"Inbox/atomic_app_swap_state.json").write_text(json.dumps({
        "state":"LIVE_ACCEPTANCE","from_version":"32.4.56","to_version":"32.4.57","artifact_sha256":"a"*64
    }))
    controller=ReleaseController();store=StateStore(root/"Inbox/release_controller/current.json")
    try:
        adopt_exact_pre57_install(root,controller,store)
    except RuntimeError as exc:
        assert "processed_artifact_mismatch" in str(exc)
    else:
        raise AssertionError("adoption must fail closed on artifact mismatch")


def test_32457_controller_state_reader_rejects_symlink(tmp_path):
    root=tmp_path/"energy";p=root/"Inbox/release_controller";p.mkdir(parents=True)
    external=tmp_path/"outside.json";external.write_text("{}")
    (p/"current.json").symlink_to(external)
    try:
        load_release_controller_state(root)
    except RuntimeError:
        pass
    else:
        raise AssertionError("symlink controller state must fail closed")


def test_32457_canonical_state_store_rejects_symlink(tmp_path):
    external=tmp_path/'outside-state.json'
    external.write_text(json.dumps({'phase':'COMPLETE','status':'COMPLETE'}),encoding='utf-8')
    path=tmp_path/'Inbox/release_controller/current.json'
    path.parent.mkdir(parents=True)
    path.symlink_to(external)
    store=StateStore(path)
    try:
        store.load()
    except RuntimeError as exc:
        assert 'unsafe' in str(exc)
    else:
        raise AssertionError('canonical controller StateStore must reject symlink reads')


def test_32457_side_effect_phase_is_persistable_before_publication_install_or_runtime_call():
    calls=[]
    class Adapter:
        def install(self,s):calls.append('install');return None
        def runtime_align(self,s):calls.append('runtime');return None
    controller=ReleaseController()
    state=controller.new_state(
        from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='a'*64,artifact_name='EnergieProject_v32.4.57.zip',
    )
    controller.mark_verified(state,['artifact'])
    controller.cycle(state,Adapter())
    assert state.phase=='PUBLISHING'
    assert calls==[]
    state.phase='INSTALLED';state.status='ACTIVE';state.step=5
    controller.cycle(state,Adapter())
    assert state.phase=='RUNTIME_ALIGNING'
    assert calls==[]


def test_32457_control_plane_is_actuator_not_preinstall_gate(tmp_path):
    calls=[]
    class Guard:
        def probe(self,root):
            return {'ready':True,'expected_fingerprint':'a'*64,'runtime_fingerprint':'a'*64}
    coord=NativeRuntimeCoordinator(
        tmp_path,Guard(),lambda:True,
        control_plane_prepare=lambda:calls.append('prepare'),
    )
    controller=ReleaseController()
    state=controller.new_state(
        from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='a'*64,artifact_name='EnergieProject_v32.4.57.zip',
    )
    result=coord.align(state)
    assert result.status=='GREEN'
    assert calls==[]


def test_32457_native_ready_cleans_only_exact_stale_release_request(tmp_path):
    expected='6'*64
    class Guard:
        def probe(self,root):
            return {'ready':True,'expected_fingerprint':expected,'runtime_fingerprint':expected}
    controller=ReleaseController()
    state=controller.new_state(
        from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='5'*64,artifact_name='EnergieProject_v32.4.57.zip',
    )
    state.phase='RUNTIME_ALIGNING';state.status='ACTIVE';state.step=5
    rid=hashlib.sha256(f'{state.release_id}|{state.generation}|{state.artifact_sha256}|{expected}'.encode()).hexdigest()[:32]
    request_path=tmp_path/'Inbox/control_plane/requests/native_mcp_reload.json'
    request_path.parent.mkdir(parents=True)
    request_path.write_text(json.dumps({
        'schema':'energie_control_plane_release_request_v1',
        'authorization':'release_controller','action':'native_mcp_reload',
        'container':'energie-filesystem-mcp','request_id':rid,
        'release_id':state.release_id,'generation':state.generation,
        'release_version':state.to_version,'artifact_sha256':state.artifact_sha256,
        'expected_fingerprint':expected,
    }))
    calls=[]
    result=NativeRuntimeCoordinator(
        tmp_path,Guard(),lambda:calls.append('probe') or True,
        control_plane_prepare=lambda:calls.append('prepare'),
    ).align(state)
    assert result.status=='GREEN'
    assert not request_path.exists()
    assert calls==[]


def test_32457_control_plane_sync_occurs_only_when_native_actuator_is_needed(tmp_path):
    calls=[]
    class Guard:
        def probe(self,root):
            return {'ready':False,'expected_fingerprint':'b'*64,'runtime_fingerprint':'c'*64}
    coord=NativeRuntimeCoordinator(
        tmp_path,Guard(),lambda:False,
        control_plane_prepare=lambda:calls.append('prepare'),
    )
    controller=ReleaseController()
    state=controller.new_state(
        from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='a'*64,artifact_name='EnergieProject_v32.4.57.zip',
    )
    result=coord.align(state)
    assert calls==['prepare']
    assert result.status=='BLOCKED'
    assert result.reason=='control_plane_unavailable'


def test_32457_control_plane_prepare_failure_is_one_exact_blocker(tmp_path):
    class Guard:
        def probe(self,root):
            return {'ready':False,'expected_fingerprint':'b'*64,'runtime_fingerprint':'c'*64}
    def fail_prepare():
        raise RuntimeError('socket down')
    coord=NativeRuntimeCoordinator(tmp_path,Guard(),lambda:False,control_plane_prepare=fail_prepare)
    controller=ReleaseController()
    state=controller.new_state(
        from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='a'*64,artifact_name='EnergieProject_v32.4.57.zip',
    )
    result=coord.align(state)
    assert result.status=='BLOCKED'
    assert result.reason=='control_plane_prepare_failed:RuntimeError'



def test_32457_native_fenced_red_is_exact_blocker_not_new_restart_request(tmp_path):
    expected='9'*64
    class Guard:
        def probe(self,root):return {'ready':False,'expected_fingerprint':expected,'runtime_fingerprint':'8'*64}
    controller=ReleaseController()
    state=controller.new_state(
        from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='7'*64,artifact_name='EnergieProject_v32.4.57.zip',
    )
    state.phase='RUNTIME_ALIGNING';state.status='ACTIVE';state.step=5
    import hashlib as _hashlib
    rid=_hashlib.sha256(f'{state.release_id}|{state.generation}|{state.artifact_sha256}|{expected}'.encode()).hexdigest()[:32]
    result_path=tmp_path/'Inbox/control_plane/results/native_mcp_reload.json'
    result_path.parent.mkdir(parents=True)
    result_path.write_text(json.dumps({
        'status':'RED','ok':False,'retry_allowed':False,'request_id':rid,
        'release_id':state.release_id,'generation':state.generation,
        'artifact_sha256':state.artifact_sha256,'release_version':state.to_version,
        'runtime_fingerprint':None,
    }))
    coord=NativeRuntimeCoordinator(tmp_path,Guard(),lambda:True)
    result=coord.align(state)
    assert result.status=='BLOCKED'
    assert result.reason=='native_mcp_reload_unproven'
    assert not (tmp_path/'Inbox/control_plane/requests/native_mcp_reload.json').exists()


def test_32457_stale_control_plane_heartbeat_uses_direct_probe_without_restart(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(control_plane_bootstrap,'sync_control_plane_source',lambda root:{'changed':[]})
    monkeypatch.setattr(
        control_plane_bootstrap.control_plane_runtime_guard,'probe',
        lambda root,stale_seconds=30:{
            'ready':False,'reason':'runtime_heartbeat_stale',
            'expected_fingerprint':'a'*64,'loaded_fingerprint':'a'*64,
        },
    )
    def fake_request(method,path,ok):
        calls.append((method,path))
        if method=='GET':
            return {'State':{'Running':True,'Health':{'Status':'healthy'}}}
        raise AssertionError('stale exact runtime must not restart')
    monkeypatch.setattr(control_plane_bootstrap,'_request',fake_request)
    result=control_plane_bootstrap.ensure_control_plane_current(tmp_path)
    assert result['status']=='GREEN'
    assert result['restart_performed'] is False
    assert result['direct_runtime_probe'] is True
    assert [m for m,_ in calls]==['GET']


def test_32457_control_plane_fingerprint_mismatch_restarts_existing_container_once(monkeypatch,tmp_path):
    calls=[]
    probes=iter([
        {'ready':False,'reason':'loaded_runtime_fingerprint_mismatch','expected_fingerprint':'b'*64,'loaded_fingerprint':'a'*64},
        {'ready':True,'reason':'loaded_runtime_fingerprint_match','expected_fingerprint':'b'*64,'loaded_fingerprint':'b'*64},
    ])
    monkeypatch.setattr(control_plane_bootstrap,'sync_control_plane_source',lambda root:{'changed':['control_plane.py']})
    monkeypatch.setattr(control_plane_bootstrap.control_plane_runtime_guard,'probe',lambda root,stale_seconds=30:next(probes))
    def fake_request(method,path,ok):
        calls.append((method,path))
        if method=='GET':
            return {'State':{'Running':True,'Health':{'Status':'healthy'}}}
        return {}
    monkeypatch.setattr(control_plane_bootstrap,'_request',fake_request)
    result=control_plane_bootstrap.ensure_control_plane_current(tmp_path)
    assert result['restart_performed'] is True
    assert result['direct_runtime_probe'] is False
    assert [m for m,_ in calls].count('POST')==1


def test_32457_control_plane_restart_attempt_is_bounded_per_expected_fingerprint(monkeypatch,tmp_path):
    expected='f'*64
    attempt=tmp_path/'Inbox/release_controller/control_plane_restart_attempt.json'
    attempt.parent.mkdir(parents=True)
    attempt.write_text(json.dumps({
        'schema':'energie_control_plane_restart_attempt_v1',
        'expected_fingerprint':expected,
        'status':'RED',
        'restart_performed':True,
        'retry_allowed':False,
    }))
    monkeypatch.setattr(control_plane_bootstrap,'sync_control_plane_source',lambda root:{'changed':[]})
    monkeypatch.setattr(
        control_plane_bootstrap.control_plane_runtime_guard,'probe',
        lambda root,stale_seconds=30:{
            'ready':False,'reason':'loaded_runtime_fingerprint_mismatch',
            'expected_fingerprint':expected,'loaded_fingerprint':'e'*64,
        },
    )
    calls=[]
    def fake_request(method,path,ok):
        calls.append((method,path))
        if method=='GET':
            return {'State':{'Running':True,'Health':{'Status':'healthy'}}}
        raise AssertionError('same expected fingerprint must never receive a second restart')
    monkeypatch.setattr(control_plane_bootstrap,'_request',fake_request)
    try:
        control_plane_bootstrap.ensure_control_plane_current(tmp_path)
    except RuntimeError as exc:
        assert 'bounded restart already attempted' in str(exc)
    else:
        raise AssertionError('bounded restart fence must block a second side effect')
    assert [method for method,_path in calls]==['GET']


def test_32457_control_plane_new_expected_fingerprint_may_get_one_new_bounded_restart(monkeypatch,tmp_path):
    old='a'*64;new='b'*64
    attempt=tmp_path/'Inbox/release_controller/control_plane_restart_attempt.json'
    attempt.parent.mkdir(parents=True)
    attempt.write_text(json.dumps({
        'schema':'energie_control_plane_restart_attempt_v1',
        'expected_fingerprint':old,
        'status':'RED','restart_performed':True,'retry_allowed':False,
    }))
    probes=iter([
        {'ready':False,'reason':'loaded_runtime_fingerprint_mismatch','expected_fingerprint':new,'loaded_fingerprint':old},
        {'ready':True,'reason':'loaded_runtime_fingerprint_match','expected_fingerprint':new,'loaded_fingerprint':new},
    ])
    monkeypatch.setattr(control_plane_bootstrap,'sync_control_plane_source',lambda root:{'changed':['control_plane.py']})
    monkeypatch.setattr(control_plane_bootstrap.control_plane_runtime_guard,'probe',lambda root,stale_seconds=30:next(probes))
    calls=[]
    def fake_request(method,path,ok):
        calls.append((method,path))
        if method=='GET':
            return {'State':{'Running':True,'Health':{'Status':'healthy'}}}
        return {}
    monkeypatch.setattr(control_plane_bootstrap,'_request',fake_request)
    result=control_plane_bootstrap.ensure_control_plane_current(tmp_path)
    assert result['status']=='GREEN' and result['restart_performed'] is True
    assert [method for method,_path in calls].count('POST')==1
    assert not attempt.exists()


def test_32457_controller_reexecs_new_code_only_after_complete_target():
    controller=ReleaseController()
    state=controller.new_state(from_version='32.4.57',to_version='32.4.58',artifact_sha256='b'*64,artifact_name='EnergieProject_v32.4.58.zip')
    state.phase='COMPLETE';state.status='COMPLETE';state.step=8
    assert should_reexec('32.4.57','32.4.58',state) is True
    assert should_reexec('32.4.58','32.4.58',state) is False
    state.status='WAITING'
    assert should_reexec('32.4.57','32.4.58',state) is False


def test_32457_atomic_accepted_before_controller_save_recovers_idempotently(tmp_path):
    root=tmp_path/'energy';app=root/'App';app.mkdir(parents=True)
    (app/'VERSIE.txt').write_text('32.4.57',encoding='utf-8')
    rollback=root/'App.__rollback_32.4.56';rollback.mkdir()
    (rollback/'VERSIE.txt').write_text('32.4.56',encoding='utf-8')
    controller=ReleaseController()
    state=controller.new_state(
        from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='a'*64,artifact_name='EnergieProject_v32.4.57.zip',
    )
    state.phase='VERIFYING';state.status='ACTIVE';state.step=6
    paths=atomic_app_swap.SwapPaths.for_release(root,'32.4.56','32.4.57')
    atomic_app_swap.write_journal_atomic(paths,state='ACCEPTED',artifact_sha256='a'*64)
    class Guard:
        def probe(self,root):return {'ready':True}
    class Native:
        guard=Guard()
    adapter=AtomicReleaseAdapter(root,atomic_app_swap,Native(),None)
    verified=adapter.verify_live(state)
    assert verified.status=='GREEN'
    accepted=adapter.atomic_accept(state)
    assert accepted.status=='GREEN'
    assert 'atomic_already_accepted' in accepted.evidence


def test_32457_pre_activation_rollback_removes_exact_candidate_and_settles_journal(tmp_path):
    root=tmp_path/'energy';app=root/'App';app.mkdir(parents=True)
    (app/'VERSIE.txt').write_text('32.4.56',encoding='utf-8')
    controller=ReleaseController()
    state=controller.new_state(from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='a'*64,artifact_name='EnergieProject_v32.4.57.zip')
    paths=atomic_app_swap.SwapPaths.for_release(root,'32.4.56','32.4.57')
    paths.candidate.mkdir();(paths.candidate/'VERSIE.txt').write_text('32.4.57')
    atomic_app_swap.write_journal_atomic(paths,state='PREPARED',artifact_sha256='a'*64)
    adapter=AtomicReleaseAdapter(root,atomic_app_swap,None,None)
    result=adapter.rollback(state,'probe_failed')
    assert result.status=='ROLLED_BACK'
    assert not paths.candidate.exists()
    journal=atomic_app_swap.load_journal(paths)
    assert journal['state']=='ROLLED_BACK'
    assert (root/'App/VERSIE.txt').read_text().strip()=='32.4.56'


def test_32457_no_journal_candidate_cleanup_is_bounded_to_exact_candidate(tmp_path):
    root=tmp_path/'energy';app=root/'App';app.mkdir(parents=True)
    (app/'VERSIE.txt').write_text('32.4.56',encoding='utf-8')
    keep=root/'App.__failed_32.4.57_001';keep.mkdir()
    controller=ReleaseController()
    state=controller.new_state(from_version='32.4.56',to_version='32.4.57',
        artifact_sha256='b'*64,artifact_name='EnergieProject_v32.4.57.zip')
    paths=atomic_app_swap.SwapPaths.for_release(root,'32.4.56','32.4.57')
    paths.candidate.mkdir();(paths.candidate/'VERSIE.txt').write_text('32.4.57')
    adapter=AtomicReleaseAdapter(root,atomic_app_swap,None,None)
    result=adapter.rollback(state,'same_filesystem_probe_failed')
    assert result.status=='ROLLED_BACK'
    assert not paths.candidate.exists()
    assert keep.is_dir()
    assert atomic_app_swap.load_journal(paths) is None
