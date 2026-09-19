from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
import sys
sys.path.insert(0, str(PM)); sys.path.insert(0, str(APP))
from release_transition_worker import ReleaseTransitionWorker

INSTALLER = ROOT / 'tests/fixtures/pre57/release_installer.sh'
RECOVERY = ROOT / 'tools/release_ingress_recovery.py'


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_tree(root: Path, *, version: str, pm_version: str, candidate: bool) -> None:
    files: dict[str, bytes] = {
        'README.md': b'readme\n',
        'INSTALL.md': b'install\n',
        'CHANGELOG.md': f'# {version}\n'.encode(),
        'repository.yaml': b'name: EnergieProject\n',
        'VERSIE.txt': f'{version}\n'.encode(),
        'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt': f'{pm_version}\n'.encode(),
        'slimmemeterportal_import/rootfs/app/projectmanager_v2/probe.py': f"RELEASE = '{version}'\n".encode(),
        'tools/atomic_app_swap.py': (ROOT / 'tools/atomic_app_swap.py').read_bytes(),
        'tools/release_zip.py': (ROOT / 'tools/release_zip.py').read_bytes(),
    }
    if candidate:
        sources = {
            'tools/release_transition_prepare.py': ROOT / 'tools/release_transition_prepare.py',
            'tools/release_installer.sh': ROOT / 'tests/fixtures/pre57/release_installer.sh',
            'tools/release_watcher.sh': ROOT / 'tests/fixtures/pre57/release_watcher.sh',
            'slimmemeterportal_import/rootfs/app/projectmanager_v2/release_transition.py':
                ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2/release_transition.py',
            'slimmemeterportal_import/rootfs/app/transition_state_io.py':
                ROOT / 'slimmemeterportal_import/rootfs/app/transition_state_io.py',
        }
        for rel, source in sources.items():
            files[rel] = source.read_bytes()
    root.mkdir(parents=True, exist_ok=True)
    for rel, data in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = ''.join(f'{_sha(data)}  {rel}\n' for rel, data in sorted(files.items()))
    sums = {'files': [{'path': rel, 'sha256': _sha(data)} for rel, data in sorted(files.items())]}
    (root / 'MANIFEST.sha256').write_text(manifest, encoding='utf-8')
    (root / 'SHA256SUMS.json').write_text(json.dumps(sums, sort_keys=True), encoding='utf-8')


def _zip_tree(tree: Path, target: Path) -> None:
    with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(tree.rglob('*')):
            if path.is_file():
                zf.write(path, path.relative_to(tree).as_posix())


