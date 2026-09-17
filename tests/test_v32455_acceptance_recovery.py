from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import operating_mode_runtime as mode_runtime
from operating_modes import ModeState, Mode
from release_validation_hold import activate_release_hold, load_release_hold


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _pm_status(root: Path, *, generation: str = 'gen-final', updated_at: str = '2026-09-15T16:00:00+00:00') -> Path:
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    _write_json(runtime / 'status/current.json', {
        'schema': 'energie_projectmanager_status_v2',
        'updated_at': updated_at,
        'cycle_generation': generation,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
        'release': {'version': '32.4.55', 'active_verified': True},
        'health': {'status': 'GREEN', 'checks': []},
    })
    return runtime


def _coherent_audit(runtime: Path, *, generation: str = 'gen-final', updated_at: str = '2026-09-15T16:00:00+00:00') -> None:
    _write_json(runtime / 'self_audit/current.json', {
        'status': 'GREEN',
        'status_updated_at': updated_at,
        'cycle_generation': generation,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
        'missing': [], 'invalid': [], 'warnings': [],
    })


def _prepare_hold_runtime(root: Path) -> tuple[object, Path]:
    (root / 'App').mkdir(parents=True, exist_ok=True)
    (root / 'App/VERSIE.txt').write_text('32.4.55\n', encoding='utf-8')
    runtime = _pm_status(root)
    activate_release_hold(root, '32.4.55', 'release_install')
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.54', 'to_version': '32.4.55',
    })
    app = SimpleNamespace(APP_VERSION='32.4.55')
    return app, runtime


def _patch_non_pm_checks_green(monkeypatch, root: Path) -> None:
    observed = {
        'workflow_running': False,
        'workflow_active': {},
        'cancel_requested': False,
        'run_on_start_effective': False,
        'schedule_effective': False,
        'full_workflow_effective': False,
        'automatic_month_close_effective': False,
        'release_processing': [],
    }
    monkeypatch.setattr(mode_runtime, 'observe_measured_runtime', lambda *args, **kwargs: dict(observed))
    monkeypatch.setattr(mode_runtime, '_web_runtime_check', lambda *args, **kwargs: {'ok': True, 'detail': 'green'})
    monkeypatch.setattr(mode_runtime, '_state_io_check', lambda *args, **kwargs: {'ok': True, 'detail': 'green'})
    monkeypatch.setattr(mode_runtime, '_production_certificate_check', lambda *args, **kwargs: {'ok': True, 'detail': 'green'})
    monkeypatch.setattr(
        mode_runtime,
        'reconcile_measured_runtime',
        lambda *args, **kwargs: SimpleNamespace(reconciliation_status='ok', drift=()),
    )

    def accept(project_root, expected):
        journal = Path(project_root) / 'Inbox/atomic_app_swap_state.json'
        payload = json.loads(journal.read_text(encoding='utf-8'))
        payload['state'] = 'ACCEPTED'
        _write_json(journal, payload)
        return {'status': 'accepted', 'state': 'ACCEPTED', 'version': expected}

    monkeypatch.setattr(mode_runtime, 'finalize_validated_atomic_release', accept)


def test_mismatched_final_snapshot_blocks_then_next_coherent_final_auto_releases(monkeypatch, tmp_path: Path):
    app, runtime = _prepare_hold_runtime(tmp_path)
    _patch_non_pm_checks_green(monkeypatch, tmp_path)
    _write_json(runtime / 'self_audit/current.json', {
        'status': 'GREEN',
        'status_updated_at': '2026-09-15T15:59:59+00:00',
        'cycle_generation': 'old-generation',
        'provenance': {'generation': 'old-generation', 'phase': 'FINAL'},
        'missing': [], 'invalid': [], 'warnings': [],
    })

    first = mode_runtime.attempt_release_hold(app, tmp_path, '32.4.55', issued_by='release_transition_coordinator')
    assert first['status'] == 'blocked'
    assert json.loads((tmp_path/'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'LIVE_ACCEPTANCE'
    assert load_release_hold(tmp_path, '32.4.55').active is True

    _coherent_audit(runtime)
    second = mode_runtime.attempt_release_hold(app, tmp_path, '32.4.55', issued_by='release_transition_coordinator')

    assert second['status'] == 'released'
    assert json.loads((tmp_path/'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
    assert load_release_hold(tmp_path, '32.4.55').active is False


def test_half_written_audit_blocks_then_coherent_final_auto_releases(monkeypatch, tmp_path: Path):
    app, runtime = _prepare_hold_runtime(tmp_path)
    _patch_non_pm_checks_green(monkeypatch, tmp_path)
    audit_path = runtime / 'self_audit/current.json'
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text('{"status":"GREEN",', encoding='utf-8')

    first = mode_runtime.attempt_release_hold(app, tmp_path, '32.4.55', issued_by='release_transition_coordinator')
    assert first['status'] == 'blocked'
    assert json.loads((tmp_path/'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'LIVE_ACCEPTANCE'

    _coherent_audit(runtime)
    second = mode_runtime.attempt_release_hold(app, tmp_path, '32.4.55', issued_by='release_transition_coordinator')

    assert second['status'] == 'released'
    assert json.loads((tmp_path/'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
