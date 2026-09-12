from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json
from secret_guard import redact

_ACTION_KINDS = {
    'production_deploy': 'PRODUCTION_DEPLOY',
    'native_mcp_reload': 'PRODUCTION_RESTART',
    'architecture_change': 'ARCHITECTURE_CHANGE',
}
_VALID_STATUSES = {'PENDING', 'CONFIRMED', 'EXPIRED', 'INVALIDATED'}
_EXPLICIT_CONFIRMATION = (
    re.compile(r'^\s*(?:ja|akkoord)\s*[.!]?\s*$', re.IGNORECASE),
    re.compile(r'\bja\b.*\bvoer\b.*\buit\b', re.IGNORECASE),
    re.compile(r'\bbevestig\w*\b.*\bdefinitief\b.*\bvoer\b.*\buit\b', re.IGNORECASE),
    re.compile(r'\bvoer\b.*\bdefinitief\b.*\buit\b', re.IGNORECASE),
)
_SHORT_FOLLOWUP = re.compile(r'^\s*(?:ja|akkoord)\s*[.!]?\s*$', re.IGNORECASE)


def _utc(value=None):
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _signature(action: str, parameters: dict) -> str:
    canonical = json.dumps(
        {'action': str(action), 'parameters': redact(dict(parameters or {}))},
        ensure_ascii=False,
        sort_keys=True,
        separators=(',', ':'),
    )
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def _valid_payload(data):
    if not isinstance(data, dict) or data.get('schema') != 1 or not isinstance(data.get('items'), list):
        return False
    return all(
        isinstance(item, dict)
        and item.get('id')
        and item.get('decision_id')
        and item.get('action') in _ACTION_KINDS
        and item.get('status') in _VALID_STATUSES
        and item.get('signature')
        for item in data.get('items', [])
    )


def _explicit_confirmation(text: str) -> bool:
    value = ' '.join(str(text or '').strip().split())
    if not value:
        return False
    return any(pattern.search(value) for pattern in _EXPLICIT_CONFIRMATION)


