from __future__ import annotations

import importlib.util
import json
import os
import stat
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import' / 'rootfs' / 'app'
PM = APP / 'projectmanager_v2'


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _load_ingress_helper():
    path = ROOT / 'tools' / 'release_ingress_recovery.py'
    spec = importlib.util.spec_from_file_location('release_ingress_recovery_rebuild', path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _ingress_tree(root: Path) -> None:
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/failed', 'Inbox/logs'):
        (root / rel).mkdir(parents=True, exist_ok=True)


def test_runtimev2_json_defaults_to_cross_runtime_0666_and_rejects_symlink(tmp_path: Path):
    from persistence import atomic_write_json

    target = tmp_path / 'Inbox/projectmanager_v2/RuntimeV2/state/tasks.json'
    atomic_write_json(target, {'schema': 1})
    assert _mode(target) == 0o666
    assert _mode(target.parent) == 0o777

    target.chmod(0o600)
    atomic_write_json(target, {'schema': 1, 'updated': True})
    assert _mode(target) == 0o666

    outside = tmp_path / 'outside.json'
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(RuntimeError, match='symlink'):
        atomic_write_json(target, {'unsafe': True})
    assert target.is_symlink()
    assert not outside.exists()


def test_document_sync_preserves_existing_mode_and_rejects_symlink(tmp_path: Path):
    from document_sync import ManagedDocumentSync

    target = tmp_path / 'ACTUELE_STATUS.md'
    target.write_text('header\n', encoding='utf-8')
    target.chmod(0o666)

    result = ManagedDocumentSync().update(target, 'PROJECTMANAGER_V2', 'nieuw', placement='end')
    assert result['changed'] is True
    assert _mode(target) == 0o666

    outside = tmp_path / 'outside.md'
    outside.write_text('outside\n', encoding='utf-8')
    target.unlink()
    target.symlink_to(outside)
    with pytest.raises(RuntimeError, match='symlink'):
        ManagedDocumentSync().update(target, 'PROJECTMANAGER_V2', 'blocked')
    assert target.is_symlink()
    assert outside.read_text(encoding='utf-8') == 'outside\n'


def test_release_transition_shared_directory_and_json_modes(tmp_path: Path):
    from release_transition import ReleaseTransitionCoordinator

    root = tmp_path / 'energy'
    (root / 'Inbox').mkdir(parents=True)
    coordinator = ReleaseTransitionCoordinator(root)
    state = coordinator.create_prepared('32.4.54', '32.4.55')

    assert state['to_release'] == '32.4.55'
    assert _mode(coordinator.runtime) == 0o777
    assert _mode(coordinator.path) == 0o666


def test_release_transition_daemon_persists_worker_error(tmp_path: Path, monkeypatch):
    import release_transition_worker as mod

    class ExplodingWorker:
        def __init__(self, project_root, app_module):
            self.root = Path(project_root)

        def run_once(self):
            raise RuntimeError('boom-live-worker')

    class OneCycleStop:
        def __init__(self):
            self.waits = 0

        def is_set(self):
            return False

        def wait(self, interval):
            self.waits += 1
            return True

    monkeypatch.setattr(mod, 'ReleaseTransitionWorker', ExplodingWorker)
    root = tmp_path / 'energy'
    result = mod.release_transition_daemon(OneCycleStop(), object(), root, interval=0.01)

    status_path = root / 'Inbox/projectmanager_v2/RuntimeV2/release_transition/worker_status.json'
    assert result['lifecycle_state'] == 'BLOCKED'
    assert status_path.is_file()
    status = json.loads(status_path.read_text(encoding='utf-8'))
    assert status['status'] == 'RED'
    assert status['error'] == 'RuntimeError: boom-live-worker'
    assert _mode(status_path) == 0o666


def test_legacy_migration_classification_is_idempotent_for_ambiguous_task(tmp_path: Path):
    from release_ownership import migrate_legacy_tasks
    from task_engine import TaskStore

    runtime = tmp_path / 'Inbox/projectmanager_v2/RuntimeV2'
    task_path = runtime / 'state/tasks.json'
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task = {
        'id': 'legacy-ambiguous-1', 'title': 'Algemene taak', 'goal': 'geen releaseversie',
        'status': 'ACTIVE', 'mode': 'DEVELOPMENT', 'step': 1, 'steps_total': 1,
    }
    task_path.write_text(json.dumps({'schema': 1, 'tasks': [task]}), encoding='utf-8')
    store = TaskStore(task_path)

    first = migrate_legacy_tasks(store, project_root=tmp_path, current_release='32.4.55', evidence_ref='App/VERSIE.txt')
    second = migrate_legacy_tasks(store, project_root=tmp_path, current_release='32.4.55', evidence_ref='App/VERSIE.txt')

    index = runtime / 'release_ownership/legacy_index.jsonl'
    lines = [line for line in index.read_text(encoding='utf-8').splitlines() if line.strip()]
    assert first['classified'] == 1
    assert second['classified'] == 1
    assert len(lines) == 1
    assert json.loads(lines[0])['record_id'] == task['id']


@pytest.mark.parametrize('unsafe_part', ['lock', 'owner', 'heartbeat'])
def test_ingress_dangling_installer_symlinks_fail_closed_without_requeue(tmp_path: Path, unsafe_part: str):
    mod = _load_ingress_helper()
    _ingress_tree(tmp_path)
    processing = tmp_path / 'Inbox/processing/EnergieProject_v32.4.55.zip'
    processing.write_bytes(b'candidate')
    old = 1_000_000_000
    os.utime(processing, (old, old))

    lock = tmp_path / 'Inbox/.installer.lock'
    dangling_target = tmp_path / 'does-not-exist'
    if unsafe_part == 'lock':
        lock.symlink_to(dangling_target)
    else:
        lock.mkdir()
        if unsafe_part == 'owner':
            (lock / 'owner.json').symlink_to(dangling_target)
            (lock / 'heartbeat').write_text('1000000000', encoding='utf-8')
        else:
            (lock / 'owner.json').write_text(json.dumps({'pid': 99999999, 'started_at_epoch': old}), encoding='utf-8')
            (lock / 'heartbeat').symlink_to(dangling_target)
        os.utime(lock, (old, old))

    result = mod.reconcile(tmp_path, stale_seconds=60, now=old + 120)

    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'installer_lock_unsafe'
    assert processing.is_file()
    assert not list((tmp_path / 'Inbox/incoming').glob('*.zip'))
    assert not dangling_target.exists()


def test_docker_unix_image_export_default_read_timeout_is_large_enough_for_real_nas_cr():
    from docker_engine_unix_client import DockerEngineUnixClient

    client = DockerEngineUnixClient()
    assert client._timeout >= 600.0


def test_clearup_reaudits_wrapped_stale_plan_more_than_once_until_stable(tmp_path: Path, monkeypatch):
    import project_clearup_auto as auto

    monkeypatch.setattr(auto, 'clearup_auto_gate', lambda *a, **k: {'ready': True})
    plans = iter([
        {'plan_id': 'stale-1', 'clearup_count': 1, 'review_count': 0},
        {'plan_id': 'stale-2', 'clearup_count': 1, 'review_count': 0},
        {'plan_id': 'fresh-3', 'clearup_count': 1, 'review_count': 0},
    ])
    build_calls = []
    monkeypatch.setattr(auto, 'build_clearup_plan', lambda *a, **k: build_calls.append(1) or next(plans))
    applied = []

    def apply(*args, **kwargs):
        plan = args[1]
        applied.append(plan['plan_id'])
        if plan['plan_id'].startswith('stale'):
            raise RuntimeError(
                'CLEARUP watcher executor error: RuntimeError: '
                'CLEARUP-plan is gewijzigd; nieuwe dependency-audit vereist.'
            )
        return {'status': 'completed', 'delete_performed': False}

    monkeypatch.setattr(auto, '_apply_clearup_via_watcher', apply)
    progress = []
    result = auto.run_approved_clearup_once(
        tmp_path,
        app_version='32.4.55',
        timeout_seconds=10,
        progress_callback=lambda item: progress.append(item),
    )

    assert len(build_calls) == 3
    assert applied == ['stale-1', 'stale-2', 'fresh-3']
    assert result['plan_id'] == 'fresh-3'
    assert result['stale_plan_ids'] == ['stale-1', 'stale-2']
    assert result['replanned_after_stale'] is True
    assert sum(item.get('phase') == 'fresh_dependency_audit' for item in progress) == 2
    assert result['delete_performed'] is False


def test_clearup_runtime_budget_allows_multiple_real_nas_audits():
    source = (APP / 'main.py').read_text(encoding='utf-8')
    assert 'PROJECT_CLEARUP_MAX_SECONDS = 60 * 60' in source


def test_release_installer_normalizes_existing_runtimev2_before_transition_prepare():
    source = (ROOT / 'tools/release_installer.sh').read_text(encoding='utf-8')
    assert 'normalize_projectmanager_runtime_permissions()' in source
    assert 'find "$PM_RUNTIME" -type d -exec chmod 0777 {} +' in source
    assert 'find "$PM_RUNTIME" -type f -name "*.json" -exec chmod 0666 {} +' in source
    call = source.index('normalize_projectmanager_runtime_permissions')
    prepare = source.index('TRANSITION_PREPARED schrijven mislukt')
    assert call < prepare
