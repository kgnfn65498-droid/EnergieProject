from __future__ import annotations

import importlib.util
import hashlib
import json
import time
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM)); sys.path.insert(0, str(APP))

from release_transition_worker import ReleaseTransitionWorker
from operating_modes import Mode, ModeState, save_mode_state, load_mode_state
import operating_mode_runtime as mode_runtime


def _load_installer_practical_module():
    path = ROOT / 'tests/test_v32455_installer_atomic_practical.py'
    spec = importlib.util.spec_from_file_location('v55_installer_practical_helpers', path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod



def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + '\n', encoding='utf-8')


def _control_plane_fingerprint(directory: Path) -> str:
    digest = hashlib.sha256()
    for name in ('control_plane.py', 'qnap_control_plane_bootstrap.py'):
        digest.update(name.encode('utf-8') + b'\0')
        digest.update((directory / name).read_bytes())
    return digest.hexdigest()


def _seed_real_preflight_54(root: Path) -> None:
    now = time.time()
    updated = datetime.now(timezone.utc).isoformat()
    inbox = root / 'Inbox'
    runtime = inbox / 'projectmanager_v2/RuntimeV2'

    save_mode_state(root, ModeState(base_mode=Mode.DEVELOPMENT, effective_mode=Mode.DEVELOPMENT))
    mode_path = inbox / 'operating_mode/operating_mode_state.json'
    mode = json.loads(mode_path.read_text(encoding='utf-8'))
    mode['reconciliation_status'] = 'ok'
    mode['drift'] = []
    _write_json(mode_path, mode)
    _write_json(inbox / 'operating_mode/release_validation_hold.json', {
        'active': False, 'release_version': '32.4.54', 'validation_status': 'ok', 'reconcile_status': 'ok',
    })
    _write_json(inbox / 'atomic_app_swap_state.json', {
        'state': 'ACCEPTED', 'from_version': '32.4.53', 'to_version': '32.4.54',
    })
    _write_json(runtime / 'release_transition/current.json', {
        'schema_version': 1, 'generation_id': 'terminal-54', 'revision': 100,
        'from_release': '32.4.53', 'to_release': '32.4.54',
        'lifecycle_state': 'COMPLETE', 'phase': 'COMPLETE', 'phase_status': 'GREEN',
        'previous_base_mode': 'DEVELOPMENT', 'completed_phases': ['COMPLETE'],
        'attempts': {}, 'evidence_refs': [], 'blocker': '', 'next_action': '', 'current_ticket': None,
    })
    _write_json(runtime / 'state/tasks.json', {'schema': 1, 'tasks': []})

    generation = 'preflight-final-54'
    checks = [
        {'name': 'release_watcher', 'status': 'GREEN'},
        {'name': 'watcher_container_contract', 'status': 'GREEN'},
        {'name': 'native_mcp_runtime', 'status': 'GREEN'},
        {'name': 'command_ingress_consumer', 'status': 'GREEN'},
    ]
    _write_json(runtime / 'status/current.json', {
        'schema': 'energie_projectmanager_status_v2', 'updated_at': updated,
        'cycle_generation': generation, 'provenance': {'generation': generation, 'phase': 'FINAL'},
        'release': {'version': '32.4.54', 'active_verified': True},
        'health': {'status': 'GREEN', 'checks': checks},
    })
    _write_json(runtime / 'self_audit/current.json', {
        'status': 'GREEN', 'status_updated_at': updated, 'cycle_generation': generation,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
        'missing': [], 'invalid': [], 'warnings': [],
    })
    _write_json(inbox / 'watcher_container_contract.json', {
        'status': 'GREEN', 'ready': True, 'contract_version': 3, 'reason': 'contract_match',
    })
    _write_json(inbox / 'native_mcp_runtime/runtime_guard.json', {
        'status': 'GREEN', 'ready': True,
        'expected_fingerprint': 'a' * 64, 'runtime_fingerprint': 'a' * 64,
    })

    ingress = root / 'Data/03_Systeem/Projectmanager/CommandIngress'
    ingress.mkdir(parents=True, exist_ok=True)
    _write_json(runtime / 'commands/ingress_receipts.json', {'schema': 1, 'items': {}})
    _write_json(runtime / 'commands/queue.json', {'schema': 1, 'items': []})

    cpdir = root / 'Data/03_Systeem/Projectmanager/ControlPlane'
    cpdir.mkdir(parents=True, exist_ok=True)
    pre57 = ROOT / 'tests/fixtures/pre57'
    for name in ('control_plane.py', 'qnap_control_plane_bootstrap.py'):
        shutil.copy2(pre57 / name, cpdir / name)
    _write_json(inbox / 'control_plane/runtime.json', {
        'schema': 'energie_control_plane_runtime_v1',
        'loaded_fingerprint': _control_plane_fingerprint(cpdir),
        'heartbeat_at_epoch': now, 'pid': 123,
    })

    spec = importlib.util.spec_from_file_location('v55_full_system_embedded_guard', ROOT / 'tools/embedded_pm_runtime_guard.py')
    assert spec and spec.loader
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    fingerprint = guard.expected_fingerprint(root)
    _write_json(runtime / 'embedded_runtime/current.json', {
        'schema': 'energie_embedded_pm_runtime_v1', 'status': 'GREEN',
        'loaded_runtime_fingerprint': fingerprint, 'runtime_release_version': '32.4.54',
        'cycle_generation': generation, 'provenance': {'generation': generation, 'phase': 'FINAL'},
        'observed_at_epoch': now,
    })

