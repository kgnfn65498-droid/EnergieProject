from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from roadmap_regie import RoadmapRegie
import self_audit


def base_spec():
    return {
        'schema': 'energie_projectmanager_canonical_roadmap_v3',
        'version': 3,
        'approved_by': 'Peter',
        'items': [
            {'key': 'a', 'title': 'A', 'status': 'OPEN', 'depends_on': []},
            {'key': 'b', 'title': 'B', 'status': 'OPEN', 'depends_on': ['a']},
        ],
    }


def test_validator_rejects_dependency_cycle_instead_of_silently_stalling():
    spec = base_spec()
    spec['items'][0]['depends_on'] = ['b']
    with pytest.raises(ValueError, match='dependency cycle'):
        RoadmapRegie._validate_spec(spec)


def test_validator_enforces_declared_pre_325_gates_as_cowork_ancestors():
    spec = {
        'schema': 'energie_projectmanager_canonical_roadmap_v3',
        'version': 3,
        'approved_by': 'Peter',
        'required_gates_before_32_5': ['voice-live-acceptance', 'new-chat-handover-live'],
        'items': [
            {'key': 'voice-live-acceptance', 'title': 'Voice', 'status': 'OPEN', 'depends_on': []},
            {'key': 'new-chat-handover-live', 'title': 'Handover', 'status': 'OPEN', 'depends_on': []},
            {'key': 'cowork-pilot', 'title': 'Cowork', 'status': 'OPEN', 'depends_on': []},
        ],
    }
    with pytest.raises(ValueError, match='required pre-32.5 gate'):
        RoadmapRegie._validate_spec(spec)


def test_validator_rejects_missing_declared_voice_gate():
    spec = {
        'schema': 'energie_projectmanager_canonical_roadmap_v3',
        'version': 3,
        'approved_by': 'Peter',
        'required_gates_before_32_5': ['voice-live-acceptance'],
        'items': [
            {'key': 'cowork-pilot', 'title': 'Cowork', 'status': 'OPEN', 'depends_on': []},
        ],
    }
    with pytest.raises(ValueError, match='missing required pre-32.5 gate'):
        RoadmapRegie._validate_spec(spec)


def test_approved_v3_migration_retains_ngrok_and_inserts_voice_and_handover_before_cowork(tmp_path):
    module_path = PM / 'canonical_roadmap_migration.py'
    assert module_path.is_file(), '32.4.23 canonical roadmap migration module must exist'
    spec = importlib.util.spec_from_file_location('canonical_roadmap_migration_v32423', module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    path = tmp_path / 'canonical_roadmap_v3.json'
    original = json.loads((ROOT / 'OVERDRACHT_CANONICAL_PLACEHOLDER.json').read_text()) if False else {
        'schema': 'energie_projectmanager_canonical_roadmap_v3',
        'version': 3,
        'approved_at': '2026-09-05',
        'approved_by': 'Peter',
        'source': 'conversation_2026-09-05_after_full_32.4.2_pm_audit',
        'principle': 'Projectmanager basis eerst volledig afronden; daarna gesprek-intake en proactieve PM; vervolgens Nomad, ngrok en Cowork in die volgorde.',
        'items': [
            {'key': 'conversation-intake', 'title': 'Conversation Intake', 'priority': 1, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': [], 'acceptance': 'x'},
            {'key': 'proactive-pm', 'title': 'Proactive', 'priority': 2, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['conversation-intake'], 'acceptance': 'x'},
            {'key': 'nomad-next', 'title': 'Nomad', 'priority': 3, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['proactive-pm'], 'acceptance': 'x'},
            {'key': 'ngrok-assessment', 'title': 'ngrok assess', 'priority': 4, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['nomad-next'], 'acceptance': 'x'},
            {'key': 'subscription-independence', 'title': 'Subscription', 'priority': 5, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['ngrok-assessment'], 'acceptance': 'x'},
            {'key': 'cowork-pilot', 'title': 'Cowork', 'priority': 6, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['subscription-independence'], 'acceptance': 'x'},
            {'key': 'month-import-next', 'title': 'Month', 'priority': 7, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['cowork-pilot'], 'acceptance': 'x'},
        ],
        'safety': {'production_deploy_requires_explicit_approval': True},
    }
    path.write_text(json.dumps(original), encoding='utf-8')

    first = module.migrate_canonical_roadmap(path)
    migrated = json.loads(path.read_text(encoding='utf-8'))
    second = module.migrate_canonical_roadmap(path)

    keys = [item['key'] for item in migrated['items']]
    by_key = {item['key']: item for item in migrated['items']}
    assert first['status'] == 'migrated'
    assert second['status'] == 'already_current'
    assert migrated['migration_release'] == '32.4.23'
    assert migrated['required_gates_before_32_5'] == [
        'ngrok-assessment', 'voice-live-acceptance', 'new-chat-handover-live'
    ]
    assert 'behouden' in by_key['ngrok-assessment']['title'].lower()
    assert keys.index('voice-live-acceptance') < keys.index('cowork-pilot')
    assert keys.index('new-chat-handover-live') < keys.index('cowork-pilot')
    RoadmapRegie._validate_spec(migrated)


def test_self_audit_semantic_helper_rejects_cycle():
    helper = getattr(self_audit, '_canonical_semantic_validation', None)
    assert callable(helper)
    spec = base_spec()
    spec['items'][0]['depends_on'] = ['b']
    result = helper(spec)
    assert result['ok'] is False
    assert 'dependency cycle' in result['reason']
