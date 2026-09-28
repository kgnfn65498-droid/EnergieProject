from __future__ import annotations

import json
import os
import re
from pathlib import Path

import project_clearup_move_executor
from system_path_contract import project_system_path

_SCOPED_RESULT_ROOT='Data/03_Systeem/Projectmanager/ClearUp/Runtime/results'
_SCOPED_RESULT_RE=re.compile(r'^'+re.escape(_SCOPED_RESULT_ROOT)+r'/([0-9a-f]{32})\.json$')
_REQUEST_SCOPED_SCHEMAS={'energie_clearup_type2_request_v1','energie_clearup_scoped_request_v1'}

_ALLOWED_RESULTS={
    'Inbox/logs/project_clearup_move_result.json',
    'Data/03_Systeem/Projectmanager/Logs/project_clearup_move_result.json',
    'Data/03_Systeem/Projectmanager/Logs/Runtime/project_clearup_move_result.json',
    'Data/03_Systeem/Projectmanager/ClearUp/Runtime/project_clearup_move_result.json',
}


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError('sideband canonical result symlink refused')
    tmp=path.with_name('.'+path.name+f'.tmp-{os.getpid()}')
    try:
        tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)

def process_once(root: Path | str) -> dict | None:
    root=Path(root).resolve()
    request=root/'Inbox/project_clearup_move_request.json'
    if request.is_symlink():
        raise RuntimeError('sideband request symlink refused')
    if not request.is_file():
        return None
    try:
        raw=json.loads(request.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError(f'sideband request unreadable:{type(exc).__name__}') from exc
    request_id=str(raw.get('request_id') or '') if isinstance(raw,dict) else ''
    requested_result=str(raw.get('result_path') or '').strip() if isinstance(raw,dict) else ''
    if requested_result:
        schema=str(raw.get('schema') or '') if isinstance(raw,dict) else ''
        is_request_scoped=schema in _REQUEST_SCOPED_SCHEMAS
        dynamic_match = _SCOPED_RESULT_RE.fullmatch(requested_result) if is_request_scoped else None
        dynamic_ok = bool(dynamic_match and dynamic_match.group(1) == request_id)
        if requested_result not in _ALLOWED_RESULTS and not dynamic_ok:
            raise RuntimeError('sideband result path outside allowlist')
        result=(root/requested_result).resolve()
        if root not in result.parents:
            raise RuntimeError('sideband result path escapes project')
        if dynamic_ok:
            # 32.5.19: this is shared cross-identity IPC.  The privileged bridge,
            # not the embedded PM, owns creation and permissions of this root.
            dynamic_root=root/_SCOPED_RESULT_ROOT
            if dynamic_root.is_symlink():
                raise RuntimeError('sideband scoped result root symlink refused')
            dynamic_root.mkdir(parents=True,exist_ok=True)
            if dynamic_root.resolve() != result.parent.resolve():
                raise RuntimeError('sideband scoped result parent mismatch')
            os.chmod(dynamic_root,0o777)
    else:
        result=project_system_path(root,'Inbox/logs/project_clearup_move_result.json')
    if result.is_file() and not result.is_symlink():
        try: existing=json.loads(result.read_text(encoding='utf-8'))
        except Exception: existing={}
        if isinstance(existing,dict) and existing.get('request_id')==request_id and existing.get('status') in {'completed','rejected','error'}:
            return existing
    _,payload=project_clearup_move_executor.process(root,request,result)
    current_result=project_system_path(root,'Inbox/logs/project_clearup_move_result.json').resolve()
    # Request-scoped 32.5.x ClearUp protocols keep their result outside every
    # migratable Inbox source tree. Never mirror a Type2 result back into Inbox/logs;
    # the same rule applies to the 32.5.26 scoped Type3/final-Inbox protocol.
    schema=str(raw.get('schema') or '') if isinstance(raw,dict) else ''
    is_request_scoped=schema in _REQUEST_SCOPED_SCHEMAS
    if is_request_scoped:
        try:
            os.chmod(result,0o666)
        except OSError:
            pass
        canonical=(root/'Data/03_Systeem/Projectmanager/ClearUp/Runtime/project_clearup_move_result.json').resolve()
        if root not in canonical.parents or canonical.is_symlink():
            raise RuntimeError('sideband Type2 canonical result path unsafe')
        _atomic_json(canonical,payload)
    if not is_request_scoped and current_result != result:
        if root not in current_result.parents or current_result.is_symlink():
            raise RuntimeError('sideband activated result path unsafe')
        current_result.parent.mkdir(parents=True,exist_ok=True)
        tmp=current_result.with_name('.'+current_result.name+f'.tmp-{os.getpid()}')
        try:
            tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
            os.replace(tmp,current_result)
        finally:
            tmp.unlink(missing_ok=True)
    return payload
