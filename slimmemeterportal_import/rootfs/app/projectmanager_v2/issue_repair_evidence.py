from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _parse_iso(value):
    try:
        parsed = datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _load_items(path: Path):
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    items = payload.get('items', {}) if isinstance(payload, dict) else {}
    return items if isinstance(items, dict) else {}


def _later_receipt(items, *, after, predicate):
    candidates = []
    for ingress_id, item in items.items():
        if not isinstance(item, dict) or not predicate(item):
            continue
        at = _parse_iso(item.get('at'))
        if at is None or after is None or at <= after:
            continue
        candidates.append((at, str(ingress_id), item))
    if not candidates:
        return None
    candidates.sort(key=lambda row: (row[0], row[1]))
    return candidates[-1]


def collect_issue_repair_evidence(runtime_root, issues) -> dict[str, dict]:
    root = Path(runtime_root)
    command_receipts = _load_items(root / 'commands/ingress_receipts.json')
    handoff_receipts = _load_items(root / 'handoffs/result_ingress_receipts.json')
    repairs = {}
    for issue in issues or []:
        if not isinstance(issue, dict) or not issue.get('id'):
            continue
        fingerprint = str(issue.get('fingerprint') or '')
        reason = str((issue.get('details') or {}).get('reason') or '')
        after = _parse_iso(issue.get('last_seen_at') or issue.get('created_at'))

        if fingerprint.startswith('command_ingress:') and 'PermissionError' in reason and 'Permission denied' in reason:
            match = _later_receipt(
                command_receipts,
                after=after,
                predicate=lambda item: item.get('status') == 'IMPORTED',
            )
            if match is not None:
                _, ingress_id, item = match
                repairs[issue['id']] = {
                    'reason': 'later CommandIngress receipt IMPORTED after historical permission failure',
                    'evidence_refs': [
                        f'{root / "commands/ingress_receipts.json"}#{ingress_id}',
                        f'command:{item.get("command_id")}',
                    ],
                    'repair_class': 'command_ingress_permission',
                }
            continue

        if fingerprint.startswith('handoff_result_ingress:') and 'cannot complete from PAUSED' in reason:
            match = _later_receipt(
                handoff_receipts,
                after=after,
                predicate=lambda item: (
                    item.get('status') == 'APPLIED'
                    and item.get('resumed_from_paused') is True
                ),
            )
            if match is not None:
                _, ingress_id, item = match
                repairs[issue['id']] = {
                    'reason': 'later PAUSED handoff result APPLIED with resumed_from_paused=true',
                    'evidence_refs': [
                        f'{root / "handoffs/result_ingress_receipts.json"}#{ingress_id}',
                        f'handoff:{item.get("handoff_id")}',
                    ],
                    'repair_class': 'handoff_paused_completion',
                }
    return repairs
