from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json


class IssueStore:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema':1,'items':[]})

    def _save(self, data):
        atomic_write_json(self.path, data)

    def open(self, fingerprint: str, *, severity: str, title: str, details: dict):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        for item in data.get('items', []):
            if item.get('fingerprint') == fingerprint and item.get('status') == 'OPEN':
                item['last_seen_at'] = now
                item['severity'] = severity
                item['title'] = title
                item['details'] = details or {}
                self._save(data)
                return item
        item = {
            'id': uuid4().hex,
            'fingerprint': fingerprint,
            'severity': severity,
            'title': title,
            'details': details or {},
            'status': 'OPEN',
            'created_at': now,
            'last_seen_at': now,
        }
        data.setdefault('items', []).append(item)
        self._save(data)
        return item

    def resolve(self, issue_id: str, *, resolution: str):
        data = self._load()
        for item in data.get('items', []):
            if item.get('id') == issue_id:
                item['status'] = 'RESOLVED'
                item['resolution'] = resolution
                item['resolved_at'] = datetime.now(timezone.utc).isoformat()
                self._save(data)
                return item
        raise KeyError(issue_id)

    def resolve_fingerprint(self, fingerprint: str, *, resolution: str):
        data = self._load()
        changed = []
        now = datetime.now(timezone.utc).isoformat()
        for item in data.get('items', []):
            if item.get('fingerprint') == fingerprint and item.get('status') == 'OPEN':
                item['status'] = 'RESOLVED'
                item['resolution'] = resolution
                item['resolved_at'] = now
                changed.append(item)
        if changed:
            self._save(data)
        return changed

    def open_items(self):
        return [item for item in self._load().get('items', []) if item.get('status') == 'OPEN']
