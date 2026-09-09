from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
MAIN = APP / 'main.py'


def load_main(name='main_v32423_month_safety'):
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def options(**overrides):
    values = dict(
        automatic_month_close_enabled=True,
        automatic_month_close_day=1,
        automatic_month_close_hour=0,
        automatic_month_close_retry_hours=6,
        transfer_enabled=False,
        transfer_share_folder='transfer',
        report_service_enabled=False,
    )
    values.update(overrides)
    return SimpleNamespace(**values)


def closed_payload(*, deep_verified=True, hash_failures=None):
    return {
        'month': '2026_08',
        'closed': True,
        'status_file': '/recovery/Status/MonthClosure_2026_08.json',
        'status': {
            'status': 'CLOSED',
            'validation': {'status': 'ok'},
            'verification': {
                'status': 'valid',
                'deep_verified': deep_verified,
                'hash_failures': [] if hash_failures is None else hash_failures,
            },
        },
    }


def test_recovery_proof_requires_deep_verified_canonical_closed(monkeypatch):
    m = load_main('main_v32423_truth_deep')
    monkeypatch.setattr(m, '_mcp_call_project_tool', lambda *a, **k: closed_payload(deep_verified=False))
    proof = m.recovery_month_closure_proof('2026_08')
    assert proof['truth'] == 'UNKNOWN'
    assert proof['closed'] is False


def test_unknown_recovery_truth_fails_closed_in_scheduler(monkeypatch):
    m = load_main('main_v32423_truth_unknown_due')
    monkeypatch.setattr(m, 'automatic_production_readiness', lambda: {'ready': True})
    monkeypatch.setattr(m, 'automatic_month_is_completed', lambda _month: False)
    monkeypatch.setattr(m, 'load_state', lambda: {})
    monkeypatch.setattr(
        m,
        'recovery_month_closure_proof',
        lambda _month: {'truth': 'UNKNOWN', 'closed': False, 'evidence': None, 'error': 'timeout'},
    )
    assert m.automatic_month_close_due(
        options(), datetime(2026, 9, 9, 13, 0, tzinfo=m.TZ)
    ) is None


def test_open_recovery_truth_remains_scheduler_eligible(monkeypatch):
    m = load_main('main_v32423_truth_open_due')
    monkeypatch.setattr(m, 'automatic_production_readiness', lambda: {'ready': True})
    monkeypatch.setattr(m, 'automatic_month_is_completed', lambda _month: False)
    monkeypatch.setattr(m, 'load_state', lambda: {})
    monkeypatch.setattr(
        m,
        'recovery_month_closure_proof',
        lambda _month: {'truth': 'OPEN', 'closed': False, 'evidence': None},
    )
    assert m.automatic_month_close_due(
        options(), datetime(2026, 9, 9, 13, 0, tzinfo=m.TZ)
    ) == '2026_08'


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self):
        return json.dumps({'result': {'structuredContent': self.payload}}).encode('utf-8')


def test_month_closure_status_is_dynamic_and_never_reuses_stale_open_cache(monkeypatch):
    m = load_main('main_v32423_truth_cache')
    m._MCP_TOOL_CACHE.clear()
    payloads = [
        {'month': '2026_08', 'closed': False, 'status_file': None, 'status': None},
        closed_payload(),
    ]
    calls = []
    def urlopen(_request, timeout=0):
        calls.append(timeout)
        return FakeResponse(payloads.pop(0))
    monkeypatch.setattr(m.urllib.request, 'urlopen', urlopen)

    first = m.recovery_month_closure_proof('2026_08')
    second = m.recovery_month_closure_proof('2026_08')

    assert first['truth'] == 'OPEN'
    assert second['truth'] == 'CLOSED_VALID'
    assert len(calls) == 2


def test_preflight_blocks_closed_valid_before_mutating_workflow(monkeypatch, tmp_path):
    m = load_main('main_v32423_preflight_closed')
    monkeypatch.setattr(m, 'OUTPUT_ROOT', tmp_path / 'output')
    monkeypatch.setattr(
        m,
        'recovery_month_closure_proof',
        lambda _month: {'truth': 'CLOSED_VALID', 'closed': True, 'evidence': 'deep verified'},
    )
    result = m.automatic_month_close_preflight(options(), '2026_08')
    assert result['status'] == 'blocked_closed_valid'
    assert any(check['name'] == 'month_closure_truth' for check in result['checks'])


def test_executor_has_independent_closed_guard_before_running_state(monkeypatch):
    m = load_main('main_v32423_executor_closed')
    retry_writes = []
    workflow_calls = []
    monkeypatch.setattr(
        m,
        'recovery_month_closure_proof',
        lambda _month: {'truth': 'CLOSED_VALID', 'closed': True, 'evidence': 'deep verified'},
    )
    monkeypatch.setattr(m, 'write_automatic_retry_state', lambda **kw: retry_writes.append(kw) or kw)
    monkeypatch.setattr(m, 'update_state', lambda **_kw: None)
    monkeypatch.setattr(m, 'automatic_month_close_preflight', lambda *_a, **_k: {'status': 'ok', 'checks': [], 'errors': []})
    monkeypatch.setattr(m, 'run_full_month_workflow', lambda *a, **k: workflow_calls.append((a, k)) or {'status': 'completed', 'started_at': '', 'finished_at': '', 'duration_seconds': 0})
    monkeypatch.setattr(m, 'automatic_month_close_finalize', lambda *a, **k: {'status': 'ok'})
    monkeypatch.setattr(m, 'Options', SimpleNamespace(load=lambda: options()))
    monkeypatch.setattr(m, 'append_finalization_debug', lambda *a, **k: None)
    monkeypatch.setattr(m, 'append_automatic_run_history', lambda row: row)
    monkeypatch.setattr(m, 'mark_automatic_month_completed', lambda *a, **k: {})
    monkeypatch.setattr(m, 'automatic_month_is_completed', lambda _month: False)
    monkeypatch.setattr(m, 'read_automatic_retry_state', lambda: {})
    monkeypatch.setattr(m, 'automatic_history_proves_completed', lambda _month: False)

    result = m.execute_automatic_month_close(options(), '2026_08', trigger='automatic')

    assert result['status'] == 'blocked_closed_valid'
    assert retry_writes == []
    assert workflow_calls == []
