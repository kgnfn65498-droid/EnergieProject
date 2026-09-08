import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(APP))

from audit_log import AuditLog
from decision_queue import DecisionQueue

try:
    from conversation_approval import ConversationApprovalCoordinator
except ImportError as exc:  # TDD RED should be a behavior failure, not collection error.
    ConversationApprovalCoordinator = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def _coordinator(tmp_path, ttl=120):
    assert ConversationApprovalCoordinator is not None, f'conversation approval runtime missing: {IMPORT_ERROR}'
    decisions = DecisionQueue(tmp_path / 'decisions/queue.json')
    audit = AuditLog(tmp_path / 'audit/events.jsonl')
    return ConversationApprovalCoordinator(
        tmp_path / 'decisions/conversation_challenges.json', decisions, audit=audit, ttl_seconds=ttl
    ), decisions


def _request(coordinator, *, source='voice', now=None, parameters=None):
    return coordinator.request(
        action='production_deploy',
        parameters=parameters or {'version': '32.4.15', 'target': 'Home Assistant'},
        source_channel=source,
        now=now,
    )


def test_protected_voice_request_creates_bound_pending_challenge_not_approval(tmp_path):
    coordinator, decisions = _coordinator(tmp_path)
    result = _request(coordinator)
    assert result['status'] == 'confirmation_required'
    challenge = result['challenge']
    assert challenge['action'] == 'production_deploy'
    assert challenge['parameters'] == {'version': '32.4.15', 'target': 'Home Assistant'}
    assert challenge['version'] == '32.4.15'
    assert challenge['target'] == 'Home Assistant'
    assert challenge['source_channel'] == 'voice'
    assert decisions.get(challenge['decision_id'])['status'] == 'PENDING'
    assert '32.4.15' in result['prompt'] and 'Home Assistant' in result['prompt']


def test_second_explicit_voice_confirmation_approves_canonical_decision(tmp_path):
    coordinator, decisions = _coordinator(tmp_path)
    pending = _request(coordinator)
    challenge = pending['challenge']
    result = coordinator.confirm(
        challenge['id'], 'Ja, voer uit.', source_channel='voice',
        parameters={'version': '32.4.15', 'target': 'Home Assistant'},
    )
    assert result['status'] == 'approved'
    assert decisions.get(challenge['decision_id'])['status'] == 'APPROVED'
    assert decisions.get(challenge['decision_id'])['approved_by'] == 'Peter'


def test_typed_second_confirmation_is_equally_valid(tmp_path):
    coordinator, decisions = _coordinator(tmp_path)
    challenge = _request(coordinator)['challenge']
    result = coordinator.confirm(
        challenge['id'], 'Bevestig definitief en voer uit.', source_channel='chatgpt',
        parameters={'version': '32.4.15', 'target': 'Home Assistant'},
    )
    assert result['status'] == 'approved'
    assert decisions.get(challenge['decision_id'])['status'] == 'APPROVED'


def test_plain_yes_is_not_explicit_second_confirmation(tmp_path):
    coordinator, decisions = _coordinator(tmp_path)
    challenge = _request(coordinator)['challenge']
    result = coordinator.confirm(challenge['id'], 'ja', source_channel='voice')
    assert result['status'] == 'confirmation_required'
    assert decisions.get(challenge['decision_id'])['status'] == 'PENDING'


def test_parameter_change_invalidates_challenge_and_does_not_approve(tmp_path):
    coordinator, decisions = _coordinator(tmp_path)
    challenge = _request(coordinator)['challenge']
    result = coordinator.confirm(
        challenge['id'], 'Ja, voer uit.', source_channel='voice',
        parameters={'version': '32.4.16', 'target': 'Home Assistant'},
    )
    assert result['status'] == 'blocked'
    assert result['reason'] == 'challenge_parameters_changed'
    assert decisions.get(challenge['decision_id'])['status'] == 'PENDING'


def test_expired_or_replayed_challenge_cannot_approve_twice(tmp_path):
    t0 = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
    coordinator, decisions = _coordinator(tmp_path, ttl=30)
    expired = _request(coordinator, now=t0)['challenge']
    result = coordinator.confirm(expired['id'], 'Ja, voer uit.', source_channel='voice', now=t0 + timedelta(seconds=31))
    assert result['status'] == 'blocked' and result['reason'] == 'challenge_expired'
    assert decisions.get(expired['decision_id'])['status'] == 'PENDING'

    fresh = _request(coordinator, now=t0 + timedelta(minutes=2), parameters={'version': '32.4.15', 'target': 'Home Assistant Green'})['challenge']
    first = coordinator.confirm(fresh['id'], 'Ja, voer uit.', source_channel='voice', now=t0 + timedelta(minutes=2, seconds=1))
    second = coordinator.confirm(fresh['id'], 'Ja, voer uit.', source_channel='voice', now=t0 + timedelta(minutes=2, seconds=2))
    assert first['status'] == 'approved'
    assert second['status'] == 'blocked' and second['reason'] == 'challenge_not_pending'


def test_challenge_and_confirmation_are_audited_with_sources(tmp_path):
    coordinator, _ = _coordinator(tmp_path)
    challenge = _request(coordinator)['challenge']
    coordinator.confirm(challenge['id'], 'Ja, voer uit.', source_channel='speech')
    rows = [json.loads(line) for line in (tmp_path / 'audit/events.jsonl').read_text().splitlines()]
    assert [row['event_type'] for row in rows] == ['conversation.approval.challenge', 'conversation.approval.confirmed']
    assert rows[0]['details']['source_channel'] == 'voice'
    assert rows[1]['details']['source_channel'] == 'speech'
    assert rows[1]['details']['challenge_id'] == challenge['id']

def test_challenge_can_bind_same_canonical_decision_to_waiting_protected_command(tmp_path):
    from command_store import CommandStore
    decisions = DecisionQueue(tmp_path / 'decisions/queue.json')
    commands = CommandStore(tmp_path / 'commands/queue.json')
    coordinator = ConversationApprovalCoordinator(
        tmp_path / 'decisions/conversation_challenges.json', decisions, commands=commands
    )
    challenge = _request(coordinator)['challenge']
    assert challenge['command_id']
    command = commands.get(challenge['command_id'])
    assert command['status'] == 'WAITING_APPROVAL'
    assert command['intent'] == 'production_deploy'
    assert command['approval_decision_id'] == challenge['decision_id']
    assert command['release_version'] == '32.4.15'
    coordinator.confirm(challenge['id'], 'Ja, voer uit.', source_channel='voice')
    assert decisions.get(challenge['decision_id'])['status'] == 'APPROVED'
