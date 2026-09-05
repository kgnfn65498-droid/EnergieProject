from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json

VALID_SEVERITIES = {'GREEN', 'ORANGE', 'RED'}
VALID_STATUSES = {'OPEN', 'RESOLVED'}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    return all(isinstance(item, dict) and item.get('status') in VALID_STATUSES for item in data.get('items', []))


class IssueStore:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema': 1, 'items': []}, recover_corrupt=True, validator=_valid_payload)

    def _save(self, data):
        atomic_write_json(self.path, data)

    def open(self, fingerprint: str, *, severity: str, title: str, details: dict):
        severity = severity if severity in VALID_SEVERITIES else 'ORANGE'
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        for item in data.get('items', []):
            if item.get('fingerprint') == fingerprint and item.get('status') == 'OPEN':
                item['last_seen_at'] = now
                item['severity'] = severity
                item['title'] = title
                item['details'] = details or {}
                self._save(data)
                return dict(item)
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
        return dict(item)

    def resolve(self, issue_id: str, *, resolution: str):
        data = self._load()
        for item in data.get('items', []):
            if item.get('id') == issue_id:
                item['status'] = 'RESOLVED'
                item['resolution'] = resolution
                item['resolved_at'] = datetime.now(timezone.utc).isoformat()
                self._save(data)
                return dict(item)
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
                changed.append(dict(item))
        if changed:
            self._save(data)
        return changed

    def open_items(self):
        return [dict(item) for item in self._load().get('items', []) if item.get('status') == 'OPEN']
