from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json
from secret_guard import redact

COMMAND_STATUSES = {
    'PENDING', 'PROCESSING', 'WAITING_APPROVAL', 'APPROVED_READY',
    'APPROVED_WAITING_EXECUTOR', 'INTERRUPTED', 'DONE', 'FAILED', 'CANCELLED',
}
PENDING_STATUSES = {
    'PENDING', 'PROCESSING', 'WAITING_APPROVAL', 'APPROVED_READY',
    'APPROVED_WAITING_EXECUTOR',
}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    return all(isinstance(item, dict) and item.get('status') in COMMAND_STATUSES for item in data.get('items', []))


class CommandStore:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(
            self.path,
            default={'schema': 1, 'items': []},
            recover_corrupt=True,
            validator=_valid_payload,
        )

    def _save(self, data):
        atomic_write_json(self.path, data)

    def enqueue(self, command: dict):
        data = self._load()
        incoming = redact(dict(command or {}))
        ingress_id = str(incoming.get('ingress_id') or '').strip()
        if ingress_id:
            for existing in data.get('items', []):
                if existing.get('ingress_id') == ingress_id:
                    return dict(existing)
        now = datetime.now(timezone.utc).isoformat()
        item = incoming
        item.update({'id': uuid4().hex, 'status': 'PENDING', 'created_at': now, 'updated_at': now})
        data.setdefault('items', []).append(item)
        self._save(data)
        return dict(item)

    def claim_next(self):
        data = self._load()
        for item in data.get('items', []):
            if item.get('status') in {'PENDING', 'APPROVED_READY'}:
                item['status'] = 'PROCESSING'
                item['updated_at'] = datetime.now(timezone.utc).isoformat()
                self._save(data)
                return dict(item)
        return None

    def wait_for_approval(self, item_id: str, *, decision_id: str):
        return self._finish(item_id, 'WAITING_APPROVAL', approval_decision_id=decision_id)

    def mark_approved_ready(self, item_id: str):
        return self._finish(item_id, 'APPROVED_READY')

    def wait_for_executor(self, item_id: str, *, approved_action: dict, result: dict):
        return self._finish(
            item_id,
            'APPROVED_WAITING_EXECUTOR',
            approved_action=approved_action,
            result=result,
        )

    def cancel(self, item_id: str, *, reason: str):
        return self._finish(item_id, 'CANCELLED', cancellation_reason=reason)

    def recover_interrupted(self):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        changed = []
        for item in data.get('items', []):
            if item.get('status') == 'PROCESSING':
                item.update({
                    'status': 'INTERRUPTED',
                    'error': 'manager_restart_during_processing',
                    'updated_at': now,
                })
                changed.append(dict(item))
        if changed:
            self._save(data)
        return changed

    def complete(self, item_id: str, *, result: dict):
        return self._finish(item_id, 'DONE', result=result)

    def fail(self, item_id: str, *, error: str):
        return self._finish(item_id, 'FAILED', error=error)

    def _finish(self, item_id, status, **fields):
        if status not in COMMAND_STATUSES:
            raise ValueError(f'invalid command status: {status}')
        data = self._load()
        for item in data.get('items', []):
            if item.get('id') == item_id:
                item['status'] = status
                item.update(redact(fields))
                item['updated_at'] = datetime.now(timezone.utc).isoformat()
                self._save(data)
                return dict(item)
        raise KeyError(item_id)

    def get(self, item_id: str):
        for item in self._load().get('items', []):
            if item.get('id') == item_id:
                return dict(item)
        raise KeyError(item_id)

    def by_status(self, *statuses):
        wanted = set(statuses)
        return [dict(item) for item in self._load().get('items', []) if item.get('status') in wanted]

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]

    def pending_count(self):
        return sum(1 for item in self._load().get('items', []) if item.get('status') in PENDING_STATUSES)
