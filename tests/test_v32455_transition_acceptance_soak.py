from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import' / 'rootfs' / 'app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(APP))

import operating_mode_runtime as mode_runtime
from release_validation_hold import activate_release_hold, load_release_hold, record_hold_validation
from release_transition_worker import ReleaseTransitionWorker


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')


def _pm_pair(root: Path, *, generation: str, audit_generation: str) -> None:
    version = root / 'App/VERSIE.txt'
    version.parent.mkdir(parents=True, exist_ok=True)
    version.write_text('32.4.55\n', encoding='utf-8')
    updated_at = '2026-09-15T15:00:00+00:00'
    _write_json(root / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json', {
        'schema': 'energie_projectmanager_status_v2',
        'release': {'version': '32.4.55'},
        'health': {'status': 'GREEN', 'checks': []},
        'cycle_generation': generation,
        'updated_at': updated_at,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
    })
    _write_json(root / 'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json', {
        'status': 'GREEN', 'invalid': [], 'warnings': [],
        'cycle_generation': audit_generation,
        'status_updated_at': updated_at,
        'provenance': {'generation': audit_generation, 'phase': 'FINAL'},
    })


def _worker_at_hold_valid(root: Path) -> tuple[ReleaseTransitionWorker, dict]:
    (root / 'App').mkdir(parents=True, exist_ok=True)
    (root / 'App/VERSIE.txt').write_text('32.4.55\n', encoding='utf-8')
    (root / 'Inbox/operating_mode').mkdir(parents=True, exist_ok=True)
    worker = ReleaseTransitionWorker(root, object())
    state = worker.coord.create_prepared('32.4.54', '32.4.55', previous_base_mode='DEVELOPMENT')
    for phase in ('APP_PROMOTED', 'RECONCILE_OLD_STATE', 'PM_CURRENT', 'NATIVE_RUNTIME_CURRENT', 'HOLD_VALID'):
        state = worker.coord.advance(
            expected_revision=state['revision'],
            expected_generation=state['generation_id'],
            phase=phase,
            phase_status='PENDING' if phase == 'HOLD_VALID' else 'GREEN',
        )
    activate_release_hold(root, '32.4.55', 'release_install')
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.54', 'to_version': '32.4.55',
    })
    return worker, state


def test_hold_valid_soak_waits_without_revision_or_command_spin_then_advances_on_new_final_evidence(monkeypatch, tmp_path: Path) -> None:
    root = tmp_path / 'energy'
    worker, initial = _worker_at_hold_valid(root)
    _pm_pair(root, generation='gen-new', audit_generation='gen-old')

    def focused_validate(_app, project_root, expected_version):
        check = mode_runtime._projectmanager_self_audit_check(project_root)
        checks = {'projectmanager_self_audit': check}
        hold = record_hold_validation(project_root, expected_version, checks, 'ok')
        return {
            'status': 'ok' if check['ok'] else 'blocked',
            'version': expected_version,
            'checks': checks,
            'reconcile_status': hold.reconcile_status,
            'drift': [],
        }

    finalize_calls: list[str] = []

    def finalize(project_root, expected_version):
        finalize_calls.append(expected_version)
        journal_path = Path(project_root) / 'Inbox/atomic_app_swap_state.json'
        payload = json.loads(journal_path.read_text(encoding='utf-8'))
        payload['state'] = 'ACCEPTED'
        _write_json(journal_path, payload)
        return {'status': 'accepted', 'state': 'ACCEPTED', 'version': expected_version}

    monkeypatch.setattr(mode_runtime, 'validate_release_hold', focused_validate)
    monkeypatch.setattr(mode_runtime, 'finalize_validated_atomic_release', finalize)

    first = worker.run_once()
    assert first['phase'] == 'HOLD_VALID'
    assert first['revision'] == initial['revision']
    hold_path = root / 'Inbox/operating_mode/release_validation_hold.json'
    blocked_hold_mtime = hold_path.stat().st_mtime_ns
    blocked_transition = worker.coord.path.read_bytes()

    for _ in range(99):
        current = worker.run_once()
        assert current['phase'] == 'HOLD_VALID'
        assert current['revision'] == initial['revision']
    assert worker.coord.path.read_bytes() == blocked_transition
    assert hold_path.stat().st_mtime_ns == blocked_hold_mtime
    assert worker.commands.all() == []
    assert finalize_calls == []
    assert load_release_hold(root, '32.4.55').active is True

    # New coherent FINAL evidence is the only thing that changes.
    _pm_pair(root, generation='gen-new', audit_generation='gen-new')
    advanced = worker.run_once()

    assert advanced['phase'] == 'ATOMIC_ACCEPTANCE_COMMITTED'
    assert advanced['revision'] == initial['revision'] + 1
    assert finalize_calls == ['32.4.55']
    assert json.loads((root / 'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
    assert load_release_hold(root, '32.4.55').active is False
    assert worker.commands.all() == []
