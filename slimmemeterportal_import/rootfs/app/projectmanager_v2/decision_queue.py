from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json

PROTECTED_DECISION_KINDS = {
    'PRODUCTION_DEPLOY',
    'ARCHITECTURE_CHANGE',
    'PAID_COMMITMENT',
    'PURCHASE',
    'SAFETY_UNCERTAINTY',
}


class DecisionQueue:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema': 1, 'items': []})

    def _save(self, data):
        atomic_write_json(self.path, data)

    def request(self, kind: str, question: str, *, fingerprint: str = None, context: dict = None):
        if kind not in PROTECTED_DECISION_KINDS:
            raise ValueError(f'unsupported decision kind: {kind}')
        data = self._load()
        if fingerprint:
            for item in data.get('items', []):
                if item.get('fingerprint') == fingerprint and item.get('status') == 'PENDING':
                    return item
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
        return item

    def pending(self):
        return [item for item in self._load().get('items', []) if item.get('status') == 'PENDING']

    def get(self, item_id: str):
        for item in self._load().get('items', []):
            if item.get('id') == item_id:
                return item
        raise KeyError(item_id)

    def resolve(self, item_id: str, *, approved: bool, approved_by: str):
        data = self._load()
        for item in data.get('items', []):
            if item.get('id') == item_id:
                item['status'] = 'APPROVED' if approved else 'REJECTED'
                item['approved_by'] = approved_by
                item['updated_at'] = datetime.now(timezone.utc).isoformat()
                self._save(data)
                return item
        raise KeyError(item_id)
