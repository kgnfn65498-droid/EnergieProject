from datetime import datetime, timezone

STATUS_ORDER = {'GREEN': 0, 'ORANGE': 1, 'RED': 2}
ACTIVE_SCHEDULER_STATES = {'starting','waiting','collecting','success'}
INACTIVE_SCHEDULER_STATES = {'stopping','stopped','failed'}


def _parse_timestamp(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _scheduler_active(heartbeat: dict):
    if 'state' in heartbeat:
        state = str(heartbeat.get('state') or '').strip().lower()
        if state in ACTIVE_SCHEDULER_STATES:
            return True
        if state in INACTIVE_SCHEDULER_STATES:
            return False
        return None
    if 'active' in heartbeat:
        return heartbeat.get('active') is True
    return None


def evaluate_quarter_hour_heartbeat(heartbeat: dict, *, now=None, stale_after_seconds: int = 1200) -> dict:
    now = now or datetime.now(timezone.utc)
    if not heartbeat:
        return {'name': 'quarter_hour_scheduler', 'status': 'RED', 'reason': 'heartbeat_missing'}
    active = _scheduler_active(heartbeat)
    if active is False:
        return {'name': 'quarter_hour_scheduler', 'status': 'RED', 'reason': 'scheduler_inactive', 'details': heartbeat}
    if active is None:
        return {'name': 'quarter_hour_scheduler', 'status': 'ORANGE', 'reason': 'scheduler_state_unknown', 'details': heartbeat}
    if heartbeat.get('last_error'):
        return {'name': 'quarter_hour_scheduler', 'status': 'RED', 'reason': 'last_error', 'details': heartbeat}
    heartbeat_at = _parse_timestamp(heartbeat.get('heartbeat_at'))
    if heartbeat_at is None:
        return {'name': 'quarter_hour_scheduler', 'status': 'ORANGE', 'reason': 'heartbeat_timestamp_invalid'}
    age = max(0.0, (now.astimezone(timezone.utc) - heartbeat_at.astimezone(timezone.utc)).total_seconds())
    if age > stale_after_seconds:
        return {'name': 'quarter_hour_scheduler', 'status': 'RED', 'reason': 'heartbeat_stale', 'age_seconds': round(age, 1)}
    return {'name': 'quarter_hour_scheduler', 'status': 'GREEN', 'reason': 'ok', 'age_seconds': round(age, 1), 'details': {'state': heartbeat.get('state')}}


def summarize_health(checks: list) -> dict:
    if not checks:
        return {'status': 'ORANGE', 'attention_count': 1, 'checks': [], 'reason': 'no_checks'}
    worst = max(checks, key=lambda item: STATUS_ORDER.get(item.get('status'), 2)).get('status', 'RED')
    attention = sum(1 for item in checks if item.get('status') != 'GREEN')
    return {'status': worst, 'attention_count': attention, 'checks': checks}


def check_boolean(name: str, ok, *, failure_status='RED', reason_ok='ok', reason_fail='failed', details=None):
    if ok is True:
        return {'name': name, 'status': 'GREEN', 'reason': reason_ok, 'details': details or {}}
    if ok is None:
        return {'name': name, 'status': 'ORANGE', 'reason': 'not_verified', 'details': details or {}}
    return {'name': name, 'status': failure_status, 'reason': reason_fail, 'details': details or {}}
