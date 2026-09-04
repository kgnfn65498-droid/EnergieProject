from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json
from secret_guard import redact


class CommandStore:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema':1,'items':[]})

    def _save(self, data):
        atomic_write_json(self.path, data)

    def enqueue(self, command: dict):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        item = redact(dict(command or {}))
        item.update({'id':uuid4().hex,'status':'PENDING','created_at':now,'updated_at':now})
        data.setdefault('items', []).append(item)
        self._save(data)
        return item

    def claim_next(self):
        data = self._load()
        for item in data.get('items', []):
            if item.get('status') == 'PENDING':
                item['status'] = 'PROCESSING'
                item['updated_at'] = datetime.now(timezone.utc).isoformat()
                self._save(data)
                return item
        return None

    def complete(self, item_id: str, *, result: dict):
        return self._finish(item_id, 'DONE', result=result)

    def fail(self, item_id: str, *, error: str):
        return self._finish(item_id, 'FAILED', error=error)

    def _finish(self, item_id, status, **fields):
        data = self._load()
        for item in data.get('items', []):
            if item.get('id') == item_id:
                item['status'] = status
                item.update(redact(fields))
                item['updated_at'] = datetime.now(timezone.utc).isoformat()
                self._save(data)
                return item
        raise KeyError(item_id)

    def get(self, item_id: str):
        for item in self._load().get('items', []):
            if item.get('id') == item_id:
                return item
        raise KeyError(item_id)

    def pending_count(self):
        return sum(1 for item in self._load().get('items', []) if item.get('status') == 'PENDING')
