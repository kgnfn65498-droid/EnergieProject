from __future__ import annotations

MCP_CONTAINER='energie-filesystem-mcp'
ALLOWED_RELEASE_ACTION='native_mcp_reload'

def validate_release_scoped_request(request:dict,state:dict,*,live_version:str,expected_fingerprint:str)->bool:
    if request.get('schema')!='energie_control_plane_release_request_v1': return False
    if request.get('authorization')!='release_controller': return False
    if request.get('action')!=ALLOWED_RELEASE_ACTION: return False
    if request.get('container')!=MCP_CONTAINER: return False
    if state.get('phase')!='RUNTIME_ALIGNING': return False
    checks=(
        ('release_id','release_id'),('generation','generation'),
        ('release_version','to_version'),('artifact_sha256','artifact_sha256')
    )
    for req_key,state_key in checks:
        if str(request.get(req_key) or '')!=str(state.get(state_key) or ''): return False
    if str(request.get('release_version') or '')!=str(live_version): return False
    if str(request.get('expected_fingerprint') or '').lower()!=str(expected_fingerprint).lower(): return False
    rid=str(request.get('request_id') or '').lower()
    return len(rid)==32 and all(c in '0123456789abcdef' for c in rid)
