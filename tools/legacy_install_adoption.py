from __future__ import annotations
from system_path_contract import project_system_path
import hashlib,json,time,stat
from pathlib import Path
from release_controller import ReleaseController,Phase,Status
from state_store import StateStore

def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()

def _json(path:Path)->dict:
    try:
        st=Path(path).lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            return {}
        v=json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception:
        return {}
    return v if isinstance(v,dict) else {}

def adopt_exact_pre57_install(root:Path|str,controller:ReleaseController,store:StateStore):
    root=Path(root)
    if store.load() is not None:return None
    try:active=(root/'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    except OSError:return None
    # This bridge exists only for the one historical 32.4.56 -> 32.4.57
    # handover. 58+ must never reconstruct a missing central lifecycle from
    # legacy state; that would reintroduce a second release authority.
    if active!='32.4.57':
        return None
    atomic=_json(project_system_path(root, 'Inbox/atomic_app_swap_state.json'))
    atom=str(atomic.get('state') or '').upper()
    if atom not in {'LIVE_ACCEPTANCE','ACCEPTED'}:return None
    if str(atomic.get('to_version') or '')!=active:
        raise RuntimeError('legacy_adoption_atomic_target_mismatch')
    source=str(atomic.get('from_version') or '')
    sha=str(atomic.get('artifact_sha256') or '').lower()
    if source!='32.4.56' or len(sha)!=64 or any(c not in '0123456789abcdef' for c in sha):
        raise RuntimeError('legacy_adoption_atomic_identity_invalid')
    incoming=root/'Inbox/incoming';processing=root/'Inbox/processing'
    if any(incoming.glob('*.zip')) if incoming.is_dir() else False:
        raise RuntimeError('legacy_adoption_incoming_not_empty')
    if any(processing.glob('*.zip')) if processing.is_dir() else False:
        raise RuntimeError('legacy_adoption_processing_not_empty')
    artifact=root/'Inbox/processed'/f'EnergieProject_v{active}.zip'
    if artifact.is_symlink() or not artifact.is_file() or _sha(artifact)!=sha:
        raise RuntimeError('legacy_adoption_processed_artifact_mismatch')
    state=controller.new_state(from_version=source,to_version=active,artifact_sha256=sha,artifact_name=artifact.name)
    controller.mark_verified(state,['legacy_installer_artifact_exact','processed_artifact_hash_exact'])
    now=time.time()
    if atom=='ACCEPTED':
        state.phase=Phase.ACCEPTED.value;state.step=7
        state.evidence=(state.evidence or [])+['atomic_already_accepted']
    else:
        state.phase=Phase.INSTALLED.value;state.step=4
        state.evidence=(state.evidence or [])+['atomic_live_acceptance_adopted']
    state.status=Status.ACTIVE.value;state.phase_started_at_epoch=now;state.updated_at_epoch=now
    transition=_json(project_system_path(root, 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json'))
    if str(transition.get('to_release') or '')==active:
        state.evidence.append('legacy_transition_observed_not_authoritative')
    hold=_json(project_system_path(root, 'Inbox/operating_mode/release_validation_hold.json'))
    if str(hold.get('release_version') or '')==active:
        state.evidence.append('legacy_hold_observed_not_authoritative')
    store.save(state.to_dict())
    return state
