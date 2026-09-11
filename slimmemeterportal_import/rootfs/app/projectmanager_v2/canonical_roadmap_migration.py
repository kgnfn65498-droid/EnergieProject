from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from persistence import atomic_write_json

TARGET_RELEASE = '32.4.40'
EXPECTED_SCHEMA = 'energie_projectmanager_canonical_roadmap_v3'
BASE_KEYS = {
    'conversation-intake', 'proactive-pm', 'nomad-next', 'ngrok-assessment',
    'subscription-independence', 'cowork-pilot', 'month-import-next',
}
REQUIRED_GATES = ['32-4-closure-live', 'ngrok-assessment', 'voice-live-acceptance', 'new-chat-handover-live']


def _item(by_key: dict, key: str) -> dict:
    value = by_key.get(key)
    if not isinstance(value, dict):
        raise ValueError(f'missing expected canonical roadmap item: {key}')
    return deepcopy(value)


def _voice_item(by_key: dict) -> dict:
    if isinstance(by_key.get('voice-live-acceptance'), dict):
        return deepcopy(by_key['voice-live-acceptance'])
    return {
        'key': 'voice-live-acceptance', 'title': 'Voice Mode live end-to-end accepteren vóór 32.5',
        'priority': 6, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN',
        'depends_on': ['ngrok-assessment'],
        'acceptance': 'Echte Voice Mode bereikt via de beveiligde ngrok-route dezelfde PM-truth/intake.',
    }


def _new_chat_item(by_key: dict) -> dict:
    if isinstance(by_key.get('new-chat-handover-live'), dict):
        return deepcopy(by_key['new-chat-handover-live'])
    return {
        'key': 'new-chat-handover-live', 'title': 'Nieuwe-chat handover live end-to-end accepteren vóór 32.5',
        'priority': 7, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN',
        'depends_on': ['voice-live-acceptance'],
        'acceptance': 'Nieuwe chat hervat met geldige handover zonder verlies van roadmap/progress/KB-context.',
    }


