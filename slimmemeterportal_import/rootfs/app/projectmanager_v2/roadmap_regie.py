from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json

VALID_STATUSES = {'OPEN', 'ACTIVE', 'DONE', 'BLOCKED'}
VALID_EXECUTORS = {'handoff', 'embedded'}

DEFAULT_ITEMS = (
    {'key': 'ngrok-assessment', 'title': 'ngrok structurele noodzaak en endpointbeveiliging beoordelen', 'priority': 3, 'auto_select': True, 'mode': 'USER', 'executor': 'handoff'},
    {'key': 'subscription-independence', 'title': 'Abonnementsonafhankelijkheid vóór Cowork-pilot analyseren', 'priority': 4, 'auto_select': True, 'mode': 'USER', 'executor': 'handoff'},
    {'key': 'cowork-pilot', 'title': 'Cowork-pilot voorbereiden en uitvoeren', 'priority': 5, 'auto_select': True, 'mode': 'DEVELOPMENT', 'executor': 'handoff'},
    {'key': 'nomad-next', 'title': 'Nomad verdere ontwikkeling', 'priority': 6, 'auto_select': True, 'mode': 'DEVELOPMENT', 'executor': 'handoff'},
    {'key': 'month-import-next', 'title': 'Maandimport stabiliteit en autonomie verder afronden', 'priority': 7, 'auto_select': True, 'mode': 'DEVELOPMENT', 'executor': 'handoff'},
)


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    return all(
        isinstance(item, dict)
        and item.get('key')
        and item.get('status') in VALID_STATUSES
        and item.get('executor', 'handoff') in VALID_EXECUTORS
        for item in data.get('items', [])
    )


class RoadmapRegie:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema': 1, 'items': []}, recover_corrupt=True, validator=_valid_payload)

    def _save(self, data):
        atomic_write_json(self.path, data)

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]

    def seed_defaults(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        data = self._load()
        by_key = {item.get('key'): item for item in data.get('items', [])}
        changed = False
        for spec in DEFAULT_ITEMS:
            if spec['key'] in by_key:
                continue
            item = dict(spec)
            item.update({'status': 'OPEN', 'created_at': now.isoformat(), 'updated_at': now.isoformat()})
            data.setdefault('items', []).append(item)
            changed = True
        if changed:
            self._save(data)
        return data

    def next_open(self, *, mode=None):
        items = [
            item for item in self._load().get('items', [])
            if item.get('status') == 'OPEN'
            and item.get('auto_select') is True
            and (mode is None or item.get('mode') == mode)
        ]
        if not items:
            return None
        return dict(sorted(items, key=lambda item: (item.get('priority', 99), item.get('created_at', ''), item.get('key', '')))[0])

    def mark_active(self, key, task_id):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        for item in data.get('items', []):
            if item.get('key') == key:
                item.update({'status': 'ACTIVE', 'task_id': task_id, 'updated_at': now})
                self._save(data)
                return dict(item)
        raise KeyError(key)

    def mark_done_for_task(self, task_id):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        changed = []
        for item in data.get('items', []):
            if item.get('task_id') == task_id and item.get('status') == 'ACTIVE':
                item.update({'status': 'DONE', 'updated_at': now})
                changed.append(dict(item))
        if changed:
            self._save(data)
        return changed
