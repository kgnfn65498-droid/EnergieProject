from __future__ import annotations

MCP_CONTAINER='energie-filesystem-mcp'
ALLOWED_RELEASE_ACTION='native_mcp_reload'

def validate_release_scoped_request(
    request:dict,
    state:dict,
    *,
    live_version:str|None=None,
    expected_fingerprint:str,
    atomic_state:dict|None=None,
)->bool:
    if request.get('schema')!='energie_control_plane_release_request_v1': return False
    if request.get('authorization')!='release_controller': return False
    if request.get('action')!=ALLOWED_RELEASE_ACTION: return False
    if request.get('container')!=MCP_CONTAINER: return False
    phase=str(state.get('phase') or '')
    status=str(state.get('status') or '')
    # Normal release execution authorizes the reload while the controller owns
    # RUNTIME_ALIGNING. A freshly installed controller may also discover an
    # exact Native-MCP source/runtime mismatch only after its predecessor already
    # persisted this same release as COMPLETE. That post-COMPLETE reconciliation
    # remains safe only for the exact release-scoped request below; it must not
    # become a generic restart capability.
    if phase=='RUNTIME_ALIGNING':
        pass
    elif phase=='COMPLETE' and status=='COMPLETE':
        pass
    else:
        return False
    checks=(
        ('release_id','release_id'),('generation','generation'),
        ('release_version','to_version'),('artifact_sha256','artifact_sha256')
    )
    for req_key,state_key in checks:
        if str(request.get(req_key) or '')!=str(state.get(state_key) or ''): return False

    # 32.5.14: release-scoped runtime authority must come from the stable Inbox
    # state, not from a bind-mounted App/VERSIE.txt file. Atomic App swaps replace
    # the App inode, while a Docker file bind keeps pointing at the predecessor.
    # The controller+atomic pair is already the release acceptance authority and
    # remains on the stable Inbox mount. Legacy/manual requests keep the old
    # live_version check for backward compatibility.
    if atomic_state is not None:
        atomic_status=str(atomic_state.get('state') or '')
        if phase=='COMPLETE':
            if atomic_status!='ACCEPTED': return False
        elif atomic_status not in {'LIVE_ACCEPTANCE','ACCEPTED'}:
            return False
        if str(atomic_state.get('to_version') or '')!=str(request.get('release_version') or ''): return False
        if str(atomic_state.get('artifact_sha256') or '')!=str(request.get('artifact_sha256') or ''): return False
    else:
        if str(request.get('release_version') or '')!=str(live_version or ''): return False

    if str(request.get('expected_fingerprint') or '').lower()!=str(expected_fingerprint).lower(): return False
    rid=str(request.get('request_id') or '').lower()
    return len(rid)==32 and all(c in '0123456789abcdef' for c in rid)
