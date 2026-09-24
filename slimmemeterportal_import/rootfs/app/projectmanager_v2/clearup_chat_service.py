from __future__ import annotations

import hashlib
import json
import os
import shutil
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
MANIFEST_REL = STAGING_REL / 'CLEARUP_MANIFEST.json'
RESULT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/State/ClearUp_001_apply.json')


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
        # staging stores the original Inbox child directly beneath ClearUp_001
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
    current=root/'Inbox/release_controller/current.json'
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


def apply_clearup_001(project_root: Path|str, *, explicit_user_text: str, source: str) -> dict[str,Any]:
    root=Path(project_root).resolve()
    if source != 'mcp_remote': raise RuntimeError('ClearUp_001 requires chat/MCP user approval')
    if _token(explicit_user_text) not in AFFIRMATIVE: raise RuntimeError('explicit user approval missing')
    if (root/'App/VERSIE.txt').read_text(encoding='utf-8').strip() != '32.5.6':
        raise RuntimeError('ClearUp_001 chat apply requires active 32.5.6')
    _release_idle(root)
    _dependency_guard(root)
    live=_collect(root)
    staged=_staging_rows(root)
    if live != staged:
        raise RuntimeError('recovery/live tree mismatch; nothing removed')
    removed=[]
    for rel in ROOTS:
        p=_safe(root,rel)
        if p.is_dir(): shutil.rmtree(p)
        elif p.is_file(): p.unlink()
        else: raise RuntimeError(f'candidate disappeared before apply: {rel}')
        removed.append(rel)
    remaining=[rel for rel in ROOTS if _safe(root,rel).exists()]
    if remaining: raise RuntimeError('ClearUp readback failed: '+repr(remaining))
    payload={'schema':'energie_clearup_chat_apply_v1','status':'GREEN','clearup_id':CLEARUP_ID,
             'removed':removed,'removed_count':len(removed),'delete_performed':True,
             'recovery_reverified':True,'live_tree_reverified':True,
             'release_controller_safe':True,'processing_untouched':True}
    out=root/RESULT_REL; out.parent.mkdir(parents=True,exist_ok=True)
    tmp=out.with_suffix('.tmp'); tmp.write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8'); os.replace(tmp,out)
    return payload