class ConversationApprovalCoordinator:
    """Two-step conversation confirmation over the canonical DecisionQueue.

    This store contains challenges only. It never grants protected execution by
    itself: approval becomes real only by resolving the existing canonical
    DecisionQueue item, which remains the input to the normal approval gate.
    """

    def __init__(self, path, decisions, *, commands=None, audit=None, ttl_seconds=120):
        self.path = Path(path)
        self.decisions = decisions
        self.commands = commands
        self.audit = audit
        self.ttl_seconds = max(15, int(ttl_seconds))

    def _load(self):
        return load_json(
            self.path,
            default={'schema': 1, 'items': []},
            recover_corrupt=True,
            validator=_valid_payload,
        )

    def _save(self, data):
        atomic_write_json(self.path, data)

    def _audit(self, event_type, *, result, details):
        if self.audit is None:
            return
        self.audit.write(
            event_type,
            actor='projectmanager',
            result=result,
            details=redact(details),
        )

    def handles_followup(self, text: str) -> bool:
        """Accept a short approval token only when exactly one live challenge exists."""
        if not _SHORT_FOLLOWUP.fullmatch(str(text or '')):
            return False
        return len(self.pending()) == 1

    def _existing_pending_binding(self, *, action: str, parameters: dict):
        """Reuse one exact canonical pending decision/command; never guess between several."""
        kind = _ACTION_KINDS[action]
        version = str(parameters.get('version') or '').strip()
        matches = []
        for decision in self.decisions.pending():
            if decision.get('kind') != kind:
                continue
            context = decision.get('context') if isinstance(decision.get('context'), dict) else {}
            if str(context.get('intent') or '').strip() != action:
                continue
            context_version = str(context.get('release_version') or '').strip()
            if version and context_version and context_version != version:
                continue
            command_id = str(context.get('command_id') or '').strip()
            command = None
            if self.commands is not None:
                if not command_id:
                    continue
                try:
                    command = self.commands.get(command_id)
                except KeyError:
                    continue
                if command.get('intent') != action:
                    continue
                if command.get('status') != 'WAITING_APPROVAL':
                    continue
                if command.get('approval_decision_id') != decision.get('id'):
                    continue
                command_version = str(command.get('release_version') or '').strip()
                if version and command_version and command_version != version:
                    continue
            matches.append((dict(decision), dict(command) if isinstance(command, dict) else None))
        if len(matches) > 1:
            raise ValueError('meerdere passende PENDING Projectmanager-beslissingen; expliciete keuze vereist')
        return matches[0] if matches else (None, None)

    def request(self, *, action: str, parameters: dict, source_channel: str, now=None):
        action = str(action or '').strip()
        if action not in _ACTION_KINDS:
            raise ValueError('unsupported_protected_conversation_action')
        source_channel = str(source_channel or '').strip().lower()
        if not source_channel:
            raise ValueError('source_channel_required')
        parameters = redact(dict(parameters or {}))
        signature = _signature(action, parameters)
        stamp = _utc(now)

        data = self._load()
        for current in reversed(data.get('items', [])):
            if current.get('signature') != signature or current.get('status') != 'PENDING':
                continue
            try:
                expires = datetime.fromisoformat(str(current.get('expires_at')).replace('Z', '+00:00'))
            except (TypeError, ValueError):
                break
            if _utc(expires) >= stamp:
                return {
                    'status': 'confirmation_required',
                    'challenge': dict(current),
                    'prompt': current.get('prompt', ''),
                }

        target = str(parameters.get('target') or '').strip()
        version = str(parameters.get('version') or '').strip()
        subject = 'de beschermde actie'
        if action == 'production_deploy':
            subject = f"{version or 'de release'} als productie-update in {target or 'de productieomgeving'}"
        elif action == 'native_mcp_reload':
            subject = 'de gecontroleerde restart van energie-filesystem-mcp'
        elif action == 'architecture_change':
            subject = f"de architectuurwijziging voor {target or version or 'het opgegeven doel'}"
        prompt = f'Ik ga {subject} uitvoeren. Wil je dit nu definitief uitvoeren?'

        decision, command = self._existing_pending_binding(action=action, parameters=parameters)
        if decision is None:
            decision = self.decisions.request(
                _ACTION_KINDS[action],
                prompt,
                fingerprint=f'conversation-protected:{signature}',
                context={
                    'source_channel': source_channel,
                    'action': action,
                    'intent': action,
                    'parameters': parameters,
                    'release_version': version,
                    'signature': signature,
                    'two_step_confirmation_required': True,
                },
            )
            command = None
            if self.commands is not None:
                command_payload = {
                    'intent': action,
                    'source': f'conversation:{source_channel}',
                    'text': prompt,
                    'title': prompt,
                    'goal': prompt,
                    'ingress_id': f'conversation-protected:{signature}',
                    'release_version': version,
                    'target': target,
                }
                for key in ('artifact_path', 'artifact_sha256', 'verification_report', 'next_action', 'steps_total', 'priority'):
                    if parameters.get(key) not in (None, ''):
                        command_payload[key] = parameters.get(key)
                command = self.commands.enqueue(command_payload)
                if command.get('status') == 'PENDING':
                    command = self.commands.wait_for_approval(command['id'], decision_id=decision['id'])
                elif command.get('status') == 'WAITING_APPROVAL' and not command.get('approval_decision_id'):
                    command = self.commands.wait_for_approval(command['id'], decision_id=decision['id'])
        command_id = str((command or {}).get('id') or '')
        item = {
            'id': uuid4().hex,
            'decision_id': decision['id'],
            'command_id': command_id,
            'action': action,
            'parameters': parameters,
            'signature': signature,
            'target': target,
            'version': version,
            'source_channel': source_channel,
            'status': 'PENDING',
            'single_use': True,
            'created_at': stamp.isoformat(),
            'expires_at': (stamp + timedelta(seconds=self.ttl_seconds)).isoformat(),
            'prompt': prompt,
        }
        data.setdefault('items', []).append(item)
        self._save(data)
        self._audit(
            'conversation.approval.challenge',
            result='pending',
            details={
                'challenge_id': item['id'],
                'decision_id': item['decision_id'],
                'command_id': command_id,
                'action': action,
                'parameters': parameters,
                'source_channel': source_channel,
                'expires_at': item['expires_at'],
            },
        )
        return {'status': 'confirmation_required', 'challenge': dict(item), 'prompt': prompt}

    def confirm(self, challenge_id: str, confirmation_text: str, *, source_channel: str, parameters=None, now=None):
        challenge_id = str(challenge_id or '').strip()
        source_channel = str(source_channel or '').strip().lower()
        stamp = _utc(now)
        data = self._load()
        challenge = next((item for item in data.get('items', []) if item.get('id') == challenge_id), None)
        if challenge is None:
            return {'status': 'blocked', 'reason': 'challenge_missing'}
        if challenge.get('status') != 'PENDING':
            return {'status': 'blocked', 'reason': 'challenge_not_pending'}

        try:
            expires = datetime.fromisoformat(str(challenge.get('expires_at')).replace('Z', '+00:00'))
        except (TypeError, ValueError):
            expires = stamp - timedelta(seconds=1)
        if _utc(expires) < stamp:
            challenge['status'] = 'EXPIRED'
            challenge['expired_at'] = stamp.isoformat()
            self._save(data)
            self._audit(
                'conversation.approval.blocked',
                result='blocked',
                details={'challenge_id': challenge_id, 'reason': 'challenge_expired', 'source_channel': source_channel},
            )
            return {'status': 'blocked', 'reason': 'challenge_expired'}

        if parameters is not None:
            incoming_signature = _signature(challenge['action'], dict(parameters or {}))
            if incoming_signature != challenge.get('signature'):
                challenge['status'] = 'INVALIDATED'
                challenge['invalidated_at'] = stamp.isoformat()
                challenge['invalidated_reason'] = 'challenge_parameters_changed'
                self._save(data)
                self._audit(
                    'conversation.approval.blocked',
                    result='blocked',
                    details={
                        'challenge_id': challenge_id,
                        'reason': 'challenge_parameters_changed',
                        'source_channel': source_channel,
                    },
                )
                return {'status': 'blocked', 'reason': 'challenge_parameters_changed'}

        if not _explicit_confirmation(confirmation_text):
            return {
                'status': 'confirmation_required',
                'reason': 'explicit_second_confirmation_required',
                'challenge_id': challenge_id,
            }

        decision = self.decisions.get(challenge['decision_id'])
        if decision.get('status') != 'PENDING':
            return {'status': 'blocked', 'reason': 'canonical_decision_not_pending'}
        approved = self.decisions.resolve(challenge['decision_id'], approved=True, approved_by='Peter')
        challenge['status'] = 'CONFIRMED'
        challenge['confirmed_at'] = stamp.isoformat()
        challenge['confirmed_source_channel'] = source_channel
        challenge['confirmation_text'] = str(confirmation_text or '').strip()
        self._save(data)
        self._audit(
            'conversation.approval.confirmed',
            result='approved',
            details={
                'challenge_id': challenge_id,
                'decision_id': challenge['decision_id'],
                'source_channel': source_channel,
                'action': challenge['action'],
                'parameters': challenge['parameters'],
            },
        )
        return {
            'status': 'approved',
            'challenge_id': challenge_id,
            'decision': approved,
        }

    def pending(self):
        return [dict(item) for item in self._load().get('items', []) if item.get('status') == 'PENDING']
