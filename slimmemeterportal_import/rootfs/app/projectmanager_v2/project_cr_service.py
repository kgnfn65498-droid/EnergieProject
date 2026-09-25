from __future__ import annotations
from system_path_contract import project_system_path

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
    STALE_WORKER_MARKER_SECONDS=30*60
    REQUEST_SCHEMA='energie_project_cr_local_request_v1'
    RESULT_SCHEMA='energie_project_cr_local_result_v1'
    OPERATION='project_cr_create'

    def __init__(self, project_root: Path | str, *, timeout_seconds: float=20*60, poll_seconds: float=.25):
        self.project_root=Path(project_root)
        self.bridge_root=project_system_path(self.project_root, 'Inbox/project_cr_local')
        self.request_path=self.bridge_root/'request.json'
        self.result_path=self.bridge_root/'result.json'
        self.timeout_seconds=max(.1,float(timeout_seconds)); self.poll_seconds=max(.005,float(poll_seconds))

    @staticmethod
    def _load(path: Path) -> dict[str, Any] | None:
        try: value=json.loads(path.read_text(encoding='utf-8'))
        except (OSError,json.JSONDecodeError): return None
        return value if isinstance(value,dict) else None

    def _worker_marker_active(self) -> bool:
        marker=self.bridge_root/'project_cr_local_worker.pid'
        if not marker.is_file() or marker.is_symlink():
            return False
        content=marker.read_text(encoding='utf-8',errors='ignore').strip()
        if not content:
            return False
        try:
            age=max(0.0,time.time()-marker.stat().st_mtime)
        except OSError:
            return True
        if age <= self.STALE_WORKER_MARKER_SECONDS:
            return True
        fence=self.bridge_root/'single_worker_recovery_fence.json'
        if fence.is_symlink():
            raise RuntimeError('onveilige Project-CR recovery fence')
        request=self._load(self.request_path) or {}
        payload={
            'schema':'energie_project_cr_single_worker_recovery_v1',
            'status':'RECOVERED_STALE_MARKER',
            'reason':'stale_worker_marker_recovered',
            'marker_value':content,
            'marker_age_seconds':age,
            'request_id':str(request.get('request_id') or ''),
            'recovered_at':datetime.now(timezone.utc).isoformat(),
            'delete_performed':False,
        }
        _atomic_text(fence,json.dumps(payload,ensure_ascii=False,sort_keys=True)+'\n')
        marker.unlink(missing_ok=True)
        return False

    def _archive_bridge_evidence(self, *, reason: str) -> None:
        if self._worker_marker_active():
            raise RuntimeError('EnergieProject CR bridge heeft actieve worker; fail-closed')
        evidence=self.bridge_root/'evidence'
        evidence.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        token=secrets.token_hex(4)
        for label,path in (('request',self.request_path),('result',self.result_path)):
            if not path.is_file() or path.is_symlink():
                continue
            target=evidence/f'{stamp}-{label}-{reason}-{token}.json'
            os.replace(path,target)

    def _result_identity_valid(self, result: dict[str, Any], *, request_id: str, command: str, version: str) -> bool:
        if result.get('schema') != self.RESULT_SCHEMA or result.get('operation') != self.OPERATION:
            return False
        if str(result.get('request_id') or '') != request_id or str(result.get('version') or '') != version:
            return False
        result_command=str(result.get('command_id') or '').strip()
        if command and result_command != command:
            return False
        return True

    def create(self, *, command_id: str = '', expected_release: str = '', wait_for_result: bool = True) -> dict[str, Any]:
        version=(self.project_root/'App/VERSIE.txt').read_text(encoding='utf-8').strip()
        if not version or any(ch not in '0123456789.' for ch in version):
            raise RuntimeError('actuele runtimeversie ontbreekt of is ongeldig')
        expected = str(expected_release or '').strip()
        if expected and expected != version:
            raise RuntimeError(f'EnergieProject CR release mismatch: command={expected} actief={version}')
        command = str(command_id or '').strip()
        self.bridge_root.mkdir(parents=True,exist_ok=True)
        if self.request_path.is_symlink() or self.result_path.is_symlink():
            raise RuntimeError('onveilige EnergieProject CR bridge-path')

        request = self._load(self.request_path)
        if request:
            if request.get('schema') != self.REQUEST_SCHEMA or request.get('operation') != self.OPERATION:
                raise RuntimeError('EnergieProject CR bridge is bezet door ongeldig request')
            if request.get('expected_runtime_version') != version:
                self._archive_bridge_evidence(reason='stale-release')
                request=None
            else:
                existing_command = str(request.get('command_id') or '').strip()
                if command and existing_command and existing_command != command:
                    raise RuntimeError('EnergieProject CR bridge is bezet door ander command')
        if request:
            request_id = str(request.get('request_id') or '').strip()
            if not request_id:
                raise RuntimeError('EnergieProject CR bridge request-id ontbreekt')
        else:
            request_id=secrets.token_hex(16)
            # Preserve an orphan result unless it already proves the exact
            # identity of the request we are about to materialize. This keeps
            # restart/idempotence compatibility without allowing stale evidence
            # to satisfy a different request.
            orphan=self._load(self.result_path)
            if self.result_path.is_file() and not (
                orphan and self._result_identity_valid(orphan, request_id=request_id, command=command, version=version)
            ):
                self._archive_bridge_evidence(reason='orphan-result')
            request={'schema':self.REQUEST_SCHEMA,'request_id':request_id,'operation':self.OPERATION,
                     'expected_runtime_version':version,'created_at':datetime.now(timezone.utc).isoformat()}
            if command:
                request['command_id'] = command
            _atomic_text(self.request_path,json.dumps(request,ensure_ascii=False,sort_keys=True)+'\n')

        result=self._load(self.result_path)
        if not result or result.get('request_id') != request_id:
            if not wait_for_result:
                return {
                    'status': 'PENDING', 'ok': None, 'request_id': request_id,
                    'command_id': command or str(request.get('command_id') or ''),
                    'version': version, 'executed': False,
                }
            deadline=time.monotonic()+self.timeout_seconds
            while time.monotonic()<deadline:
                result=self._load(self.result_path)
                if result and result.get('request_id') == request_id:
                    break
                time.sleep(self.poll_seconds)
            else:
                raise RuntimeError('EnergieProject CR lokale executor timeout; fail-closed')
        if not self._result_identity_valid(result, request_id=request_id, command=command, version=version):
            raise RuntimeError('EnergieProject CR lokaal resultaat ongeldig')
        if not (result.get('status')=='GREEN' and result.get('ok') is True and result.get('deep_verified') is True):
            raise RuntimeError(str(result.get('error') or 'EnergieProject CR lokale executor rapporteert RED'))
        return result
