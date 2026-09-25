from __future__ import annotations
from system_path_contract import project_system_path
import json,stat
from pathlib import Path
VALID_PHASES={'DETECTED','VERIFIED','PUBLISHING','INSTALLING','INSTALLED','RUNTIME_ALIGNING','VERIFYING','ACCEPTED','COMPLETE'}
VALID_STATUS={'ACTIVE','WAITING','BLOCKED','COMPLETE','ROLLED_BACK'}
def load_release_controller_state(project_root:Path|str):
    path=project_system_path(Path(project_root), 'Inbox/release_controller/current.json')
    try:st=path.lstat()
    except FileNotFoundError:return None
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):raise RuntimeError('release controller state unsafe')
    value=json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(value,dict):raise RuntimeError('release controller state invalid')
    if str(value.get('phase') or '') not in VALID_PHASES:raise RuntimeError('release controller phase invalid')
    if str(value.get('status') or '') not in VALID_STATUS:raise RuntimeError('release controller status invalid')
    return value
def release_active(value):
    return bool(value and str(value.get('status') or '') not in {'COMPLETE','ROLLED_BACK'})
def release_view(value):
    if not value:return {'active':False,'status':'IDLE','phase':'IDLE'}
    return {k:value.get(k) for k in ('release_id','generation','from_version','to_version','artifact_sha256','phase','status','step','total','blocker','required_action','wait_reason')} | {'active':release_active(value)}
