from datetime import datetime, timedelta, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json


class ResearchQueue:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema': 1, 'items': []})

    def _save(self, data):
        atomic_write_json(self.path, data)

    def upsert(self, key: str, category: str, *, due_at, priority: int, cadence_days: int = 30, query: str = None):
        data = self._load()
        due = due_at.isoformat() if hasattr(due_at, 'isoformat') else str(due_at)
        item = next((x for x in data.get('items', []) if x.get('key') == key), None)
        if item is None:
            item = {'key': key}
            data.setdefault('items', []).append(item)
        item.update({
            'category': category,
            'due_at': due,
            'priority': int(priority),
            'cadence_days': int(cadence_days),
            'query': query or key,
        })
        self._save(data)
        return item

    def get(self, key: str):
        for item in self._load().get('items', []):
            if item.get('key') == key:
                return item
        raise KeyError(key)

    def due(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        result = []
        for item in self._load().get('items', []):
            try:
                due_at = datetime.fromisoformat(item['due_at'].replace('Z', '+00:00'))
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            if due_at <= now:
                result.append(item)
        return sorted(result, key=lambda x: (x.get('priority', 99), x.get('due_at', ''), x.get('key', '')))

    def complete(self, key: str, *, evidence_ref: str, now=None):
        now = now or datetime.now(timezone.utc)
        data = self._load()
        for item in data.get('items', []):
            if item.get('key') == key:
                item['last_completed_at'] = now.isoformat()
                item['last_evidence_ref'] = evidence_ref
                item['due_at'] = (now + timedelta(days=int(item.get('cadence_days', 30)))).isoformat()
                self._save(data)
                return item
        raise KeyError(key)
