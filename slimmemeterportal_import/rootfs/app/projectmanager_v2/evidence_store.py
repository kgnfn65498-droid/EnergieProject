from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from persistence import atomic_write_json, load_json

EVIDENCE_STATES = {'BEWEZEN', 'AANGENOMEN', 'NOG_TE_CONTROLEREN', 'GEBLOKKEERD'}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    return all(
        isinstance(item, dict)
        and item.get('status') in EVIDENCE_STATES
        and bool(item.get('claim'))
        for item in data.get('items', [])
    )


class EvidenceStore:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(self.path, default={'schema': 1, 'items': []}, recover_corrupt=True, validator=_valid_payload)

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]

    def record(self, claim: str, status: str, *, source: str, evidence_ref: Optional[str] = None, details: Optional[dict] = None):
        if status not in EVIDENCE_STATES:
            raise ValueError(f'unknown evidence status: {status}')
        if status == 'BEWEZEN' and not evidence_ref:
            raise ValueError('BEWEZEN requires evidence_ref')
        payload = self._load()
        item = {
            'id': uuid4().hex,
            'claim': claim,
            'status': status,
            'source': source,
            'evidence_ref': evidence_ref,
            'details': details or {},
            'recorded_at': datetime.now(timezone.utc).isoformat(),
        }
        payload.setdefault('items', []).append(item)
        atomic_write_json(self.path, payload)
        return dict(item)

    def upsert_current(self, claim: str, status: str, *, source: str, evidence_ref: Optional[str] = None, details: Optional[dict] = None):
        if status not in EVIDENCE_STATES:
            raise ValueError(f'unknown evidence status: {status}')
        if status == 'BEWEZEN' and not evidence_ref:
            raise ValueError('BEWEZEN requires evidence_ref')
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        item = next((x for x in data.get('items', []) if x.get('claim') == claim and x.get('source') == source), None)
        if item is None:
            item = {'id': uuid4().hex, 'claim': claim, 'source': source, 'created_at': now, 'status': 'NOG_TE_CONTROLEREN'}
            data.setdefault('items', []).append(item)
        item.update({'status': status, 'evidence_ref': evidence_ref, 'details': details or {}, 'recorded_at': now})
        atomic_write_json(self.path, data)
        return dict(item)
