from datetime import datetime, timedelta, timezone
from pathlib import Path
from persistence import atomic_write_json, load_json

VALID_EXECUTORS = {'official_monitor', 'handoff'}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    return all(
        isinstance(item, dict)
        and item.get('key')
        and item.get('executor', 'handoff') in VALID_EXECUTORS
        for item in data.get('items', [])
    )


class ResearchQueue:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema': 1, 'items': []}, recover_corrupt=True, validator=_valid_payload)

    def _save(self, data):
        atomic_write_json(self.path, data)

    def upsert(self, key, category, *, due_at, priority, cadence_days=30, query=None, executor='handoff', source_ids=None):
        if executor not in VALID_EXECUTORS:
            raise ValueError(f'invalid research executor: {executor}')
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
            'executor': executor,
            'source_ids': list(source_ids or []),
        })
        self._save(data)
        return dict(item)

    def get(self, key):
        for item in self._load().get('items', []):
            if item.get('key') == key:
                return dict(item)
        raise KeyError(key)

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]

    def due(self, *, now=None, executor=None):
        now = now or datetime.now(timezone.utc)
        result = []
        for item in self._load().get('items', []):
            if executor and item.get('executor', 'handoff') != executor:
                continue
            try:
                due_at = datetime.fromisoformat(str(item['due_at']).replace('Z', '+00:00'))
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)
            except (KeyError, TypeError, ValueError):
                continue
            if due_at <= now:
                result.append(dict(item))
        return sorted(result, key=lambda x: (x.get('priority', 99), x.get('due_at', ''), x.get('key', '')))

    def complete(self, key, *, evidence_ref, now=None):
        now = now or datetime.now(timezone.utc)
        data = self._load()
        for item in data.get('items', []):
            if item.get('key') == key:
                item['last_completed_at'] = now.isoformat()
                item['last_evidence_ref'] = evidence_ref
                item['due_at'] = (now + timedelta(days=int(item.get('cadence_days', 30)))).isoformat()
                self._save(data)
                return dict(item)
        raise KeyError(key)

    def defer(self, key, *, now=None, hours=6, reason='no_evidence_yet'):
        now = now or datetime.now(timezone.utc)
        data = self._load()
        for item in data.get('items', []):
            if item.get('key') == key:
                item['last_attempt_at'] = now.isoformat()
                item['last_attempt_reason'] = reason
                item['due_at'] = (now + timedelta(hours=max(1, int(hours)))).isoformat()
                self._save(data)
                return dict(item)
        raise KeyError(key)
