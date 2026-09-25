from __future__ import annotations
import json,stat
from pathlib import Path
from release_scoped_auth import validate_release_scoped_request

def _load(path:Path)->dict:
    st=Path(path).lstat()
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):raise RuntimeError('unsafe json path')
    value=json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value,dict):raise RuntimeError('json object required')
    return value

def authorize_release_native_reconcile(*,request_path:Path,controller_state_path:Path,version_path:Path,runtime_guard_path:Path,atomic_state_path:Path|None=None)->tuple[dict,dict]:
    request=_load(request_path);state=_load(controller_state_path);guard=_load(runtime_guard_path)
    atomic_state=_load(atomic_state_path) if atomic_state_path is not None else None
    live_version=None if atomic_state is not None else Path(version_path).read_text(encoding='utf-8').strip()
    expected=str(guard.get('expected_fingerprint') or '').lower()
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
        raise RuntimeError('native MCP runtime guard expected fingerprint invalid')
    if not validate_release_scoped_request(
        request,state,live_version=live_version,expected_fingerprint=expected,atomic_state=atomic_state
    ):
        raise RuntimeError('release-scoped native MCP reconcile authorization rejected')
    return request,state

def authorize_release_native_request(*,request_path:Path,controller_state_path:Path,version_path:Path,runtime_guard_path:Path,atomic_state_path:Path|None=None)->tuple[dict,dict]:
    request,state=authorize_release_native_reconcile(
        request_path=request_path,
        controller_state_path=controller_state_path,
        version_path=version_path,
        runtime_guard_path=runtime_guard_path,
        atomic_state_path=atomic_state_path,
    )
    guard=_load(runtime_guard_path)
    if guard.get('status')!='RELOAD_REQUIRED' or guard.get('reload_required') is not True:
        raise RuntimeError('native MCP runtime guard does not require reload')
    return request,state

def release_result_fields(request:dict)->dict:
    return {k:request[k] for k in ('release_id','generation','artifact_sha256','release_version')}
