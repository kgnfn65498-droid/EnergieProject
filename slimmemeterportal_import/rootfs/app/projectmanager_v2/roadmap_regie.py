import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json

VALID_STATUSES = {'OPEN', 'ACTIVE', 'DONE', 'BLOCKED', 'SUPERSEDED'}
VALID_EXECUTORS = {'handoff', 'embedded'}


FALLBACK_ITEMS = (
    {'key': 'ngrok-assessment', 'title': 'ngrok structurele noodzaak en endpointbeveiliging beoordelen', 'priority': 3, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'depends_on': []},
    {'key': 'subscription-independence', 'title': 'Abonnementsonafhankelijkheid vóór Cowork-pilot analyseren', 'priority': 4, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'depends_on': []},
    {'key': 'cowork-pilot', 'title': 'Cowork-pilot voorbereiden en uitvoeren', 'priority': 5, 'mode': 'DEVELOPMENT', 'executor': 'handoff', 'auto_select': True, 'depends_on': []},
    {'key': 'nomad-next', 'title': 'Nomad verdere ontwikkeling', 'priority': 6, 'mode': 'DEVELOPMENT', 'executor': 'handoff', 'auto_select': True, 'depends_on': []},
    {'key': 'month-import-next', 'title': 'Maandimport stabiliteit en autonomie verder afronden', 'priority': 7, 'mode': 'DEVELOPMENT', 'executor': 'handoff', 'auto_select': True, 'depends_on': []},
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
        return load_json(self.path, default={'schema': 2, 'items': []}, recover_corrupt=True, validator=_valid_payload)

    def _save(self, data):
        atomic_write_json(self.path, data)

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]


    def seed_defaults(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        data = self._load()
        by_key = {item.get('key'): item for item in data.get('items', [])}
        changed = False
        for order, spec in enumerate(FALLBACK_ITEMS, start=1):
            if spec['key'] in by_key:
                continue
            item = dict(spec)
            item.update({'status': 'OPEN', 'canonical_order': order, 'created_at': now.isoformat(), 'updated_at': now.isoformat()})
            data.setdefault('items', []).append(item)
            changed = True
        if changed:
            self._save(data)
        return data

    @staticmethod
    def canonical_hash(spec: dict) -> str:
        raw = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _validate_spec(spec: dict):
        if not isinstance(spec, dict) or not isinstance(spec.get('items'), list):
            raise ValueError('invalid canonical roadmap spec')
        seen = set()
        for item in spec['items']:
            if not isinstance(item, dict) or not item.get('key') or not item.get('title'):
                raise ValueError('invalid canonical roadmap item')
            if item['key'] in seen:
                raise ValueError(f"duplicate roadmap key: {item['key']}")
            seen.add(item['key'])
            if item.get('executor', 'handoff') not in VALID_EXECUTORS:
                raise ValueError(f"invalid executor for {item['key']}")
            if item.get('status', 'OPEN') not in {'OPEN', 'DONE'}:
                raise ValueError(f"canonical status must be OPEN/DONE: {item['key']}")
        for item in spec['items']:
            for dependency in item.get('depends_on', []):
                if dependency not in seen:
                    raise ValueError(f"unknown dependency {dependency} for {item['key']}")

    def reconcile_canonical(self, spec: dict, *, source_path: str = '') -> dict:
        self._validate_spec(spec)
        data = self._load()
        existing = {item.get('key'): item for item in data.get('items', [])}
        canonical_keys = {item['key'] for item in spec['items']}
        now = datetime.now(timezone.utc).isoformat()
        deactivated = []
        new_items = []

        for order, source in enumerate(spec['items'], start=1):
            current = existing.get(source['key'])
            if current is None:
                current = {
                    'key': source['key'],
                    'created_at': now,
                    'status': source.get('status', 'OPEN'),
                }
            old_status = current.get('status', 'OPEN')
            old_task_id = current.get('task_id')
            current.update({
                'title': source['title'],
                'priority': int(source.get('priority', order)),
                'mode': source.get('mode', 'USER'),
                'executor': source.get('executor', 'handoff'),
                'auto_select': source.get('auto_select', True) is True,
                'depends_on': list(source.get('depends_on', [])),
                'acceptance': source.get('acceptance', ''),
                'canonical_order': order,
                'updated_at': now,
            })
            if old_status == 'DONE':
                current['status'] = 'DONE'
            elif old_status in {'ACTIVE', 'BLOCKED'}:
                current['status'] = old_status
                if old_task_id:
                    current['task_id'] = old_task_id
            else:
                current['status'] = source.get('status', 'OPEN')
                current.pop('task_id', None)
            new_items.append(current)

        for key, item in existing.items():
            if key in canonical_keys:
                continue
            historical = dict(item)
            historical['status'] = 'SUPERSEDED'
            historical['auto_select'] = False
            historical['updated_at'] = now
            historical['superseded_reason'] = 'not present in canonical roadmap'
            new_items.append(historical)
            if item.get('status') in {'ACTIVE', 'BLOCKED'} and item.get('task_id'):
                deactivated.append({'key': key, 'task_id': item['task_id'], 'reason': 'removed_from_canonical_roadmap'})

        by_key = {item['key']: item for item in new_items}
        for item in new_items:
            if item.get('status') not in {'ACTIVE', 'BLOCKED'}:
                continue
            missing = [dep for dep in item.get('depends_on', []) if by_key.get(dep, {}).get('status') != 'DONE']
            if missing:
                task_id = item.pop('task_id', None)
                item['status'] = 'OPEN'
                item['updated_at'] = now
                if task_id:
                    deactivated.append({
                        'key': item['key'],
                        'task_id': task_id,
                        'reason': f"canonical_dependencies_not_done:{','.join(missing)}",
                    })

        data = {
            'schema': 2,
            'canonical': {
                'schema': spec.get('schema'),
                'version': spec.get('version'),
                'approved_at': spec.get('approved_at'),
                'approved_by': spec.get('approved_by'),
                'source_path': source_path,
                'sha256': self.canonical_hash(spec),
                'reconciled_at': now,
            },
            'items': sorted(new_items, key=lambda x: (x.get('canonical_order', 9999), x.get('priority', 99), x.get('key', ''))),
        }
        self._save(data)
        return {'canonical': dict(data['canonical']), 'deactivated': deactivated, 'items': self.all()}

    def _dependencies_done(self, item, by_key):
        return all(by_key.get(dep, {}).get('status') == 'DONE' for dep in item.get('depends_on', []))

    def next_open(self, *, mode=None):
        data = self._load()
        by_key = {item.get('key'): item for item in data.get('items', [])}
        items = [
            item for item in data.get('items', [])
            if item.get('status') == 'OPEN'
            and item.get('auto_select') is True
            and (mode is None or item.get('mode') == mode)
            and self._dependencies_done(item, by_key)
        ]
        if not items:
            return None
        return dict(sorted(items, key=lambda item: (item.get('canonical_order', 9999), item.get('priority', 99), item.get('created_at', ''), item.get('key', '')))[0])

    def mark_active(self, key, task_id):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        for item in data.get('items', []):
            if item.get('key') == key:
                if item.get('status') == 'DONE':
                    return dict(item)
                item.update({'status': 'ACTIVE', 'task_id': task_id, 'updated_at': now})
                self._save(data)
                return dict(item)
        raise KeyError(key)

    def mark_done_for_task(self, task_id):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        changed = []
        for item in data.get('items', []):
            if item.get('task_id') == task_id:
                if item.get('status') == 'DONE':
                    changed.append(dict(item))
                    continue
                if item.get('status') in {'ACTIVE', 'BLOCKED'}:
                    item.update({'status': 'DONE', 'updated_at': now})
                    changed.append(dict(item))
        if changed:
            self._save(data)
        return changed

    def reopen_for_task(self, task_id, *, reason):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        changed = []
        for item in data.get('items', []):
            if item.get('task_id') == task_id and item.get('status') in {'ACTIVE', 'BLOCKED'}:
                item['status'] = 'OPEN'
                item.pop('task_id', None)
                item['updated_at'] = now
                item['reopened_reason'] = str(reason)
                changed.append(dict(item))
        if changed:
            self._save(data)
        return changed

    def canonical_metadata(self):
        data = self._load()
        value = data.get('canonical')
        return dict(value) if isinstance(value, dict) else {}
