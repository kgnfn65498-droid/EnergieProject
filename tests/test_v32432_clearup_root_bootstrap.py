from pathlib import Path
import importlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
HELPER = ROOT / 'tools' / 'prepare_clearup_root.sh'
WATCHER = ROOT / 'tools' / 'release_watcher.sh'


def run_helper(project_root: Path):
    return subprocess.run(
        ['sh', str(HELPER), str(project_root)],
        text=True,
        capture_output=True,
        check=False,
    )


def seed_accepted_clearup_gate(root: Path):
    approval = root / 'Data/03_Systeem/Projectmanager/State/32_4_25_scope_cleanup_and_history_repair_20260909.md'
    approval.parent.mkdir(parents=True)
    approval.write_text('Status: DEVELOPMENT SCOPE APPROVED BY USER\nCLEARUP\n', encoding='utf-8')
    inbox = root / 'Inbox'
    (inbox / 'operating_mode').mkdir(parents=True)
    (inbox / 'atomic_app_swap_state.json').write_text(
        json.dumps({'state': 'ACCEPTED', 'to_version': '32.4.32'}), encoding='utf-8'
    )
    (inbox / 'operating_mode/release_validation_hold.json').write_text(
        json.dumps({'active': False, 'validation_status': 'ok'}), encoding='utf-8'
    )


def test_clearup_root_bootstrap_creates_exact_project_root_quarantine(tmp_path: Path):
    result = run_helper(tmp_path)
    assert result.returncode == 0, result.stderr
    clearup = tmp_path / 'CLEARUP'
    assert clearup.is_dir()
    assert not clearup.is_symlink()
    assert (clearup.stat().st_mode & 0o777) == 0o777
    assert not list(clearup.glob('.clearup-write-probe.*'))


def test_clearup_root_bootstrap_rejects_symlink_without_touching_target(tmp_path: Path):
    outside = tmp_path / 'outside'
    outside.mkdir(mode=0o755)
    (tmp_path / 'CLEARUP').symlink_to(outside, target_is_directory=True)
    before_mode = outside.stat().st_mode & 0o777
    result = run_helper(tmp_path)
    assert result.returncode != 0
    assert (tmp_path / 'CLEARUP').is_symlink()
    assert (outside.stat().st_mode & 0o777) == before_mode


def test_new_watcher_prepares_clearup_root_without_host_python_dependency():
    source = WATCHER.read_text(encoding='utf-8')
    assert 'CLEARUP_PREPARE="$PROJECT/tools/prepare_clearup_root.sh"' in source
    assert 'sh "$CLEARUP_PREPARE" "$ROOT"' in source
    invocation = source.index('sh "$CLEARUP_PREPARE" "$ROOT"')
    assert invocation < source.index('Release watcher gestart')
    surrounding = source[max(0, invocation - 300):invocation + 300]
    assert 'python3' not in surrounding
    assert 'Inbox/CLEARUP' not in source


def test_clearup_gate_blocks_missing_destination_before_expensive_work(tmp_path: Path):
    seed_accepted_clearup_gate(tmp_path)
    sys.path.insert(0, str(APP))
    try:
        module = importlib.import_module('project_clearup_auto')
        gate = module.clearup_auto_gate(tmp_path, app_version='32.4.32')
    finally:
        sys.path.remove(str(APP))
    assert gate['ready'] is False
    assert 'clearup_root_not_ready' in gate['blockers']
    assert gate['clearup_destination']['reason'] == 'clearup_root_missing'
    assert gate['crash_recovery']['reason'] == 'deferred_until_clearup_root_ready'


def test_32432_release_identity_is_consistent():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.47'
    main = (ROOT / 'slimmemeterportal_import/rootfs/app/main.py').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.4.47"' in main