def _project(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / 'energy'
    app = root / 'App'
    _write_tree(app, version='32.4.54', pm_version='2.0.0-rc41', candidate=False)
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed', 'Inbox/logs', 'Backups'):
        (root / rel).mkdir(parents=True, exist_ok=True)
    candidate_tree = tmp_path / 'candidate'
    _write_tree(candidate_tree, version='32.4.55', pm_version='2.0.0-rc42', candidate=True)
    release = root / 'Inbox/incoming/EnergieProject_v32.4.55.zip'
    _zip_tree(candidate_tree, release)
    return root, release


def _run_installer(root: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update({
        'ENERGIE_ROOT': str(root),
        'ENERGIE_INSTALLER_REEXEC': '1',
        'ENERGIE_BACKUP_RETENTION': '3',
        'ENERGIE_PROCESSED_RETENTION': '3',
    })
    return subprocess.run(
        ['sh', str(INSTALLER)], env=env, text=True, capture_output=True,
        check=False, timeout=30,
    )


def _state(root: Path) -> dict:
    return json.loads((root / 'Inbox/atomic_app_swap_state.json').read_text(encoding='utf-8'))


def test_real_installer_atomic_flow_is_exactly_once_through_live_acceptance(tmp_path: Path):
    root, release = _project(tmp_path)
    artifact_sha = hashlib.sha256(release.read_bytes()).hexdigest()

    first = _run_installer(root)
    assert first.returncode == 0, first.stdout + first.stderr

    assert (root / 'App/VERSIE.txt').read_text().strip() == '32.4.55'
    assert (root / 'App.__rollback_32.4.54/VERSIE.txt').read_text().strip() == '32.4.54'
    state = _state(root)
    assert state['state'] == 'LIVE_ACCEPTANCE'
    assert state['from_version'] == '32.4.54'
    assert state['to_version'] == '32.4.55'
    assert state['artifact_sha256'] == artifact_sha

    hold = json.loads((root / 'Inbox/operating_mode/release_validation_hold.json').read_text())
    assert hold['active'] is True
    assert hold['release_version'] == '32.4.55'

    transition = json.loads((root / 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json').read_text())
    assert transition['lifecycle_state'] == 'ACTIVE'
    assert transition['phase'] == 'TRANSITION_PREPARED'
    assert transition['from_release'] == '32.4.54'
    assert transition['to_release'] == '32.4.55'

    processed = root / 'Inbox/processed/EnergieProject_v32.4.55.zip'
    assert processed.is_file()
    assert hashlib.sha256(processed.read_bytes()).hexdigest() == artifact_sha
    assert not list((root / 'Inbox/incoming').glob('*.zip'))
    assert not list((root / 'Inbox/processing').glob('*.zip'))
    assert not (root / 'Inbox/.installer.lock').exists()
    assert (root / 'Inbox/ha_publication_required.json').is_file()
    assert (root / 'Inbox/operating_mode/post_release_maintenance_required.json').is_file()
    backups_before = sorted((root / 'Backups').glob('EnergieProject_pre_*.tar.gz'))
    assert len(backups_before) == 1

    app_inode = (root / 'App').stat().st_ino
    transition_before = transition.copy()
    journal_before = state.copy()
    second = _run_installer(root)
    assert second.returncode == 0, second.stdout + second.stderr
    assert 'Geen release-ZIP in incoming.' in (second.stdout + second.stderr)
    assert (root / 'App').stat().st_ino == app_inode
    assert _state(root) == journal_before
    assert json.loads((root / 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json').read_text()) == transition_before
    assert len(list((root / 'Backups').glob('EnergieProject_pre_*.tar.gz'))) == 1


def test_orphan_processing_requires_canonical_recovery_before_real_installer(tmp_path: Path):
    root, release = _project(tmp_path)
    orphan = root / 'Inbox/processing' / release.name
    release.rename(orphan)
    old = orphan.stat().st_mtime - 120
    os.utime(orphan, (old, old))

    blocked = _run_installer(root)
    assert blocked.returncode != 0
    assert 'processing bevat bestaande release-ZIP' in (blocked.stdout + blocked.stderr)
    assert orphan.is_file()
    assert not (root / 'Inbox/incoming' / orphan.name).exists()
    assert (root / 'App/VERSIE.txt').read_text().strip() == '32.4.54'

    recovered = subprocess.run(
        [os.fspath(Path(os.sys.executable)), os.fspath(RECOVERY), 'reconcile', '--root', os.fspath(root), '--stale-seconds', '30'],
        text=True, capture_output=True, check=False, timeout=10,
    )
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
    assert not orphan.exists()
    assert (root / 'Inbox/incoming' / orphan.name).is_file()

    installed = _run_installer(root)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert (root / 'App/VERSIE.txt').read_text().strip() == '32.4.55'
    assert _state(root)['state'] == 'LIVE_ACCEPTANCE'
    assert len(list((root / 'Inbox/processed').glob('EnergieProject_v32.4.55.zip'))) == 1
    assert not list((root / 'Inbox/processing').glob('*.zip'))


def test_transition_prepared_advances_only_after_real_installer_proves_promotion(tmp_path: Path):
    root, _ = _project(tmp_path)
    installed = _run_installer(root)
    assert installed.returncode == 0, installed.stdout + installed.stderr
    worker = ReleaseTransitionWorker(root, object())
    before = worker.coord.load()
    assert before['phase'] == 'TRANSITION_PREPARED'

    after = worker.run_once()

    assert after['phase'] == 'APP_PROMOTED'
    assert after['revision'] == before['revision'] + 1
    assert after['generation_id'] == before['generation_id']
    assert worker.commands.all() == []


def test_transition_prepared_stays_stable_without_matching_atomic_promotion(tmp_path: Path):
    root, _ = _project(tmp_path)
    worker = ReleaseTransitionWorker(root, object())
    prepared = worker.coord.create_prepared('32.4.54', '32.4.55', previous_base_mode='DEVELOPMENT')
    before_bytes = worker.coord.path.read_bytes()

    for _ in range(20):
        current = worker.run_once()
        assert current['phase'] == 'TRANSITION_PREPARED'
        assert current['revision'] == prepared['revision']

    assert worker.coord.path.read_bytes() == before_bytes
    assert worker.commands.all() == []


def test_real_installer_to_complete_transition_is_unique_and_stable_for_100_cycles(monkeypatch, tmp_path: Path):
    from types import SimpleNamespace
    import operating_mode_runtime as mode_runtime
    from operating_modes import Mode, ModeState, save_mode_state, load_mode_state

    root, _ = _project(tmp_path)
    installed = _run_installer(root)
    assert installed.returncode == 0, installed.stdout + installed.stderr

    generation = 'practical-final-generation'
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    _payload_status = {
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
    (runtime/'status/current.json').write_text(json.dumps(_payload_status), encoding='utf-8')
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

    app = SimpleNamespace(APP_VERSION='32.4.55')
    worker = ReleaseTransitionWorker(root, app)
    seen = []
    for _ in range(20):
        state = worker.run_once()
        seen.append(state['phase'])
        if state.get('lifecycle_state') == 'COMPLETE':
            break

    final = worker.coord.load()
    assert final['lifecycle_state'] == 'COMPLETE', seen
    assert final['phase'] == 'COMPLETE'
    assert final['phase_status'] == 'GREEN'
    assert final['current_ticket'] is None
    assert final['blocker'] == ''
    assert 'APP_PROMOTED' in seen
    assert 'ATOMIC_ACCEPTANCE_COMMITTED' in seen
    assert 'PROJECT_CR' in seen
    assert 'NAS_CR' in seen
    assert 'CLEARUP' in seen
    assert 'HYGIENE' in seen
    assert 'LIVE_PROVEN' in seen
    assert 'RESTORE_DEVELOPMENT' in seen
    assert json.loads((root/'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
    hold = json.loads((root/'Inbox/operating_mode/release_validation_hold.json').read_text())
    assert hold['active'] is False and hold['validation_status'] == 'ok'
    mode = load_mode_state(root)
    assert mode.base_mode is Mode.DEVELOPMENT
    assert mode.effective_mode is Mode.DEVELOPMENT
    assert worker.commands.all() == []

    before_transition = worker.coord.path.read_bytes()
    before_mode = (root/'Inbox/operating_mode/operating_mode_state.json').read_bytes()
    before_commands = (runtime/'commands/queue.json').read_bytes() if (runtime/'commands/queue.json').is_file() else b''
    final_revision = final['revision']
    for _ in range(100):
        stable = worker.run_once()
        assert stable['lifecycle_state'] == 'COMPLETE'
        assert stable['revision'] == final_revision
    assert worker.coord.path.read_bytes() == before_transition
    assert (root/'Inbox/operating_mode/operating_mode_state.json').read_bytes() == before_mode
    after_commands = (runtime/'commands/queue.json').read_bytes() if (runtime/'commands/queue.json').is_file() else b''
    assert after_commands == before_commands
