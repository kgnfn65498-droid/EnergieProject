from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'


def load_module(name: str, filename: str):
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    spec = importlib.util.spec_from_file_location(name, APP / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def rollback(root: Path, version: str, files: int = 1):
    path = root / f'App.__rollback_{version}'
    path.mkdir(parents=True)
    (path / 'VERSIE.txt').write_text(version, encoding='utf-8')
    for idx in range(files):
        (path / f'payload-{idx}.txt').write_text('stable', encoding='utf-8')


def ready_root(root: Path, version: str = '32.4.29') -> None:
    (root / 'CLEARUP').mkdir(parents=True, exist_ok=True)
    approval = root / 'Data/03_Systeem/Projectmanager/State/32_4_25_scope_cleanup_and_history_repair_20260909.md'
    approval.parent.mkdir(parents=True, exist_ok=True)
    approval.write_text('Status: DEVELOPMENT SCOPE APPROVED BY USER\nCLEARUP\n', encoding='utf-8')

    atomic = root / 'Inbox/atomic_app_swap_state.json'
    atomic.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_text(json.dumps({'state': 'ACCEPTED', 'to_version': version, 'rollback_path': 'App.__rollback_32.4.28'}), encoding='utf-8')

    hold = root / 'Inbox/operating_mode/release_validation_hold.json'
    hold.parent.mkdir(parents=True, exist_ok=True)
    hold.write_text(json.dumps({'active': False, 'validation_status': 'ok'}), encoding='utf-8')

    cr = root / 'Backups/CrashRecovery'
    cr.mkdir(parents=True, exist_ok=True)
    backup = cr / '2026-09-10 10.00 CrashRecovery EnergieProject.zip'
    backup.write_bytes(b'tiny-test-backup')
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    stem = backup.with_suffix('')
    Path(str(stem) + '.sha256').write_text(f'{digest}  {backup.name}\n', encoding='utf-8')
    Path(str(stem) + '.manifest.json').write_text(json.dumps({'file_count': 1}), encoding='utf-8')
    Path(str(stem) + '.restore.txt').write_text('RESTORE VERIFIED\n', encoding='utf-8')


def test_run_reports_permanent_ordered_phases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    auto = load_module('project_clearup_auto_32429_progress', 'project_clearup_auto.py')
    ready_root(tmp_path)
    for version in ('32.4.20', '32.4.21', '32.4.22', '32.4.23'):
        rollback(tmp_path, version)

    events = []

    def local_executor(root, plan, *, run_id, deadline_monotonic, progress_callback, started_monotonic, pre_acceptance=False):
        return auto.apply_clearup_plan(
            root, plan, confirmation=plan['confirmation_required'], run_id=run_id,
            deadline_monotonic=deadline_monotonic, progress_callback=progress_callback,
            started_monotonic=started_monotonic,
        )

    monkeypatch.setattr(auto, '_apply_clearup_via_watcher', local_executor)
    result = auto.run_approved_clearup_once(
        tmp_path,
        app_version='32.4.29',
        run_id='progress-proof',
        timeout_seconds=30,
        progress_callback=lambda event: events.append(dict(event)),
    )

    assert result['status'] == 'completed'
    phases = [event['phase'] for event in events]
    expected = ['gate', 'crash_recovery_check', 'candidate_inventory', 'dependency_index', 'candidate_hash', 'apply', 'manifest']
    positions = [phases.index(phase) for phase in expected]
    assert positions == sorted(positions)
    assert all('elapsed_seconds' in event for event in events)
    candidate_events = [event for event in events if event['phase'] == 'candidate_hash']
    assert candidate_events
    assert all(event['candidate_index'] >= 1 and event['candidate_total'] >= event['candidate_index'] for event in candidate_events)


def test_expired_deadline_stops_before_any_move(tmp_path: Path):
    clearup = load_module('project_clearup_32429_timeout', 'project_clearup.py')
    for version in ('32.4.20', '32.4.21', '32.4.22', '32.4.23'):
        rollback(tmp_path, version, files=4)
    plan = clearup.build_clearup_plan(tmp_path, current_version='32.4.29', keep_rollbacks=3)
    source = tmp_path / 'App.__rollback_32.4.20'

    with pytest.raises(clearup.ClearupExecutionTimeout) as exc:
        clearup.apply_clearup_plan(
            tmp_path,
            plan,
            confirmation=plan['confirmation_required'],
            run_id='deadline-proof',
            deadline_monotonic=time.monotonic() - 0.01,
        )

    assert exc.value.phase
    assert source.exists()
    assert not (tmp_path / 'CLEARUP/deadline-proof').exists()


def test_crash_recovery_hash_honours_deadline(tmp_path: Path):
    auto = load_module('project_clearup_auto_32429_cr_timeout', 'project_clearup_auto.py')
    payload = tmp_path / 'backup.zip'
    payload.write_bytes(b'x' * (2 * 1024 * 1024))

    with pytest.raises(auto.ClearupExecutionTimeout) as exc:
        auto._sha256(payload, deadline_monotonic=time.monotonic() - 0.01)

    assert exc.value.phase == 'crash_recovery_check'


def test_main_wires_live_checkpoint_writer_and_hard_timeout():
    source = (APP / 'main.py').read_text(encoding='utf-8')
    assert 'project_clearup_runtime.json' in source
    assert 'progress_callback=' in source
    assert 'timeout_seconds=' in source


def test_persisted_clearup_runtime_checkpoint_is_observational(tmp_path: Path):
    clearup = load_module('project_clearup_32429_runtime_checkpoint', 'project_clearup.py')
    for version in ('32.4.20', '32.4.21', '32.4.22', '32.4.23'):
        rollback(tmp_path, version)
    runtime = tmp_path / 'Data/03_Systeem/Projectmanager/State/project_clearup_runtime.json'
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(json.dumps({'phase': 'candidate_hash', 'candidate': 'App.__rollback_32.4.20'}), encoding='utf-8')

    plan = clearup.build_clearup_plan(tmp_path, current_version='32.4.29', keep_rollbacks=3)
    item = next(i for i in plan['items'] if i['source_path'] == 'App.__rollback_32.4.20')
    assert item['disposition'] == 'CLEARUP'
    assert any(ref['path'].endswith('project_clearup_runtime.json') for ref in item['informational_references'])
