PROTECTED_ACTIONS = {
    'production_deploy': 'PRODUCTION_DEPLOY',
    'architecture_change': 'ARCHITECTURE_CHANGE',
    'paid_commitment': 'PAID_COMMITMENT',
    'purchase': 'PURCHASE',
}

AUTONOMOUS_SIMPLE_ACTIONS = {
    'admin_update',
    'documentation_update',
    'status_update',
    'market_research',
    'health_check',
    'notification_event',
}


def _approved(approval, required_kind: str) -> bool:
    return bool(
        approval
        and approval.get('kind') == required_kind
        and approval.get('status') == 'APPROVED'
        and approval.get('approved_by')
    )


def can_execute(action: str, *, safety: dict, approval: dict = None) -> bool:
    if action in PROTECTED_ACTIONS:
        return _approved(approval, PROTECTED_ACTIONS[action]) and safety.get('proven_safe', False)
    if action == 'small_repair':
        return all(safety.get(k) is True for k in ('proven_safe', 'reversible', 'tested'))
    if action in {'code_change', 'release_prepare'}:
        return all(safety.get(k) is True for k in ('isolated', 'tested', 'rollback_available'))
    if action == 'retention_cleanup':
        return all(safety.get(k) is True for k in ('retention_verified', 'target_verified'))
    if action in AUTONOMOUS_SIMPLE_ACTIONS:
        return safety.get('scope_allowed', True) is True and safety.get('contains_secret', False) is False
    return False
