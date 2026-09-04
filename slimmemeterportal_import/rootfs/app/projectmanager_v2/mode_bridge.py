import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

VALID_MODES={'USER','DEVELOPMENT','MAINTENANCE'}


class ModeBridge:
    def __init__(self, command_path):
        self.command_path=Path(command_path)

    def request_base_mode(self, mode: str, *, reason: str='', issued_by: str='projectmanager') -> dict:
        mode=str(mode).upper().strip()
        if mode not in VALID_MODES:
            raise ValueError(f'invalid mode: {mode}')
        payload={
            'schema_version':1,
            'request_id':f'{issued_by}-{uuid4().hex[:12]}',
            'action':'set_base',
            'requested_mode':mode,
            'reason':reason,
            'issued_by':issued_by,
            'confirmed_by_user':False,
            'created_at':datetime.now(timezone.utc).isoformat(),
        }
        self._atomic_write(payload)
        return payload

    def reconcile(self, *, reason: str='projectmanager reconciliation', issued_by: str='projectmanager') -> dict:
        payload={
            'schema_version':1,
            'request_id':f'{issued_by}-{uuid4().hex[:12]}',
            'action':'reconcile',
            'reason':reason,
            'issued_by':issued_by,
            'confirmed_by_user':False,
            'created_at':datetime.now(timezone.utc).isoformat(),
        }
        self._atomic_write(payload)
        return payload

    def _atomic_write(self, payload):
        path=self.command_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp=path.with_name(path.name+f'.tmp.{os.getpid()}.{uuid4().hex[:6]}')
        tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        os.replace(tmp,path)
