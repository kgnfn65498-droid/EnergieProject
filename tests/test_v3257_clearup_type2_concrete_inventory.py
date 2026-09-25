import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'slimmemeterportal_import/rootfs/app'
PM=APP/'projectmanager_v2'
sys.path.insert(0,str(APP));sys.path.insert(0,str(PM));sys.path.insert(0,str(ROOT/'tools'))

from system_path_contract import project_system_path, active_mapping_fingerprint
import clearup_type2_service as service

EXPECTED={
'ClearUp_002':[('Inbox/projectmanager_v2/RuntimeV2','Data/03_Systeem/Projectmanager/RuntimeV2','pm_runtime')],
'ClearUp_003':[('Inbox/logs','Data/03_Systeem/Projectmanager/Logs/Runtime','logs'),('Inbox/github_publisher_history.jsonl','Data/03_Systeem/Projectmanager/Logs/Publisher/github_publisher_history.jsonl','publisher_history')],
'ClearUp_004':[('Inbox/operating_mode','Data/03_Systeem/Projectmanager/OperatingMode','operating_mode')],
'ClearUp_005':[('Inbox/release_controller','Data/03_Systeem/Projectmanager/ReleaseController','release_controller'),('Inbox/latest_release_status.txt','Data/03_Systeem/Projectmanager/ReleaseController/latest_release_status.txt','latest_release_status')],
'ClearUp_006':[('Inbox/ha_runtime','Data/03_Systeem/Projectmanager/RuntimeEvidence/HomeAssistant','ha_runtime'),('Inbox/native_mcp_runtime','Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP','native_mcp_runtime')],
'ClearUp_007':[('Inbox/control_plane','Data/03_Systeem/Projectmanager/ControlPlane/Runtime','control_plane_runtime'),('Inbox/energie-control-plane.containerstation-v3.yml','Data/03_Systeem/Projectmanager/ControlPlane/energie-control-plane.containerstation-v3.yml','control_plane_yaml')],
'ClearUp_008':[('Inbox/process','Data/03_Systeem/Projectmanager/Runtime/Process','process')],
'ClearUp_010':[('Inbox/project_cr_local','Data/03_Systeem/Projectmanager/CrashRecovery/ProjectLocal','project_cr_local'),('Inbox/nas_container_cr_local','Data/03_Systeem/Projectmanager/CrashRecovery/NASContainerLocal','nas_container_cr_local')],
'ClearUp_011':[('Inbox/atomic_app_swap_state.json','Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json','atomic_state'),('Inbox/github_publication_state.json','Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json','github_publication_state'),('Inbox/github_publisher_state.json','Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publisher_state.json','github_publisher_state')],
'ClearUp_012':[('Inbox/.nas-container-cr.operation.lock','Data/03_Systeem/Projectmanager/Runtime/Locks/nas-container-cr.operation.lock','nas_cr_lock'),('Inbox/.release-controller.lock','Data/03_Systeem/Projectmanager/Runtime/Locks/release-controller.lock','release_controller_lock'),('Inbox/.release-transition.operation.lock','Data/03_Systeem/Projectmanager/Runtime/Locks/release-transition.operation.lock','release_transition_lock'),('Inbox/watcher_heartbeat.v2','Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_heartbeat.v2','watcher_heartbeat_v2')],
'ClearUp_009':[('Inbox/.watcher.heartbeat','Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher.heartbeat.legacy','watcher_heartbeat_legacy'),('Inbox/watcher_container_contract.json','Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_container_contract.json','watcher_contract')],
}

def test_bundled_concrete_type2_inventory_is_complete():
    for cid, expected in EXPECTED.items():
        path=ROOT/'tools/clearup_type2_plans'/f'{cid}.json'
        d=json.loads(path.read_text())
        assert d['schema']=='energie_clearup_type2_plan_v1' and d['classification']=='TYPE2' and d['status']=='READY'
        got=[(x['source'],x['destination'],x.get('path_key','')) for x in d['items']]
        assert got==expected
        assert all(x['contract_checks'] for x in d['items'])

