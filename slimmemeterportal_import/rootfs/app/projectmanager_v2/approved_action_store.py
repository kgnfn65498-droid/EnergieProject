from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json
from secret_guard import redact

VALID_STATUSES = {
    'APPROVED_AWAITING_SAFETY_OR_EXECUTOR',
    'DONE',
    'CANCELLED',
}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    return all(
        isinstance(item, dict)
        and item.get('id')
        and item.get('decision_id')
        and item.get('command_id')
        and item.get('status') in VALID_STATUSES
        for item in data.get('items', [])
    )


class ApprovedActionStore:
    """Persistent handoff for actions that Peter approved but PM may not execute.

    The embedded Projectmanager records the approval once. A separate, explicit
    executor may later consume the handoff after its own safety proof. Recording
    the handoff never performs the protected side effect itself.
    """

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

    def add(self, *, decision: dict, command: dict, action: str):
        data = self._load()
        decision_id = str(decision.get('id') or '')
        command_id = str(command.get('id') or '')
        if not decision_id or not command_id:
            raise ValueError('decision_id and command_id are required')
        for item in data.get('items', []):
            if item.get('decision_id') == decision_id and item.get('command_id') == command_id:
                return dict(item)
        now = datetime.now(timezone.utc).isoformat()
        item = redact({
            'id': uuid4().hex,
            'decision_id': decision_id,
            'command_id': command_id,
            'action': action,
            'intent': command.get('intent'),
            'title': command.get('title') or command.get('text') or action,
            'approved_by': decision.get('approved_by'),
            'approved_at': decision.get('resolved_at') or decision.get('updated_at'),
            'status': 'APPROVED_AWAITING_SAFETY_OR_EXECUTOR',
            'created_at': now,
            'updated_at': now,
            'protected_side_effect_executed': False,
        })
        data.setdefault('items', []).append(item)
        self._save(data)
        return dict(item)

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]

    def open_items(self):
        return [
            dict(item) for item in self._load().get('items', [])
            if item.get('status') == 'APPROVED_AWAITING_SAFETY_OR_EXECUTOR'
        ]
