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

def _release_tuple(value:str):
    try:
        parts=tuple(int(part) for part in str(value or '').strip().split('.'))
    except ValueError:
        return None
    return parts if len(parts)==3 else None

def _legacy_live_version(version_path:Path)->str:
    path=Path(version_path)
    st=path.lstat()
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        raise RuntimeError('unsafe legacy version path')
    value=path.read_text(encoding='utf-8').strip()
    if not value:
        raise RuntimeError('legacy live version ontbreekt')
    return value

def authorize_release_native_reconcile(*,request_path:Path,controller_state_path:Path,version_path:Path,runtime_guard_path:Path,atomic_state_path:Path|None=None)->tuple[dict,dict]:
    request=_load(request_path);state=_load(controller_state_path);guard=_load(runtime_guard_path)
    release_parts=_release_tuple(request.get('release_version'))
    if release_parts is None:
        raise RuntimeError('release-scoped request release_version invalid')
    if atomic_state_path is None:
        # Compatibility only for historical release-scoped fixtures/contracts.
        # 32.5.13+ is the generation where atomic state became mandatory after
        # the stale App/VERSIE bind failure; current/future production never
        # falls back to the file-based authority.
        if release_parts >= (32,5,13):
            raise RuntimeError('release-scoped request vereist stabiele atomic authority')
        atomic_state=None
        live_version=_legacy_live_version(version_path)
    else:
        atomic_state=_load(atomic_state_path)
        live_version=None
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
