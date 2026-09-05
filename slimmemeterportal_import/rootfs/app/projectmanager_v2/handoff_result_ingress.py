import json
from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json
from secret_guard import contains_secret_text

VALID_SCHEMA = 'energie_pmv2_handoff_result_v1'
MAX_RESULT_BYTES = 65536
MAX_EVIDENCE_REFS = 20


def _valid_receipts(data):
    return isinstance(data, dict) and isinstance(data.get('items', {}), dict)


class HandoffResultIngressConsumer:
    """Consume immutable external handoff results and reconcile task+roadmap exactly once."""

    def __init__(self, directory, receipt_path, handoffs, tasks, roadmap):
        self.directory = Path(directory) if directory else None
        self.receipt_path = Path(receipt_path)
        self.handoffs = handoffs
        self.tasks = tasks
        self.roadmap = roadmap

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
        if self.directory is None or not self.directory.is_dir():
            return []
        receipts = self._receipts()
        results = []
        changed = False
        budget = max(0, int(max_items))
        for path in sorted(self.directory.glob('*.json')):
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
            if path.stat().st_size > MAX_RESULT_BYTES:
                raise ValueError('handoff_result_too_large')
            raw = path.read_text(encoding='utf-8')
            if contains_secret_text(raw):
                raise ValueError('secret_like_content_rejected')
            envelope = json.loads(raw)
            if not isinstance(envelope, dict) or envelope.get('schema') != VALID_SCHEMA:
                raise ValueError('invalid_handoff_result_schema')
            if str(envelope.get('id') or '') != ingress_id:
                raise ValueError('handoff_result_ingress_id_mismatch')
            handoff_id = str(envelope.get('handoff_id') or '').strip()
            outcome = str(envelope.get('outcome') or '').strip().upper()
            summary = str(envelope.get('summary') or '').strip()
            evidence_refs = envelope.get('evidence_refs') or []
            if not handoff_id:
                raise ValueError('handoff_id_required')
            if outcome not in {'DONE', 'BLOCKED'}:
                raise ValueError('invalid_handoff_outcome')
            if not summary:
                raise ValueError('summary_required')
            if not isinstance(evidence_refs, list) or len(evidence_refs) > MAX_EVIDENCE_REFS:
                raise ValueError('invalid_evidence_refs')
            evidence_refs = [str(item).strip() for item in evidence_refs if str(item).strip()]
            if outcome == 'DONE' and not evidence_refs:
                raise ValueError('done_requires_evidence')

            handoff = self.handoffs.get(handoff_id)
            task_id = handoff['task_id']
            if outcome == 'DONE':
                # Idempotent convergence: each state transition accepts an already-final state.
                self.tasks.complete_handoff(task_id, summary=summary, evidence_refs=evidence_refs)
                self.roadmap.mark_done_for_task(task_id)
                final_handoff = self.handoffs.complete(handoff_id, summary=summary, evidence_refs=evidence_refs)
                return {
                    'status': 'APPLIED',
                    'ingress_id': ingress_id,
                    'handoff_id': handoff_id,
                    'task_id': task_id,
                    'roadmap_key': final_handoff.get('roadmap_key'),
                    'outcome': 'DONE',
                    'at': now,
                }

            self.tasks.block(task_id, summary)
            final_handoff = self.handoffs.block(handoff_id, summary=summary)
            return {
                'status': 'APPLIED',
                'ingress_id': ingress_id,
                'handoff_id': handoff_id,
                'task_id': task_id,
                'roadmap_key': final_handoff.get('roadmap_key'),
                'outcome': 'BLOCKED',
                'at': now,
            }
        except Exception as exc:
            return {
                'status': 'REJECTED',
                'ingress_id': ingress_id,
                'reason': f'{type(exc).__name__}: {exc}',
                'at': now,
            }