def _install_via_real_watcher_once(root: Path) -> subprocess.CompletedProcess[str]:
    tools = root / 'App/tools'
    tools.mkdir(parents=True, exist_ok=True)
    pre57 = ROOT / 'tests/fixtures/pre57'
    historical = {
        'release_watcher.sh': pre57 / 'release_watcher.sh',
        'release_installer.sh': pre57 / 'release_installer.sh',
        'release_preflight.py': pre57 / 'release_preflight.py',
        'control_plane_runtime_guard.py': pre57 / 'control_plane_runtime_guard.py',
    }
    for name in (
        'release_watcher.sh', 'release_installer.sh', 'release_ingress_recovery.py', 'release_zip.py',
        'release_preflight.py', 'control_plane_runtime_guard.py', 'embedded_pm_runtime_guard.py',
    ):
        source = historical.get(name, ROOT / 'tools' / name)
        shutil.copy2(source, tools / name)

    env = os.environ.copy()
    env.update({
        'ENERGIE_ROOT': str(root),
        'ENERGIE_WATCHER_REEXEC': '1',
        'ENERGIE_INSTALLER_REEXEC': '1',
        'ENERGIE_INGRESS_RECOVERY_STALE_SECONDS': '30',
        'ENERGIE_BACKUP_RETENTION': '3',
        'ENERGIE_PROCESSED_RETENTION': '3',
    })
    return subprocess.run(
        ['sh', str(tools / 'release_watcher.sh'), 'once'],
        env=env, text=True, capture_output=True, check=False, timeout=40,
    )


