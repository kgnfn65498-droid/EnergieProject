from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json
from proactive_policy import evaluate_signal
from proactive_assessment import derive_assessment

PROMOTE_CATEGORIES_WITHOUT_SAVING = {'security', 'regulation', 'end_of_life', 'data_quality'}
VALID_STATUSES = {'PROMOTED', 'WATCHING'}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('items', []), list):
        return False
    return all(isinstance(item, dict) and item.get('status') in VALID_STATUSES for item in data.get('items', []))


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
        return load_json(self.path, default={'schema': 1, 'items': []}, recover_corrupt=True, validator=_valid_payload)

    def _save(self, data):
        atomic_write_json(self.path, data)

    def all(self):
        return [dict(item) for item in self._load().get('items', [])]

    def upsert(self, fingerprint: str, *, category: str, subject: str, evidence: list, annual_saving_eur=None, payback_years=None, compatible=None, assessment=None, details=None):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        item = next((x for x in data.get('items', []) if x.get('fingerprint') == fingerprint), None)
        if item is None:
            item = {'id': uuid4().hex, 'fingerprint': fingerprint, 'created_at': now, 'status': 'WATCHING'}
            data.setdefault('items', []).append(item)
        normalized_evidence = list(dict.fromkeys(evidence or []))
        resolved_assessment = (
            dict(assessment)
            if isinstance(assessment, dict)
            else assessment
            if assessment is not None
            else derive_assessment(
                category,
                evidence=normalized_evidence,
                annual_saving_eur=annual_saving_eur,
                compatible=compatible,
                details=details or {},
            )
        )
        item.update({
            'category': category,
            'subject': subject,
            'evidence': normalized_evidence,
            'annual_saving_eur': annual_saving_eur,
            'payback_years': payback_years,
            'compatible': compatible,
            'assessment': resolved_assessment,
            'details': details or {},
            'updated_at': now,
        })
        item['proactive_evaluation'] = evaluate_signal(item)
        item['status'] = 'PROMOTED' if item['proactive_evaluation'].get('decision') == 'PROMOTE' else 'WATCHING'
        self._save(data)
        return dict(item)

    def mark_notified(self, fingerprint: str, *, material_fingerprint: str, now=None):
        material = str(material_fingerprint or '').strip()
        if not material:
            raise ValueError('material_fingerprint_required')
        data = self._load()
        for item in data.get('items', []):
            if item.get('fingerprint') != fingerprint:
                continue
            stamp = (now or datetime.now(timezone.utc)).isoformat()
            item['last_notified_material_fingerprint'] = material
            item['last_notified_at'] = stamp
            item['updated_at'] = stamp
            self._save(data)
            return dict(item)
        raise KeyError(fingerprint)