def test_type2_loader_falls_back_to_bundled_plan(tmp_path):
    (tmp_path/'App/tools/clearup_type2_plans').mkdir(parents=True)
    (tmp_path/'App/VERSIE.txt').parent.mkdir(parents=True,exist_ok=True)
    (tmp_path/'App/VERSIE.txt').write_text('32.5.7\n')
    (tmp_path/'App/tools/clearup_type2_plans/ClearUp_002.json').write_bytes((ROOT/'tools/clearup_type2_plans/ClearUp_002.json').read_bytes())
    plan=service._load_plan(tmp_path,'ClearUp_002')
    assert plan['items'][0]['path_key']=='pm_runtime'

def test_system_path_contract_switches_only_after_verified_marker(tmp_path):
    old=tmp_path/'Inbox/projectmanager_v2/RuntimeV2'; old.mkdir(parents=True)
    new=tmp_path/'Data/03_Systeem/Projectmanager/RuntimeV2'; new.mkdir(parents=True)
    assert project_system_path(tmp_path,'Inbox/projectmanager_v2/RuntimeV2/status/current.json')==old/'status/current.json'
    marker=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/PathActivation/pm_runtime.json';marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({'schema':'energie_clearup_system_path_contract_v1','key':'pm_runtime','active':True}))
    assert project_system_path(tmp_path,'Inbox/projectmanager_v2/RuntimeV2/status/current.json')==new/'status/current.json'

def test_idle_sideband_wires_clearup_request_to_privileged_executor_without_release_gate():
    controller=(ROOT/'tools/release_controller_service.py').read_text()
    bridge=(ROOT/'tools/sideband_bridge.py').read_text()
    assert 'sideband_bridge.process_once(self.root)' in controller
    assert 'project_clearup_move_executor.process(root,request,result)' in bridge
    assert "'Inbox/logs/project_clearup_move_result.json'" in bridge
    assert "'Data/03_Systeem/Projectmanager/Logs/project_clearup_move_result.json'" in bridge
    assert "'Data/03_Systeem/Projectmanager/Logs/Runtime/project_clearup_move_result.json'" in bridge
    # Release core remains free of housekeeping semantics: sideband is only polled after no release candidate exists.
    assert 'project_clearup' not in controller
    assert 'maintenance' not in controller.lower()

def test_control_plane_compose_is_ready_for_type2_system_paths():
    text=(ROOT/'tools/control_plane/docker-compose.containerstation.yml').read_text()
    assert 'Data/03_Systeem/Projectmanager/RuntimeV2/approved_actions:/pm-approved:ro' in text
    assert 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime:/control-plane-runtime:rw' in text
    assert 'Data/03_Systeem/Projectmanager/ReleaseController:/release-controller:ro' in text
    assert 'Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP:/native-mcp-runtime:ro' in text


def test_system_path_fingerprint_changes_only_after_activation(tmp_path):
    old=tmp_path/'Inbox/projectmanager_v2/RuntimeV2'; old.mkdir(parents=True)
    new=tmp_path/'Data/03_Systeem/Projectmanager/RuntimeV2'; new.mkdir(parents=True)
    before=active_mapping_fingerprint(tmp_path)
    marker=tmp_path/'Data/03_Systeem/Projectmanager/ClearUp/PathActivation/pm_runtime.json'; marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({'schema':'energie_clearup_system_path_contract_v1','key':'pm_runtime','active':True}))
    after=active_mapping_fingerprint(tmp_path)
    assert before != after

def test_long_lived_runtimes_rebind_when_path_contract_changes():
    controller=(ROOT/'tools/release_controller_service.py').read_text()
    embedded=(APP/'projectmanager_v2/embedded_runtime.py').read_text()
    entrypoint=(APP/'projectmanager_v2_entrypoint.py').read_text()
    assert 'active_mapping_fingerprint(root)' in controller
    assert "reason':'system_path_binding_changed'" in controller
    assert 'active_mapping_fingerprint(runtime.config.project_root)' in embedded
    assert "'state':'rebind_required'" in embedded
    assert "embedded_result.get('state') == 'rebind_required'" in entrypoint
