from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json
from secret_guard import redact

VALID_STATUSES = {'OPEN', 'DONE', 'BLOCKED', 'CANCELLED'}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    return all(
        isinstance(item, dict)
        and item.get('id')
        and item.get('task_id')
        and item.get('roadmap_key')
        and item.get('status') in VALID_STATUSES
        for item in data.get('items', [])
    )


class HandoffQueue:
    """Persistent single-writer queue for work delegated to an external agent.

    The Projectmanager creates handoffs. External workers only return immutable
    result envelopes through HandoffResultIngress; they never mutate RuntimeV2.
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

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]

    def get(self, handoff_id):
        for item in self._load().get('items', []):
            if item.get('id') == handoff_id:
                return dict(item)
        raise KeyError(handoff_id)

    def by_task(self, task_id):
        for item in self._load().get('items', []):
            if item.get('task_id') == task_id:
                return dict(item)
        return None

    def open_items(self):
        return [dict(item) for item in self._load().get('items', []) if item.get('status') == 'OPEN']

    def ensure_for_task(self, task: dict, roadmap_item: dict):
        existing = self.by_task(task['id'])
        if existing is not None:
            return existing
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        item = redact({
            'id': uuid4().hex,
            'task_id': task['id'],
            'roadmap_key': roadmap_item['key'],
            'title': roadmap_item.get('title') or task.get('title'),
            'goal': task.get('goal') or roadmap_item.get('title'),
            'acceptance': roadmap_item.get('acceptance') or '',
            'priority': int(roadmap_item.get('priority', 5)),
            'status': 'OPEN',
            'created_at': now,
            'updated_at': now,
            'summary': '',
            'evidence_refs': [],
        })
        data.setdefault('items', []).append(item)
        self._save(data)
        return dict(item)

    def complete(self, handoff_id, *, summary, evidence_refs):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        for item in data.get('items', []):
            if item.get('id') != handoff_id:
                continue
            if item.get('status') == 'DONE':
                return dict(item)
            if item.get('status') not in {'OPEN'}:
                raise ValueError(f"handoff_not_open:{item.get('status')}")
            item.update({
                'status': 'DONE',
                'summary': str(summary),
                'evidence_refs': list(evidence_refs),
                'completed_at': now,
                'updated_at': now,
            })
            self._save(data)
            return dict(item)
        raise KeyError(handoff_id)

    def block(self, handoff_id, *, summary):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        for item in data.get('items', []):
            if item.get('id') != handoff_id:
                continue
            if item.get('status') == 'BLOCKED':
                return dict(item)
            if item.get('status') != 'OPEN':
                raise ValueError(f"handoff_not_open:{item.get('status')}")
            item.update({'status': 'BLOCKED', 'summary': str(summary), 'updated_at': now})
            self._save(data)
            return dict(item)
        raise KeyError(handoff_id)

    def cancel_for_task(self, task_id, *, reason):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        changed = []
        for item in data.get('items', []):
            if item.get('task_id') == task_id and item.get('status') == 'OPEN':
                item.update({'status': 'CANCELLED', 'summary': str(reason), 'updated_at': now})
                changed.append(dict(item))
        if changed:
            self._save(data)
        return changed