def migrate_canonical_roadmap(path: Path | str) -> dict:
    """Idempotently add the live 32.4 closure gate before ngrok/Voice/32.5."""
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
        or not BASE_KEYS.issubset(keys)
    ):
        return {'status': 'unsupported', 'reason': 'canonical roadmap does not match approved v3 baseline'}

    by_key = {item['key']: item for item in items if isinstance(item, dict) and item.get('key')}
    conversation = _item(by_key, 'conversation-intake')
    proactive = _item(by_key, 'proactive-pm')
    nomad = _item(by_key, 'nomad-next')
    ngrok = _item(by_key, 'ngrok-assessment')
    subscription = _item(by_key, 'subscription-independence')
    cowork = _item(by_key, 'cowork-pilot')
    month_import = _item(by_key, 'month-import-next')
    voice = _voice_item(by_key)
    new_chat = _new_chat_item(by_key)
    closure = deepcopy(by_key.get('32-4-closure-live') or {
        'key': '32-4-closure-live',
        'title': '32.4 live closure autonoom afronden',
        'mode': 'MAINTENANCE', 'executor': 'embedded', 'auto_select': False, 'status': 'OPEN',
        'acceptance': 'Watcher/runtime, actuele CR sets, verse CLEARUP en closure-health zijn live GREEN.',
    })
    closure.update({'priority': 4, 'depends_on': [], 'auto_select': False, 'executor': 'embedded', 'mode': 'MAINTENANCE'})
    ngrok.update({
        'title': 'ngrok behouden: beveiligde externe PM-ingress configureren en live accepteren',
        'priority': 5,
        'depends_on': ['32-4-closure-live'],
        'acceptance': (
            'ngrok blijft de officiële externe toegangspoort voor Nomad/Voice/ChatGPT naar PMV2; '
            'alleen de dedicated authenticated PM-route is publiek, deny-by-default, met edge-authenticatie, '
            'rate limiting en audit logging; volledige poort 8099/HA/NAS wordt niet publiek gemaakt.'
        ),
    })
    voice.update({'priority': 6, 'depends_on': ['ngrok-assessment']})
    new_chat.update({'priority': 7, 'depends_on': ['voice-live-acceptance']})
    subscription.update({'priority': 8, 'depends_on': ['new-chat-handover-live']})
    cowork.update({'priority': 9, 'depends_on': ['subscription-independence']})
    month_import.update({'priority': 10, 'depends_on': ['cowork-pilot']})

    migrated = deepcopy(current)
    migrated.update({
        'approved_at': '2026-09-11', 'approved_by': 'Peter',
        'source': 'conversation_2026-09-11_32.4.40_final_pm_closure',
        'principle': '32.4 eerst live sluiten; daarna ngrok-security, Voice Mode, nieuwe-chat handover en pas daarna 32.5/Cowork.',
        'migration_release': TARGET_RELEASE,
        'required_gates_before_32_5': list(REQUIRED_GATES),
        'items': [conversation, proactive, nomad, closure, ngrok, voice, new_chat, subscription, cowork, month_import],
    })
    safety = dict(migrated.get('safety') or {})
    safety.update({
        'ngrok_retained': True, 'ngrok_full_8099_exposure_forbidden': True,
        'series_32_4_live_closure_required_before_ngrok': True,
        'voice_live_acceptance_required_before_32_5': True,
        'new_chat_handover_live_required_before_32_5': True,
    })
    migrated['safety'] = safety
    trace = {
        'conversation-intake': (['UDL-004'], ['conversation_intake_e2e'], True),
        'proactive-pm': (['UDL-004'], ['proactive_pm_e2e'], True),
        'nomad-next': (['UDL-004'], ['nomad_same_truth'], True),
        '32-4-closure-live': (['UDL-001','UDL-002','UDL-003','UDL-004'], ['watcher_v3','native_mcp_fingerprint','canonical_roadmap_readback','cr_sets','clearup_hygiene','atomic_acceptance'], True),
        'ngrok-assessment': (['UDL-004'], ['ngrok_edge_security'], True),
        'voice-live-acceptance': (['UDL-004'], ['voice_e2e'], True),
        'new-chat-handover-live': (['UDL-003','UDL-004'], ['new_chat_verder_e2e'], True),
        'subscription-independence': (['UDL-004'], ['subscription_analysis'], False),
        'cowork-pilot': (['UDL-003','UDL-004'], ['cowork_pilot_metrics'], True),
        'month-import-next': (['UDL-003'], ['month_import_e2e'], True),
    }
    for item in migrated['items']:
        refs, tests, live_required = trace.get(item.get('key'), ([], [], False))
        item['acceptance_matrix_required'] = True
        item['ledger_refs'] = list(refs)
        item['required_tests'] = list(tests)
        item['live_required'] = bool(live_required)
        item.setdefault('evidence_refs', [])
        item.setdefault('carry_forward', [])
        if item.get('status') == 'DONE':
            item['acceptance_state'] = 'CLOSED_COLD'
        else:
            item['acceptance_state'] = 'LIVE_REQUIRED' if live_required else 'TODO'
    try:
        atomic_write_json(target, migrated, mode=0o644)
    except OSError as exc:
        return {
            'status': 'persistence_required', 'path': str(target), 'release': TARGET_RELEASE,
            'persistence_required': True, 'reason': f'{type(exc).__name__}: {exc}',
        }
    try:
        persisted = json.loads(target.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            'status': 'persistence_verification_failed', 'path': str(target),
            'release': TARGET_RELEASE, 'reason': f'{type(exc).__name__}: {exc}',
        }
    if (target.stat().st_mode & 0o777) != 0o644:
        return {
            'status': 'persistence_verification_failed', 'path': str(target),
            'release': TARGET_RELEASE, 'reason': 'canonical_roadmap_mode_not_0644',
        }
    if persisted != migrated:
        return {
            'status': 'persistence_verification_failed', 'path': str(target),
            'release': TARGET_RELEASE, 'reason': 'disk_readback_differs_from_migrated_spec',
        }
    raw = json.dumps(persisted, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {
        'status': 'migrated', 'path': str(target), 'release': TARGET_RELEASE,
        'sha256': hashlib.sha256(raw).hexdigest(),
    }


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description='Persist and verify the approved canonical roadmap migration')
    parser.add_argument('--path', required=True)
    args = parser.parse_args()
    result = migrate_canonical_roadmap(Path(args.path))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('status') in {'migrated', 'already_current'} else 3


if __name__ == '__main__':
    raise SystemExit(main())
