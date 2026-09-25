from __future__ import annotations
from system_path_contract import project_system_path

import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

CLEARUP_ID = 'ClearUp_001'
ROOTS = (
    'Inbox/.bridge_patch_stage_20260914T171141Z',
    'Inbox/live_bridge_backup_20260914T171141Z',
    'Inbox/live_bridge_backup_queue_schema_20260914T172223Z',
    'Inbox/.release-transition.operation.lock.backup_20260914T1812Z',
)
AFFIRMATIVE = {'akkoord','ja','yes','approve','goedgekeurd','goedkeuren'}
STAGING_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Staging/ClearUp_001')
RESULT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/State/ClearUp_001_apply.json')
WATCHER_REQUEST_REL = Path('Inbox/project_clearup_move_request.json')
WATCHER_RESULT_REL = Path('Inbox/logs/project_clearup_move_result.json')
WATCHER_SCHEMA = 'energie_clearup_type1_delete_request_v1'
WATCHER_RESULT_SCHEMA = 'energie_clearup_type1_delete_result_v1'
WATCHER_TIMEOUT_SECONDS = 60.0


def _sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def _token(text: str) -> str:
    return ' '.join(str(text or '').strip().lower().strip(' .,!?:;').split())


def _safe(root: Path, rel: str) -> Path:
    p=(root/rel).resolve()
    if p == root or root not in p.parents:
        raise RuntimeError('unsafe ClearUp path')
    return p


def _collect(root: Path, roots=ROOTS) -> list[dict[str,Any]]:
    rows=[]
    for rel in roots:
        p=_safe(root,rel)
        if not p.exists() or p.is_symlink():
            raise RuntimeError(f'candidate missing/unsafe: {rel}')
        seq=[p] if p.is_file() else [p,*sorted(p.rglob('*'))]
        for q in seq:
            if q.is_symlink():
                raise RuntimeError(f'symlink refused: {q}')
            r=q.relative_to(root).as_posix()
            if q.is_file(): rows.append({'path':r,'type':'file','size':q.stat().st_size,'sha256':_sha(q)})
            elif q.is_dir(): rows.append({'path':r,'type':'directory'})
    return rows


def _staging_rows(project_root: Path) -> list[dict[str,Any]]:
    stage=project_root/STAGING_REL
    if not stage.is_dir() or stage.is_symlink():
        raise RuntimeError('ClearUp_001 recovery staging missing/unsafe')
    mapping=[]
    for rel in ROOTS:
        src=Path(rel)
        p=stage/src.name
        if not p.exists() or p.is_symlink():
            raise RuntimeError(f'recovery staging incomplete: {src.name}')
        seq=[p] if p.is_file() else [p,*sorted(p.rglob('*'))]
        for q in seq:
            if q.is_symlink(): raise RuntimeError('staging symlink refused')
            suffix=q.relative_to(stage).as_posix()
            live_path='Inbox/'+suffix
            if q.is_file(): mapping.append({'path':live_path,'type':'file','size':q.stat().st_size,'sha256':_sha(q)})
            elif q.is_dir(): mapping.append({'path':live_path,'type':'directory'})
    return mapping


def _release_idle(root: Path) -> None:
    current=project_system_path(root, 'Inbox/release_controller/current.json')
    if current.is_file():
        try: state=json.loads(current.read_text(encoding='utf-8'))
        except Exception as exc: raise RuntimeError('release controller state unreadable') from exc
        if str(state.get('status') or '').upper() != 'COMPLETE' or str(state.get('phase') or '').upper() != 'COMPLETE':
            raise RuntimeError('release controller not COMPLETE; ClearUp blocked')
    processing=root/'Inbox/processing'
    if processing.is_dir() and any(p.name.startswith('EnergieProject_v') and p.suffix=='.zip' for p in processing.iterdir() if p.is_file()):
        raise RuntimeError('release processing active; ClearUp blocked')


def _dependency_guard(root: Path) -> None:
    needles=[Path(x).name for x in ROOTS]
    allowed={
        'App/tools/clearup_executor.py','App/tools/clearup_dependency_guard.py',
        'App/tools/native_mcp_runtime_contract_hotfix.py','App/tests/test_v3253_clearup_chat_export.py',
        'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_chat_service.py',
        'App/tools/project_clearup_move_executor.py',
    }
    hits=[]
    for base in (root/'App/slimmemeterportal_import/rootfs/app',):
        if not base.exists(): continue
        for p in base.rglob('*.py'):
            rel=p.relative_to(root).as_posix()
            if rel in allowed or p.name=='clearup_chat_service.py': continue
            try: text=p.read_text(encoding='utf-8')
            except OSError: continue
            for n in needles:
                if n in text: hits.append((rel,n))
    if hits:
        raise RuntimeError('active dependency guard RED: '+repr(hits[:5]))


