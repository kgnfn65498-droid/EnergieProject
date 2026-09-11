from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f'onveilig bridgepad: {path}')
    tmp=path.with_name(f'.{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}')
    try:
        with tmp.open('x',encoding='utf-8') as h:
            h.write(text); h.flush(); os.fsync(h.fileno())
        os.replace(tmp,path)
    finally:
        tmp.unlink(missing_ok=True)


class ConfiguredProjectCrService:
    REQUEST_SCHEMA='energie_project_cr_local_request_v1'
    RESULT_SCHEMA='energie_project_cr_local_result_v1'
    OPERATION='project_cr_create'

    def __init__(self, project_root: Path | str, *, timeout_seconds: float=20*60, poll_seconds: float=.25):
        self.project_root=Path(project_root)
        self.bridge_root=self.project_root/'Inbox/project_cr_local'
        self.request_path=self.bridge_root/'request.json'
        self.result_path=self.bridge_root/'result.json'
        self.timeout_seconds=max(.1,float(timeout_seconds)); self.poll_seconds=max(.005,float(poll_seconds))

    @staticmethod
    def _load(path: Path) -> dict[str, Any] | None:
        try: value=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,json.JSONDecodeError): return None
        return value if isinstance(value,dict) else None

    def create(self) -> dict[str, Any]:
        version=(self.project_root/'App/VERSIE.txt').read_text(encoding='utf-8').strip()
        if not version or any(ch not in '0123456789.' for ch in version):
            raise RuntimeError('actuele runtimeversie ontbreekt of is ongeldig')
        self.bridge_root.mkdir(parents=True,exist_ok=True)
        if self.request_path.is_symlink() or self.result_path.is_symlink():
            raise RuntimeError('onveilige EnergieProject CR bridge-path')
        request_id=secrets.token_hex(16)
        request={'schema':self.REQUEST_SCHEMA,'request_id':request_id,'operation':self.OPERATION,
                 'expected_runtime_version':version,'created_at':datetime.now(timezone.utc).isoformat()}
        _atomic_text(self.request_path,json.dumps(request,ensure_ascii=False,sort_keys=True)+'\n')
        deadline=time.monotonic()+self.timeout_seconds
        while time.monotonic()<deadline:
            result=self._load(self.result_path)
            if not result or result.get('request_id')!=request_id:
                time.sleep(self.poll_seconds); continue
            if result.get('schema')!=self.RESULT_SCHEMA or result.get('version')!=version:
                raise RuntimeError('EnergieProject CR lokaal resultaat ongeldig')
            if not (result.get('status')=='GREEN' and result.get('ok') is True and result.get('deep_verified') is True):
                raise RuntimeError(str(result.get('error') or 'EnergieProject CR lokale executor rapporteert RED'))
            return result
        raise RuntimeError('EnergieProject CR lokale executor timeout; fail-closed')
