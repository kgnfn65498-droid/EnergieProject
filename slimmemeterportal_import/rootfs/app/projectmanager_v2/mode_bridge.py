import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

VALID_MODES={'USER','DEVELOPMENT','MAINTENANCE'}


class ModeBridge:
    def __init__(self, command_path):
        self.command_path=Path(command_path)

    def request_base_mode(self, mode: str, *, reason: str='', issued_by: str='projectmanager', confirmed_by_user: bool=False) -> dict:
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
            'confirmed_by_user':bool(confirmed_by_user),
            'created_at':datetime.now(timezone.utc).isoformat(),
        }
        self._atomic_write(payload)
        return payload

    def request_transition_owned_temporary_maintenance(
        self, *, generation_id: str, ticket_request_id: str, idempotency_key: str,
        command_id: str, project_cr_request_id: str, release_owner: str,
        approval_reference: str, confirmed_by_user: bool,
    ) -> dict:
        """Request the one fenced mode change consumed by the release coordinator."""
        fence = {
            'generation_id': generation_id, 'phase': 'PROJECT_CR',
            'phase_status': 'WAITING_RESULT', 'lifecycle_state': 'ACTIVE',
            'ticket_request_id': ticket_request_id, 'idempotency_key': idempotency_key,
            'executor_name': 'project_cr_create', 'release_owner': release_owner,
            'command_id': command_id, 'project_cr_request_id': project_cr_request_id,
            'approval_reference': approval_reference,
        }
        if not confirmed_by_user or any(not str(value).strip() for value in fence.values()):
            raise ValueError('complete explicit transition-owned maintenance approval is required')
        payload = {
            'schema_version': 1, 'request_id': f'transition-owned-{uuid4().hex[:12]}',
            'action': 'transition_owned_temporary_maintenance',
            'requested_mode': 'MAINTENANCE', 'issued_by': 'release_transition_recovery',
            'confirmed_by_user': True, 'transition_fence': fence,
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
