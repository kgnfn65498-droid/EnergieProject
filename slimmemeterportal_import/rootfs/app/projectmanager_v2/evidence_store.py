from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from persistence import atomic_write_json, load_json

EVIDENCE_STATES = {'BEWEZEN', 'AANGENOMEN', 'NOG_TE_CONTROLEREN', 'GEBLOKKEERD'}


class EvidenceStore:
    def __init__(self, path):
        self.path = Path(path)

    def all(self):
        data = load_json(self.path, default={'schema': 1, 'items': []})
        return list(data.get('items', []))

    def record(self, claim: str, status: str, *, source: str, evidence_ref: Optional[str] = None, details: Optional[dict] = None):
        if status not in EVIDENCE_STATES:
            raise ValueError(f'unknown evidence status: {status}')
        if status == 'BEWEZEN' and not evidence_ref:
            raise ValueError('BEWEZEN requires evidence_ref')
        payload = load_json(self.path, default={'schema': 1, 'items': []})
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
        return item
