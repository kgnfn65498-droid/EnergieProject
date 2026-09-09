from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from persistence import atomic_write_json

TARGET_RELEASE = '32.4.23'
EXPECTED_SCHEMA = 'energie_projectmanager_canonical_roadmap_v3'
EXPECTED_KEYS = {
    'conversation-intake', 'proactive-pm', 'nomad-next', 'ngrok-assessment',
    'subscription-independence', 'cowork-pilot', 'month-import-next',
}
REQUIRED_GATES = ['ngrok-assessment', 'voice-live-acceptance', 'new-chat-handover-live']


def _item(by_key: dict, key: str) -> dict:
    value = by_key.get(key)
    if not isinstance(value, dict):
        raise ValueError(f'missing expected canonical roadmap item: {key}')
    return deepcopy(value)


def migrate_canonical_roadmap(path: Path | str) -> dict:
    """Idempotently apply the user-approved 32.4.23 pre-32.5 governance gates."""
    target = Path(path)
    try:
        current = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        return {'status': 'invalid', 'reason': f'{type(exc).__name__}: {exc}'}
    if not isinstance(current, dict):
        return {'status': 'invalid', 'reason': 'canonical roadmap is not an object'}

    if current.get('migration_release') == TARGET_RELEASE:
        return {'status': 'already_current', 'path': str(target)}

    items = current.get('items')
    keys = {str(item.get('key')) for item in items if isinstance(item, dict)} if isinstance(items, list) else set()
    if (
        current.get('schema') != EXPECTED_SCHEMA
        or current.get('version') != 3
        or current.get('approved_by') != 'Peter'
        or keys != EXPECTED_KEYS
    ):
        return {'status': 'unsupported', 'reason': 'canonical roadmap does not match approved v3 migration baseline'}

    by_key = {item['key']: item for item in items}
    conversation = _item(by_key, 'conversation-intake')
    proactive = _item(by_key, 'proactive-pm')
    nomad = _item(by_key, 'nomad-next')
    ngrok = _item(by_key, 'ngrok-assessment')
    subscription = _item(by_key, 'subscription-independence')
    cowork = _item(by_key, 'cowork-pilot')
    month_import = _item(by_key, 'month-import-next')

    ngrok.update({
        'title': 'ngrok behouden: beveiligde externe PM-ingress configureren en live accepteren',
        'priority': 4,
        'depends_on': ['nomad-next'],
        'acceptance': (
            'ngrok blijft de officiële externe toegangspoort voor Nomad/Voice/ChatGPT naar PMV2; '
            'alleen de dedicated authenticated PM-route is publiek, deny-by-default, met edge-authenticatie, '
            'rate limiting en audit logging; volledige poort 8099/HA/NAS wordt niet publiek gemaakt.'
        ),
    })
    voice = {
        'key': 'voice-live-acceptance',
        'title': 'Voice Mode live end-to-end accepteren vóór 32.5',
        'priority': 5,
        'mode': 'USER',
        'executor': 'handoff',
        'auto_select': True,
        'status': 'OPEN',
        'depends_on': ['ngrok-assessment'],
        'acceptance': (
            'Echte Voice Mode buiten het lokale netwerk bereikt via de beveiligde ngrok-route dezelfde PM-truth/intake; '
            'statusvragen en beschermde tweestapsbevestiging zijn live bewezen zonder parallelle projectwaarheid.'
        ),
    }
    new_chat = {
        'key': 'new-chat-handover-live',
        'title': 'Nieuwe-chat handover live end-to-end accepteren vóór 32.5',
        'priority': 6,
        'mode': 'USER',
        'executor': 'handoff',
        'auto_select': True,
        'status': 'OPEN',
        'depends_on': ['voice-live-acceptance'],
        'acceptance': (
            'Een echte nieuwe ChatGPT/Voice-chat maakt en gebruikt een geldige ready-handover snapshot en hervat '
            'zonder opnieuw vragen of verlies van roadmap/progress/KB-context.'
        ),
    }
    subscription.update({'priority': 7, 'depends_on': ['new-chat-handover-live']})
    cowork.update({'priority': 8, 'depends_on': ['subscription-independence']})
    month_import.update({'priority': 9, 'depends_on': ['cowork-pilot']})

    migrated = deepcopy(current)
    migrated.update({
        'approved_at': '2026-09-09',
        'approved_by': 'Peter',
        'source': 'conversation_2026-09-09_32.4.23_audit_closure',
        'principle': (
            'Projectmanager 32.4 veilig sluiten; daarna Nomad/ngrok beveiligd afronden; '
            'Voice Mode en nieuwe-chat handover live bewijzen vóór 32.5/Cowork.'
        ),
        'migration_release': TARGET_RELEASE,
        'required_gates_before_32_5': list(REQUIRED_GATES),
        'items': [conversation, proactive, nomad, ngrok, voice, new_chat, subscription, cowork, month_import],
    })
    safety = dict(migrated.get('safety') or {})
    safety.update({
        'ngrok_retained': True,
        'ngrok_full_8099_exposure_forbidden': True,
        'voice_live_acceptance_required_before_32_5': True,
        'new_chat_handover_live_required_before_32_5': True,
    })
    migrated['safety'] = safety
    atomic_write_json(target, migrated)
    return {'status': 'migrated', 'path': str(target), 'release': TARGET_RELEASE}
