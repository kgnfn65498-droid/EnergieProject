from __future__ import annotations
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA='energie_clearup_system_path_contract_v1'
ACTIVATION_ROOT=Path('Data/03_Systeem/Projectmanager/ClearUp/PathActivation')
MAPPINGS={
 'pm_runtime':('Inbox/projectmanager_v2/RuntimeV2','Data/03_Systeem/Projectmanager/RuntimeV2'),
 'logs':('Inbox/logs','Data/03_Systeem/Projectmanager/Logs/Runtime'),
 'operating_mode':('Inbox/operating_mode','Data/03_Systeem/Projectmanager/OperatingMode'),
 'release_controller':('Inbox/release_controller','Data/03_Systeem/Projectmanager/ReleaseController'),
 'ha_runtime':('Inbox/ha_runtime','Data/03_Systeem/Projectmanager/RuntimeEvidence/HomeAssistant'),
 'native_mcp_runtime':('Inbox/native_mcp_runtime','Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP'),
 'control_plane_runtime':('Inbox/control_plane','Data/03_Systeem/Projectmanager/ControlPlane/Runtime'),
 'process':('Inbox/process','Data/03_Systeem/Projectmanager/Runtime/Process'),
 'publisher_history':('Inbox/github_publisher_history.jsonl','Data/03_Systeem/Projectmanager/Logs/Publisher/github_publisher_history.jsonl'),
 'latest_release_status':('Inbox/latest_release_status.txt','Data/03_Systeem/Projectmanager/ReleaseController/latest_release_status.txt'),
 'watcher_contract':('Inbox/watcher_container_contract.json','Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_container_contract.json'),
 'control_plane_yaml':('Inbox/energie-control-plane.containerstation-v3.yml','Data/03_Systeem/Projectmanager/ControlPlane/energie-control-plane.containerstation-v3.yml'),
 'watcher_heartbeat_legacy':('Inbox/.watcher.heartbeat','Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher.heartbeat.legacy'),
 'watcher_heartbeat_v2':('Inbox/watcher_heartbeat.v2','Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_heartbeat.v2'),
 'atomic_state':('Inbox/atomic_app_swap_state.json','Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json'),
 'github_publication_state':('Inbox/github_publication_state.json','Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json'),
 'github_publisher_state':('Inbox/github_publisher_state.json','Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publisher_state.json'),
 'project_cr_local':('Inbox/project_cr_local','Data/03_Systeem/Projectmanager/CrashRecovery/ProjectLocal'),
 'nas_container_cr_local':('Inbox/nas_container_cr_local','Data/03_Systeem/Projectmanager/CrashRecovery/NASContainerLocal'),
 'nas_cr_lock':('Inbox/.nas-container-cr.operation.lock','Data/03_Systeem/Projectmanager/Runtime/Locks/nas-container-cr.operation.lock'),
 'release_controller_lock':('Inbox/.release-controller.lock','Data/03_Systeem/Projectmanager/Runtime/Locks/release-controller.lock'),
 'release_transition_lock':('Inbox/.release-transition.operation.lock','Data/03_Systeem/Projectmanager/Runtime/Locks/release-transition.operation.lock'),
}
PREFIXES=sorted(((src,key,dst) for key,(src,dst) in MAPPINGS.items()), key=lambda x:len(x[0]), reverse=True)

def _active(root:Path,key:str,destination:Path)->bool:
    marker=root/ACTIVATION_ROOT/f'{key}.json'
    if marker.is_symlink() or not marker.is_file() or destination.is_symlink() or not destination.exists(): return False
    try: data=json.loads(marker.read_text(encoding='utf-8'))
    except Exception: return False
    return isinstance(data,dict) and data.get('schema')==SCHEMA and data.get('key')==key and data.get('active') is True

def project_system_path(project_root:Path|str, relative:str)->Path:
    root=Path(project_root).resolve(); rel=str(relative).replace('\\','/').strip('/')
    for src,key,dst in PREFIXES:
        if rel==src or rel.startswith(src+'/'):
            suffix=rel[len(src):].lstrip('/')
            dest=root/dst
            base=dest if _active(root,key,dest) else root/src
            return base/suffix if suffix else base
    return root/rel

def mapping_for_source(source:str)->tuple[str,str,str]|None:
    rel=str(source).replace('\\','/').strip('/')
    for src,key,dst in PREFIXES:
        if rel==src: return key,src,dst
    return None


def active_mapping_fingerprint(project_root:Path|str)->str:
    """Fingerprint the currently resolved path contract without reading payload data."""
    root=Path(project_root).resolve(); rows=[]
    for key,(src,dst) in sorted(MAPPINGS.items()):
        resolved=project_system_path(root,src)
        rows.append(f"{key}\0{src}\0{dst}\0{resolved.relative_to(root).as_posix()}")
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