def _snapshot_release_dirs(root: Path) -> dict[str,list[tuple[str,int,str]]]:
    result={}
    for rel in ('Inbox/incoming','Inbox/processing'):
        base=root/rel
        rows=[]
        if base.is_dir():
            for p in sorted(base.rglob('*')):
                if p.is_symlink(): raise RuntimeError(f'release mailbox symlink refused: {p}')
                if p.is_file(): rows.append((p.relative_to(base).as_posix(),p.stat().st_size,_sha(p)))
        result[rel]=rows
    return result


def _atomic_json(path: Path, payload: dict[str,Any]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink(): raise RuntimeError(f'unsafe request/result path: {path}')
    tmp=path.with_name(f'.{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}')
    try:
        with tmp.open('x',encoding='utf-8') as h:
            json.dump(payload,h,ensure_ascii=False,indent=2,sort_keys=True); h.write('\n'); h.flush(); os.fsync(h.fileno())
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


def _watcher_delete(root: Path, *, live_rows: list[dict[str,Any]], release_mailbox_before: dict[str,list[tuple[str,int,str]]]) -> dict[str,Any]:
    request_path=root/WATCHER_REQUEST_REL; result_path=project_system_path(root, str(WATCHER_RESULT_REL))
    if request_path.exists(): raise RuntimeError('ClearUp watcher request already active')
    try:
        existing=json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else {}
    except Exception:
        existing={}
    request_id=secrets.token_hex(16)
    expires=datetime.now(timezone.utc)+timedelta(seconds=WATCHER_TIMEOUT_SECONDS)
    payload={
        'schema':WATCHER_SCHEMA,
        'request_id':request_id,
        'operation':'clearup_001_delete',
        'clearup_id':CLEARUP_ID,
        'release_version':'32.5.7',
        'created_at':datetime.now(timezone.utc).isoformat(),
        'expires_at':expires.isoformat(),
        'roots':list(ROOTS),
        'expected_rows':live_rows,
        'staging_relative':STAGING_REL.as_posix(),
        'result_path':result_path.relative_to(root).as_posix(),
    }
    _atomic_json(request_path,payload)
    deadline=time.monotonic()+WATCHER_TIMEOUT_SECONDS
    try:
        while time.monotonic()<deadline:
            if result_path.is_file():
                try: response=json.loads(result_path.read_text(encoding='utf-8'))
                except Exception: response={}
                if isinstance(response,dict) and response.get('request_id')==request_id:
                    if response.get('schema')!=WATCHER_RESULT_SCHEMA:
                        raise RuntimeError('ClearUp watcher result schema mismatch')
                    if response.get('status')!='completed':
                        raise RuntimeError('ClearUp watcher delete failed: '+str(response.get('error') or response.get('status')))
                    result=response.get('result')
                    if not isinstance(result,dict): raise RuntimeError('ClearUp watcher result missing')
                    if result.get('delete_performed') is not True: raise RuntimeError('ClearUp watcher did not prove deletion')
                    return result
            time.sleep(0.25)
        raise RuntimeError('ClearUp watcher delete timeout')
    finally:
        try:
            if request_path.is_file():
                current=json.loads(request_path.read_text(encoding='utf-8'))
                if current.get('request_id')==request_id: request_path.unlink(missing_ok=True)
        except Exception:
            pass


def apply_clearup_001(project_root: Path|str, *, explicit_user_text: str, source: str) -> dict[str,Any]:
    root=Path(project_root).resolve()
    if source != 'mcp_remote': raise RuntimeError('ClearUp_001 requires chat/MCP user approval')
    if _token(explicit_user_text) not in AFFIRMATIVE: raise RuntimeError('explicit user approval missing')
    if (root/'App/VERSIE.txt').read_text(encoding='utf-8').strip() != '32.5.7':
        raise RuntimeError('ClearUp_001 chat apply requires active 32.5.7')
    _release_idle(root)
    _dependency_guard(root)
    live=_collect(root); staged=_staging_rows(root)
    if live != staged: raise RuntimeError('recovery/live tree mismatch; nothing removed')
    mailbox_before=_snapshot_release_dirs(root)
    result=_watcher_delete(root,live_rows=live,release_mailbox_before=mailbox_before)
    remaining=[rel for rel in ROOTS if _safe(root,rel).exists()]
    if remaining: raise RuntimeError('ClearUp readback failed: '+repr(remaining))
    mailbox_after=_snapshot_release_dirs(root)
    if mailbox_after != mailbox_before: raise RuntimeError('incoming/processing changed during ClearUp; fail closed')
    out_payload={
        'schema':'energie_clearup_chat_apply_v2','status':'GREEN','clearup_id':CLEARUP_ID,
        'removed':list(ROOTS),'removed_count':len(ROOTS),'delete_performed':True,
        'recovery_reverified':True,'live_tree_reverified':True,
        'release_controller_safe':True,'processing_untouched':True,'incoming_untouched':True,
        'watcher_privileged_executor':True,'watcher_result':result,
    }
    out=root/RESULT_REL; _atomic_json(out,out_payload)
    return out_payload
