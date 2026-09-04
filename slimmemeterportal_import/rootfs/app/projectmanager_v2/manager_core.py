from typing import Tuple

RED_EVENTS = {'data_loss', 'security', 'production_down', 'blocking_failure'}
ORANGE_EVENTS = {'drift', 'warning', 'overdue', 'degraded'}
PROTECTED_ACTIONS = {'production_deploy', 'architecture_change', 'paid_commitment', 'purchase'}


def classify_severity(event_type: str) -> Tuple[str, str]:
    if event_type in RED_EVENTS:
        return 'RED', 'notify_now'
    if event_type in ORANGE_EVENTS:
        return 'ORANGE', 'next_status'
    return 'GREEN', 'log_only'


def may_execute(action: str, *, proven_safe: bool, reversible: bool, tested: bool) -> bool:
    if action in PROTECTED_ACTIONS:
        return False
    if action == 'small_repair':
        return proven_safe and reversible and tested
    return proven_safe


def next_mode(current: str, event: str) -> str:
    if event == 'development_started':
        return 'DEVELOPMENT'
    if event in {'maintenance_started', 'incident_started', 'crash_recovery_started'}:
        return 'MAINTENANCE'
    if event == 'definition_of_done_met':
        return 'USER'
    return current
