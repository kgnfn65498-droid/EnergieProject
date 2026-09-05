from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json

PROTECTED_DECISION_KINDS = {
    'MODE_CHANGE',
    'PRODUCTION_DEPLOY',
    'ARCHITECTURE_CHANGE',
    'PAID_COMMITMENT',
    'PURCHASE',
    'SAFETY_UNCERTAINTY',
}
VALID_STATUSES = {'PENDING', 'APPROVED', 'REJECTED'}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    for item in data.get('items', []):
        if not isinstance(item, dict):
            return False
        if item.get('status') not in VALID_STATUSES:
            return False
        if item.get('kind') not in PROTECTED_DECISION_KINDS:
            return False
    return True


class DecisionQueue:
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

    def request(self, kind: str, question: str, *, fingerprint: str = None, context: dict = None):
        if kind not in PROTECTED_DECISION_KINDS:
            raise ValueError(f'unsupported decision kind: {kind}')
        data = self._load()
        if fingerprint:
            for item in data.get('items', []):
                if item.get('fingerprint') == fingerprint and item.get('status') in {'PENDING', 'APPROVED'}:
                    return dict(item)
        now = datetime.now(timezone.utc).isoformat()
        item = {
            'id': uuid4().hex,
            'kind': kind,
            'question': question,
            'fingerprint': fingerprint,
            'context': context or {},
            'status': 'PENDING',
            'created_at': now,
            'updated_at': now,
        }
        data.setdefault('items', []).append(item)
        self._save(data)
        return dict(item)

    def pending(self):
        return [dict(item) for item in self._load().get('items', []) if item.get('status') == 'PENDING']

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]

    def get(self, item_id: str):
        for item in self._load().get('items', []):
            if item.get('id') == item_id:
                return dict(item)
        raise KeyError(item_id)

    def resolve(self, item_id: str, *, approved: bool, approved_by: str):
        if approved_by != 'Peter':
            raise ValueError('only Peter may resolve protected Projectmanager decisions')
        data = self._load()
        for item in data.get('items', []):
            if item.get('id') == item_id:
                if item.get('status') != 'PENDING':
                    return dict(item)
                item['status'] = 'APPROVED' if approved else 'REJECTED'
                item['approved_by'] = approved_by
                item['resolved_at'] = datetime.now(timezone.utc).isoformat()
                item['updated_at'] = item['resolved_at']
                self._save(data)
                return dict(item)
        raise KeyError(item_id)
