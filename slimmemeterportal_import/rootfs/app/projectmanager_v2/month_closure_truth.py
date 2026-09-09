from __future__ import annotations

from typing import Any

CLOSED_VALID = 'CLOSED_VALID'
OPEN = 'OPEN'
UNKNOWN = 'UNKNOWN'


def closure_status_is_deep_verified(status: Any) -> bool:
    if not isinstance(status, dict):
        return False
    validation = status.get('validation') if isinstance(status.get('validation'), dict) else {}
    verification = status.get('verification') if isinstance(status.get('verification'), dict) else {}
    return bool(
        str(status.get('status') or '').strip().upper() == 'CLOSED'
        and str(validation.get('status') or '').strip().lower() == 'ok'
        and str(verification.get('status') or '').strip().lower() == 'valid'
        and verification.get('deep_verified') is True
        and not (verification.get('hash_failures') or [])
    )


def classify_month_closure(payload: Any) -> dict[str, Any]:
    """Classify RecoveryManager month-closure truth without guessing on malformed CLOSED data."""
    if not isinstance(payload, dict):
        return {'truth': UNKNOWN, 'closed': False, 'reason': 'invalid_recovery_response'}

    closed_flag = payload.get('closed')
    status = payload.get('status')
    status_text = str((status or {}).get('status') or '').strip().upper() if isinstance(status, dict) else ''

    if closed_flag is True or status_text == 'CLOSED':
        if closed_flag is True and closure_status_is_deep_verified(status):
            return {'truth': CLOSED_VALID, 'closed': True, 'reason': 'closed_deep_verified'}
        return {'truth': UNKNOWN, 'closed': False, 'reason': 'closed_not_deep_verified'}

    if closed_flag is False:
        return {'truth': OPEN, 'closed': False, 'reason': 'recovery_reports_open'}

    return {'truth': UNKNOWN, 'closed': False, 'reason': 'closure_truth_missing'}
