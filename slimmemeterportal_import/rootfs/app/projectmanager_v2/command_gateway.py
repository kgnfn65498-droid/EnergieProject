COMMANDS = {
    'status_query': {'action': 'read_status', 'allowed_without_approval': True},
    'energy_query': {'action': 'read_energy', 'allowed_without_approval': True},
    'roadmap_query': {'action': 'read_roadmap', 'allowed_without_approval': True},
    'start_development': {'action': 'mode_development', 'allowed_without_approval': True},
    'start_maintenance': {'action': 'mode_maintenance', 'allowed_without_approval': True},
    'admin_update': {'action': 'admin_update', 'allowed_without_approval': True},
    'production_deploy': {'action': 'production_deploy', 'allowed_without_approval': False, 'decision_kind': 'PRODUCTION_DEPLOY'},
    'architecture_change': {'action': 'architecture_change', 'allowed_without_approval': False, 'decision_kind': 'ARCHITECTURE_CHANGE'},
}

UNSUPPORTED_PROTECTED_INTENTS = {'paid_commitment', 'purchase'}


def plan_command(command: dict) -> dict:
    intent = (command or {}).get('intent')
    if intent in UNSUPPORTED_PROTECTED_INTENTS:
        return {
            'intent': intent,
            'action': 'blocked',
            'allowed_without_approval': False,
            'reason': 'protected_capability_not_installed_fail_closed',
            'source': (command or {}).get('source'),
        }
    base = COMMANDS.get(intent)
    if base is None:
        return {
            'intent': intent,
            'action': 'blocked',
            'allowed_without_approval': False,
            'reason': 'unknown_intent_fail_closed',
            'source': (command or {}).get('source'),
        }
    return {
        'intent': intent,
        'source': (command or {}).get('source'),
        'text': (command or {}).get('text'),
        **base,
    }
