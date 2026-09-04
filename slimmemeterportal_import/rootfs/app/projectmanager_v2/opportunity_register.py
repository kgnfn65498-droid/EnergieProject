from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json

PROMOTE_CATEGORIES_WITHOUT_SAVING = {'security', 'regulation', 'end_of_life', 'data_quality'}


def _promotable(item: dict) -> bool:
    if not item.get('evidence'):
        return False
    if item.get('compatible') is False:
        return False
    if (item.get('annual_saving_eur') or 0) > 0:
        return True
    return item.get('category') in PROMOTE_CATEGORIES_WITHOUT_SAVING


class OpportunityRegister:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema': 1, 'items': []})

    def _save(self, data):
        atomic_write_json(self.path, data)

    def all(self):
        return list(self._load().get('items', []))

    def upsert(self, fingerprint: str, *, category: str, subject: str, evidence: list, annual_saving_eur=None, payback_years=None, compatible=None, details=None):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        item = next((x for x in data.get('items', []) if x.get('fingerprint') == fingerprint), None)
        if item is None:
            item = {'id': uuid4().hex, 'fingerprint': fingerprint, 'created_at': now}
            data.setdefault('items', []).append(item)
        item.update({
            'category': category,
            'subject': subject,
            'evidence': list(dict.fromkeys(evidence or [])),
            'annual_saving_eur': annual_saving_eur,
            'payback_years': payback_years,
            'compatible': compatible,
            'details': details or {},
            'updated_at': now,
        })
        item['status'] = 'PROMOTED' if _promotable(item) else 'WATCHING'
        self._save(data)
        return item
