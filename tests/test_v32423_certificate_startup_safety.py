from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
MAIN = APP / 'main.py'
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import operating_mode_runtime as mode_runtime
from operating_modes import ModeState


def load_main(name='main_v32423_cert_startup'):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_core_revision_is_raised_for_scheduler_safety_change():
    m = load_main('main_v32423_core_rev')
    assert m.PRODUCTION_CORE_REVISION == '9.4-core3'


def test_startup_gate_requires_ok_recovery_known_closure_and_non_error_selftest():
    m = load_main('main_v32423_startup_gate_fn')
    fn = getattr(m, 'startup_recovery_ready', None)
    assert callable(fn)
    assert fn({'status': 'ok'}, {'truth': 'CLOSED_VALID'}, {'status': 'ok'}) is True
    assert fn({'status': 'attention'}, {'truth': 'CLOSED_VALID'}, {'status': 'ok'}) is False
    assert fn({'status': 'ok'}, {'truth': 'UNKNOWN'}, {'status': 'ok'}) is False
    assert fn({'status': 'ok'}, {'truth': 'OPEN'}, {'status': 'error'}) is False


def test_startup_sets_gate_only_after_selftest_and_semantic_readiness_check():
    source = MAIN.read_text(encoding='utf-8')
    start = source.index('def startup_self_test()')
    end = source.index('threading.Thread(target=startup_self_test', start)
    block = source[start:end]
    assert 'startup_recovery_ready(' in block
    assert block.index('result = run_self_test()') < block.index('STARTUP_RECOVERY_READY.set()')
    assert block.index('startup_recovery_ready(') < block.index('STARTUP_RECOVERY_READY.set()')


def _safe_observed():
    return {
        'workflow_running': False,
        'workflow_active': {},
        'cancel_requested': False,
        'run_on_start_effective': False,
        'schedule_effective': False,
        'full_workflow_effective': False,
        'automatic_month_close_effective': False,
        'release_processing': [],
    }


def test_release_hold_is_certificate_aware_and_allows_only_safe_core_mismatch_pending(monkeypatch, tmp_path):
    fake_app = SimpleNamespace(
        APP_VERSION='32.4.23',
        validate_production_certificate=lambda: {
            'valid': False,
            'integrity': 'ok',
            'production_core_revision': '9.4-core1',
            'checks': {
                'status_accepted': True,
                'core_revision_current': False,
                'scheduler_unchanged': True,
                'preflight_ok': True,
                'workflow_ok': True,
                'finalization_ok': True,
                'integrity_ok': True,
            },
        },
    )
    hold = SimpleNamespace(active=True)
    monkeypatch.setattr(mode_runtime, 'load_release_hold', lambda *_a, **_k: hold)
    monkeypatch.setattr(mode_runtime, 'load_mode_state', lambda *_a, **_k: ModeState.initial())
    monkeypatch.setattr(mode_runtime, 'observe_measured_runtime', lambda *_a, **_k: _safe_observed())
    monkeypatch.setattr(mode_runtime, '_web_runtime_check', lambda _a: {'ok': True, 'detail': 'ok'})
    monkeypatch.setattr(mode_runtime, '_state_io_check', lambda *_a: {'ok': True, 'detail': 'ok'})
    monkeypatch.setattr(mode_runtime, '_automatic_runtime_idle_check', lambda _o: {'ok': True, 'detail': 'idle'})
    monkeypatch.setattr(mode_runtime, '_release_chain_check', lambda *_a: {'ok': True, 'detail': 'idle'})
    monkeypatch.setattr(mode_runtime, '_projectmanager_self_audit_check', lambda *_a: {'ok': True, 'detail': 'green'})
    monkeypatch.setattr(
        mode_runtime,
        'reconcile_measured_runtime',
        lambda *_a, **_k: SimpleNamespace(reconciliation_status='ok', drift=()),
    )
    monkeypatch.setattr(mode_runtime, 'record_hold_validation', lambda *_a, **_k: None)

    result = mode_runtime.validate_release_hold(fake_app, tmp_path, '32.4.23')

    assert 'production_certificate' in result['checks']
    assert result['checks']['production_certificate']['ok'] is True
    assert 'pending recertification' in result['checks']['production_certificate']['detail']
    assert result['status'] == 'ok'


def test_release_hold_blocks_corrupt_or_semantically_invalid_certificate():
    check = getattr(mode_runtime, '_production_certificate_check', None)
    assert callable(check)
    corrupt = SimpleNamespace(validate_production_certificate=lambda: {
        'valid': False,
        'integrity': 'error',
        'checks': {'integrity_ok': False, 'core_revision_current': False},
    })
    result = check(corrupt)
    assert result['ok'] is False
