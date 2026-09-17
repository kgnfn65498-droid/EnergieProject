from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / 'docs/recovery/32.4.55_bounded_recovery_runbook.json'


def _runbook() -> dict:
    value = json.loads(RUNBOOK.read_text(encoding='utf-8'))
    assert isinstance(value, dict)
    return value


def test_runbook_is_deterministic_bounded_and_has_no_free_shell():
    data = _runbook()
    assert data['release'] == '32.4.55'
    assert data['canonical_route'] == ['ZIP','Incoming','watcher','installer','live','acceptance','processed']
    assert data['max_actions_per_run'] == 5
    assert data['unknown_scenario_policy'] == 'STOP_NO_EXTRA_SHELL'
    assert data['rules']['no_free_shell'] is True
    assert data['rules']['no_manual_state_fabrication'] is True
    assert data['rules']['no_parallel_release_route'] is True
    catalog = data['action_catalog']
    for name, scenario in data['scenarios'].items():
        actions = scenario['actions']
        assert 1 <= len(actions) <= 5, name
        assert len(actions) == len(list(actions)), name
        assert all(action in catalog for action in actions), name


def test_every_mutating_action_has_precondition_scope_readback_and_postcondition():
    data = _runbook()
    for action_id, action in data['action_catalog'].items():
        assert action['precondition'], action_id
        assert action['side_effect_scope'], action_id
        assert action['readback'], action_id
        assert action['postcondition'], action_id
        if action_id not in {'READ_RELEASE_STATE','STOP_FAIL_CLOSED'}:
            assert action['executor'] in {'energie-release-watcher','existing_control_plane','bounded_external_terminal'}
            assert action['action']


def test_protected_runbook_actions_remain_approval_gated():
    data = _runbook()
    protected = {key for key, value in data['action_catalog'].items() if value['protected']}
    assert protected == {'WATCHER_RECREATE','NATIVE_MCP_RELOAD','CONTROL_PLANE_RESTART'}
    assert data['rules']['protected_actions_require_explicit_approval'] is True
    for scenario in data['scenarios'].values():
        actions = set(scenario['actions'])
        if actions & protected:
            assert any('approval' in item.lower() for item in scenario['preconditions'])


def test_unknown_recovery_stops_instead_of_growing_command_chain():
    data = _runbook()
    scenario = data['scenarios']['UNKNOWN_OR_BRANCHING_RECOVERY']
    assert scenario['actions'] == ['READ_RELEASE_STATE','STOP_FAIL_CLOSED']
    assert data['action_catalog']['STOP_FAIL_CLOSED']['side_effect_scope'] == 'none'



def test_stale_control_plane_has_one_exact_protected_restart_and_readback():
    data = _runbook()
    action = data['action_catalog']['CONTROL_PLANE_RESTART']
    assert action['protected'] is True
    assert action['action'] == 'docker restart energie-control-plane'
    scenario = data['scenarios']['CONTROL_PLANE_STALE_OR_DOWN']
    assert scenario['actions'] == ['READ_RELEASE_STATE','CONTROL_PLANE_RESTART','READ_RELEASE_STATE']
    assert 'runtime.json' in action['readback']
