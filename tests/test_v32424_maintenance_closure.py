from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
MAIN = APP / 'main.py'
for p in (APP, PM):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def load_main(name: str):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_legacy_lifecycle_closed_conflicting_with_recovery_open_is_unknown(monkeypatch):
    m = load_main('main_v32424_legacy_conflict')
    calls = []

    def fake_call(name, arguments, timeout=8.0, *, use_cache=True):
        calls.append((name, use_cache))
        if name == 'month_closure_status':
            return {'month': '2026_07', 'closed': False, 'status_file': None, 'status': None}
        if name == 'workflow_month_status':
            return {'month': '2026_07', 'stage': 'CLOSED', 'exists': True, 'note': 'legacy complete'}
        raise AssertionError(name)

    monkeypatch.setattr(m, '_mcp_call_project_tool', fake_call)
    proof = m.recovery_month_closure_proof('2026_07')

    assert proof['truth'] == 'UNKNOWN'
    assert proof['closed'] is False
    assert 'legacy' in (proof.get('error') or '').lower() or 'conflict' in (proof.get('error') or '').lower()
    assert ('month_closure_status', False) in calls
    assert ('workflow_month_status', False) in calls


def test_non_mutating_core_acceptance_never_calls_month_workflow(monkeypatch, tmp_path):
    m = load_main('main_v32424_nonmutating_acceptance')
    workflow_calls = []
    monkeypatch.setattr(m, 'run_full_month_workflow', lambda *a, **k: workflow_calls.append((a, k)) or {'status': 'completed'})
    monkeypatch.setattr(m, 'run_self_test', lambda: {'status': 'ok', 'checks': []})
    monkeypatch.setattr(m, 'load_state', lambda: {})
    monkeypatch.setattr(m, 'update_state', lambda **kw: None)
    monkeypatch.setattr(m, 'append_audit_event', lambda *a, **k: None)
    monkeypatch.setattr(m, 'PRODUCTION_CERTIFICATE_PATH', tmp_path / 'production_certificate.json')
    monkeypatch.setattr(m, 'PRODUCTION_CERTIFICATE_HISTORY_PATH', tmp_path / 'production_certificate_history.jsonl')

    result = m.run_non_mutating_core_acceptance()

    assert result['status'] == 'completed'
    assert result['month_mutation'] is False
    assert result['production_core_revision'] == m.PRODUCTION_CORE_REVISION
    assert workflow_calls == []
    cert = m.write_non_mutating_core_acceptance(result)
    validation = m.validate_production_certificate(cert)
    assert validation['valid'] is True
    assert cert['test_type'] == 'non_mutating_core_safety'


def test_roadmap_migration_permission_denied_returns_runtime_spec(monkeypatch, tmp_path):
    module_path = PM / 'canonical_roadmap_migration.py'
    spec = importlib.util.spec_from_file_location('migration_v32424_permission', module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)

    original = {
        'schema': 'energie_projectmanager_canonical_roadmap_v3',
        'version': 3,
        'approved_at': '2026-09-05',
        'approved_by': 'Peter',
        'source': 'baseline',
        'items': [
            {'key': 'conversation-intake', 'title': 'Conversation', 'priority': 1, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': [], 'acceptance': 'x'},
            {'key': 'proactive-pm', 'title': 'Proactive', 'priority': 2, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['conversation-intake'], 'acceptance': 'x'},
            {'key': 'nomad-next', 'title': 'Nomad', 'priority': 3, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['proactive-pm'], 'acceptance': 'x'},
            {'key': 'ngrok-assessment', 'title': 'ngrok', 'priority': 4, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['nomad-next'], 'acceptance': 'x'},
            {'key': 'subscription-independence', 'title': 'Subscription', 'priority': 5, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['ngrok-assessment'], 'acceptance': 'x'},
            {'key': 'cowork-pilot', 'title': 'Cowork', 'priority': 6, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['subscription-independence'], 'acceptance': 'x'},
            {'key': 'month-import-next', 'title': 'Month', 'priority': 7, 'mode': 'USER', 'executor': 'handoff', 'auto_select': True, 'status': 'OPEN', 'depends_on': ['cowork-pilot'], 'acceptance': 'x'},
        ],
        'safety': {'production_deploy_requires_explicit_approval': True},
    }
    path = tmp_path / 'canonical_roadmap_v3.json'
    path.write_text(json.dumps(original), encoding='utf-8')

    def denied(*_a, **_k):
        raise PermissionError('directory is read-only to addon')

    monkeypatch.setattr(module, 'atomic_write_json', denied)
    result = module.migrate_canonical_roadmap(path)

    assert result['status'] == 'migrated_read_only'
    assert result['persistence_required'] is True
    assert result['spec']['migration_release'] == '32.4.23'
    assert path.read_text(encoding='utf-8') == json.dumps(original)


def test_recovery_open_with_unavailable_lifecycle_truth_fails_closed(monkeypatch):
    m = load_main('main_v32424_lifecycle_unavailable')

    def fake_call(name, arguments, timeout=8.0, *, use_cache=True):
        if name == 'month_closure_status':
            return {'month': '2026_07', 'closed': False, 'status_file': None, 'status': None}
        if name == 'workflow_month_status':
            return None
        raise AssertionError(name)

    monkeypatch.setattr(m, '_mcp_call_project_tool', fake_call)
    proof = m.recovery_month_closure_proof('2026_07')
    assert proof['truth'] == 'UNKNOWN'
    assert proof['closed'] is False
    assert 'unavailable' in (proof.get('error') or '').lower()


def test_manage_certificate_rejects_tampered_non_mutating_evidence_and_reruns(monkeypatch, tmp_path):
    m = load_main('main_v32424_manage_evidence')
    monkeypatch.setattr(m, 'PRODUCTION_CERTIFICATE_PATH', tmp_path / 'production_certificate.json')
    monkeypatch.setattr(m, 'PRODUCTION_CERTIFICATE_HISTORY_PATH', tmp_path / 'production_certificate_history.jsonl')
    monkeypatch.setattr(m, 'PRODUCTION_CERTIFICATE_MANAGEMENT_PATH', tmp_path / 'production_certificate_management.json')
    monkeypatch.setattr(m, 'append_audit_event', lambda *a, **k: None)
    monkeypatch.setattr(m, 'update_state', lambda **kw: None)

    tampered = {
        'version': m.APP_VERSION,
        'production_core_revision': m.PRODUCTION_CORE_REVISION,
        'status': 'completed',
        'test_type': 'non_mutating_core_safety',
        'month_mutation': False,
        'scheduler_state_changed': False,
        'checks': [{'name': 'unknown_fail_closed', 'status': 'error'}],
    }
    state = {'automatic_month_close_test_last_result': {}, 'production_core_acceptance_last_result': tampered}
    monkeypatch.setattr(m, 'load_state', lambda: state)
    reruns = []

    def good_acceptance():
        reruns.append(True)
        return {
            'version': m.APP_VERSION,
            'production_core_revision': m.PRODUCTION_CORE_REVISION,
            'tested_at': '2026-09-09T18:00:00+02:00',
            'status': 'completed',
            'test_type': 'non_mutating_core_safety',
            'month_mutation': False,
            'scheduler_state_changed': False,
            'checks': [{'name': 'unknown_fail_closed', 'status': 'ok'}],
        }

    monkeypatch.setattr(m, 'run_non_mutating_core_acceptance', good_acceptance)
    result = m.manage_production_certificate(allow_repair=True)

    assert reruns == [True]
    assert result['valid'] is True
    assert result['action'] == 'generated_from_non_mutating_core_acceptance'
