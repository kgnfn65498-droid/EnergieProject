import json
import os
from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json

VALID_SCHEMA = 'energie_pmv2_approval_ingress_v1'
MAX_APPROVAL_BYTES = 16384


def _valid_receipts(data):
    return isinstance(data, dict) and isinstance(data.get('items', {}), dict)


class ApprovalIngressConsumer:
    """Consume local HA-ingress approval envelopes exactly once."""

    def __init__(self, directory, receipt_path, decision_queue):
        if isinstance(directory, (list, tuple)):
            raw_directories = [str(item) for item in directory if str(item).strip()]
        else:
            raw = str(directory or '')
            raw_directories = [item for item in raw.split(os.pathsep) if item.strip()]
        self.directories = [Path(item) for item in raw_directories]
        self.directory = self.directories[0] if self.directories else None
        self.receipt_path = Path(receipt_path)
        self.decisions = decision_queue

    def _receipts(self):
        return load_json(
            self.receipt_path,
            default={'schema': 1, 'items': {}},
            recover_corrupt=True,
            validator=_valid_receipts,
        )

    def _save_receipts(self, data):
        atomic_write_json(self.receipt_path, data)

    def consume(self, *, max_items=20):
        directories = [path for path in self.directories if path.is_dir()]
        if not directories:
            return []
        receipts = self._receipts()
        results = []
        changed = False
        budget = max(0, int(max_items))
        candidates = []
        for directory in directories:
            candidates.extend(directory.glob('*.json'))
        for path in sorted(candidates, key=lambda item: (item.name, str(item.parent))):
            if len(results) >= budget:
                break
            ingress_id = path.stem
            if ingress_id in receipts.get('items', {}):
                continue
            result = self._consume_one(path, ingress_id)
            receipts.setdefault('items', {})[ingress_id] = result
            results.append(result)
            changed = True
        if changed:
            self._save_receipts(receipts)
        return results

    def _consume_one(self, path: Path, ingress_id: str):
        now = datetime.now(timezone.utc).isoformat()
        try:
            if path.stat().st_size > MAX_APPROVAL_BYTES:
                raise ValueError('approval_too_large')
            envelope = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(envelope, dict) or envelope.get('schema') != VALID_SCHEMA:
                raise ValueError('invalid_approval_schema')
            if str(envelope.get('id') or '') != ingress_id:
                raise ValueError('approval_ingress_id_mismatch')
            decision_id = str(envelope.get('decision_id') or '').strip()
            if not decision_id:
                raise ValueError('decision_id_required')
            if type(envelope.get('approved')) is not bool:
                raise ValueError('approved_must_be_boolean')
            if envelope.get('approved_by') != 'Peter':
                raise ValueError('only_Peter_may_approve')
            current = self.decisions.get(decision_id)
            if current.get('status') != 'PENDING':
                return {
                    'status': 'IGNORED_ALREADY_RESOLVED',
                    'ingress_id': ingress_id,
                    'decision_id': decision_id,
                    'decision_status': current.get('status'),
                    'at': now,
                }
            resolved = self.decisions.resolve(
                decision_id,
                approved=envelope['approved'],
                approved_by='Peter',
            )
            return {
                'status': 'APPLIED',
                'ingress_id': ingress_id,
                'decision_id': decision_id,
                'decision_status': resolved.get('status'),
                'at': now,
            }
        except Exception as exc:
            return {
                'status': 'REJECTED',
                'ingress_id': ingress_id,
                'reason': f'{type(exc).__name__}: {exc}',
                'at': now,
            }
