from __future__ import annotations
from system_path_contract import project_system_path
import json,os
from datetime import datetime,timezone
from pathlib import Path

def write_ha_runtime_marker(project_root:Path|str,version:str)->dict:
    root=Path(project_root);path=project_system_path(root, 'Inbox/ha_runtime/current.json');path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise RuntimeError('ha runtime marker path unsafe')
    payload={'schema':'energie_ha_runtime_v1','version':str(version),'pid':os.getpid(),
             'started_at':datetime.now(timezone.utc).isoformat()}
    tmp=path.with_name(path.name+f'.tmp-{os.getpid()}')
    try:tmp.write_text(json.dumps(payload,sort_keys=True)+'\n',encoding='utf-8');os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)
    return payload