def _seed_runtime_and_drive_complete(monkeypatch, root: Path) -> tuple[ReleaseTransitionWorker, dict]:
    generation = 'full-system-final-generation'
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    status = {
        'schema': 'energie_projectmanager_status_v2',
        'release': {'version': '32.4.55'},
        'health': {'status': 'GREEN', 'checks': [
            {'name': 'native_mcp_runtime', 'status': 'GREEN'},
            {'name': 'project_crash_recovery_set', 'status': 'GREEN'},
            {'name': 'nas_container_crash_recovery_retention', 'status': 'GREEN'},
            {'name': 'project_structure_hygiene', 'status': 'GREEN'},
        ]},
        'cycle_generation': generation,
        'updated_at': '2026-09-15T16:30:00+00:00',
        'provenance': {'generation': generation, 'phase': 'FINAL'},
    }
    (runtime/'status').mkdir(parents=True, exist_ok=True)
    (runtime/'self_audit').mkdir(parents=True, exist_ok=True)
    (runtime/'status/current.json').write_text(json.dumps(status), encoding='utf-8')
    (runtime/'self_audit/current.json').write_text(json.dumps({
        'status': 'GREEN', 'invalid': [], 'warnings': [], 'missing': [],
        'cycle_generation': generation,
        'status_updated_at': '2026-09-15T16:30:00+00:00',
        'provenance': {'generation': generation, 'phase': 'FINAL'},
    }), encoding='utf-8')
    (root/'Inbox/logs/project_clearup_runtime.json').write_text(
        json.dumps({'status': 'completed'}), encoding='utf-8')
    save_mode_state(root, ModeState(base_mode=Mode.MAINTENANCE, effective_mode=Mode.MAINTENANCE))

    observed = {
        'workflow_running': False, 'workflow_active': {}, 'cancel_requested': False,
        'run_on_start_effective': False, 'schedule_effective': False,
        'full_workflow_effective': False, 'automatic_month_close_effective': False,
        'release_processing': [],
    }
    monkeypatch.setattr(mode_runtime, 'observe_measured_runtime', lambda *a, **k: dict(observed))
    monkeypatch.setattr(mode_runtime, '_web_runtime_check', lambda *a, **k: {'ok': True, 'detail': 'green'})
    monkeypatch.setattr(mode_runtime, '_state_io_check', lambda *a, **k: {'ok': True, 'detail': 'green'})
    monkeypatch.setattr(mode_runtime, '_production_certificate_check', lambda *a, **k: {'ok': True, 'detail': 'green'})
    monkeypatch.setattr(
        mode_runtime, 'reconcile_measured_runtime',
        lambda *a, **k: SimpleNamespace(reconciliation_status='ok', drift=()),
    )

    worker = ReleaseTransitionWorker(root, SimpleNamespace(APP_VERSION='32.4.55'))
    for _ in range(24):
        state = worker.run_once()
        if state.get('lifecycle_state') == 'COMPLETE':
            break
    return worker, worker.coord.load()


def test_zip_through_watcher_installer_acceptance_processed_and_complete_is_one_canonical_system(monkeypatch, tmp_path: Path):
    helpers = _load_installer_practical_module()
    root, release = helpers._project(tmp_path)
    assert release.is_file()
    assert (root/'App/VERSIE.txt').read_text().strip() == '32.4.54'
    _seed_real_preflight_54(root)

    watched = _install_via_real_watcher_once(root)
    assert watched.returncode == 0, watched.stdout + watched.stderr

    # ZIP -> Incoming -> watcher -> real installer -> live + processed.
    assert (root/'App/VERSIE.txt').read_text().strip() == '32.4.55'
    assert not list((root/'Inbox/incoming').glob('*.zip'))
    assert not list((root/'Inbox/processing').glob('*.zip'))
    processed = root/'Inbox/processed/EnergieProject_v32.4.55.zip'
    assert processed.is_file()
    atomic = json.loads((root/'Inbox/atomic_app_swap_state.json').read_text())
    assert atomic['state'] == 'LIVE_ACCEPTANCE'
    assert atomic['from_version'] == '32.4.54' and atomic['to_version'] == '32.4.55'
    transition = json.loads((root/'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json').read_text())
    assert transition['phase'] == 'TRANSITION_PREPARED'

    # Same project root continues through PM FINAL evidence -> hold/acceptance -> COMPLETE.
    worker, final = _seed_runtime_and_drive_complete(monkeypatch, root)
    assert final['lifecycle_state'] == 'COMPLETE'
    assert final['phase'] == 'COMPLETE'
    assert final['phase_status'] == 'GREEN'
    assert final['current_ticket'] is None and final['blocker'] == ''
    assert json.loads((root/'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
    hold = json.loads((root/'Inbox/operating_mode/release_validation_hold.json').read_text())
    assert hold['active'] is False and hold['validation_status'] == 'ok'
    mode = load_mode_state(root)
    assert mode.base_mode is Mode.DEVELOPMENT and mode.effective_mode is Mode.DEVELOPMENT
    assert worker.commands.all() == []
    assert processed.is_file()

    # Terminal end-state must remain stable, not spin after success.
    before_transition = worker.coord.path.read_bytes()
    before_mode = (root/'Inbox/operating_mode/operating_mode_state.json').read_bytes()
    final_revision = final['revision']
    for _ in range(100):
        again = worker.run_once()
        assert again['lifecycle_state'] == 'COMPLETE'
        assert again['revision'] == final_revision
    assert worker.coord.path.read_bytes() == before_transition
    assert (root/'Inbox/operating_mode/operating_mode_state.json').read_bytes() == before_mode
