import json
from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json
from secret_guard import contains_secret_text

ALLOWED_FIELDS = {
    'intent', 'text', 'title', 'goal', 'steps_total', 'priority', 'next_action',
    'artifact_path', 'artifact_sha256', 'release_version', 'verification_report',
}
MAX_COMMAND_BYTES = 65536
VALID_SCHEMA = 'energie_pmv2_command_ingress_v1'


def _valid_receipts(data):
    return isinstance(data, dict) and isinstance(data.get('items', {}), dict)


class CommandIngressConsumer:
    """Read immutable external command envelopes and import them once."""

    def __init__(self, directory, receipt_path, command_store):
        self.directory = Path(directory) if directory else None
        self.receipt_path = Path(receipt_path)
        self.commands = command_store

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
            changed = True
            results.append(result)
        if changed:
            self._save_receipts(receipts)
        return results

    def _consume_one(self, path: Path, ingress_id: str):
        now = datetime.now(timezone.utc).isoformat()
        try:
            if path.stat().st_size > MAX_COMMAND_BYTES:
                raise ValueError('command_too_large')
            raw = path.read_text(encoding='utf-8')
            if contains_secret_text(raw):
                raise ValueError('secret_like_content_rejected')
            envelope = json.loads(raw)
            if not isinstance(envelope, dict) or envelope.get('schema') != VALID_SCHEMA:
                raise ValueError('invalid_ingress_schema')
            if str(envelope.get('id') or '') != ingress_id:
                raise ValueError('ingress_id_mismatch')
            body = envelope.get('command')
            if not isinstance(body, dict) or not body.get('intent'):
                raise ValueError('invalid_command_body')
            payload = {key: body.get(key) for key in ALLOWED_FIELDS if key in body}
            payload['source'] = 'mcp_remote'
            payload['ingress_id'] = ingress_id
            item = self.commands.enqueue(payload)
            return {
                'status': 'IMPORTED',
                'ingress_id': ingress_id,
                'command_id': item['id'],
                'intent': item.get('intent'),
                'at': now,
            }
        except Exception as exc:
            return {
                'status': 'REJECTED',
                'ingress_id': ingress_id,
                'reason': f'{type(exc).__name__}: {exc}',
                'at': now,
            }
