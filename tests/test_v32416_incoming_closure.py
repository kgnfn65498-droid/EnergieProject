import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(APP))
sys.path.insert(0, str(PM))

from operating_mode_runtime import _projectmanager_self_audit_check


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _runtime(root: Path, checks: list[dict], health_status='RED'):
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    _write_json(runtime / 'status/current.json', {
        'schema': 'energie_projectmanager_status_v2',
        'release': {'version': '32.4.16'},
        'health': {'status': health_status, 'checks': checks},
    })
    _write_json(runtime / 'self_audit/current.json', {'status': 'GREEN', 'invalid': [], 'warnings': []})
    version = root / 'App/VERSIE.txt'
    version.parent.mkdir(parents=True, exist_ok=True)
    version.write_text('32.4.16\n', encoding='utf-8')
    stat = (runtime / 'status/current.json').stat()
    os.utime(runtime / 'self_audit/current.json', (stat.st_atime + 1, stat.st_mtime + 1))
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.15', 'to_version': '32.4.16',
        'artifact_sha256': 'synthetic',
    })


def _expected_waiting_next_checks(count=1):
    return [
        {'name': 'release_incoming', 'status': 'ORANGE' if count == 1 else 'RED',
         'reason': 'release_waiting_incoming' if count == 1 else 'multiple_releases_block_ingress',
         'details': {'count': count}},
        {'name': 'release_atomic_state', 'status': 'RED',
         'reason': 'live_acceptance_blocks_release_ingress',
         'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE', 'age_seconds': 2784}}},
    ]


def test_one_waiting_next_release_does_not_block_current_atomic_acceptance(tmp_path):
    root = tmp_path / 'energy'
    _runtime(root, _expected_waiting_next_checks(1))
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is True, result


def test_multiple_waiting_releases_remain_fail_closed(tmp_path):
    root = tmp_path / 'energy'
    _runtime(root, _expected_waiting_next_checks(2))
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is False


def test_waiting_release_exception_never_hides_unrelated_health_problem(tmp_path):
    root = tmp_path / 'energy'
    checks = _expected_waiting_next_checks(1) + [
        {'name': 'release_watcher', 'status': 'RED', 'reason': 'watcher_inactive_or_stale'}
    ]
    _runtime(root, checks)
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is False


def test_watcher_blocks_live_acceptance_but_allows_immediately_after_accepted(tmp_path):
    watcher = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    function = 'atomic_swap_allows_release_ingress(){' + watcher.split('atomic_swap_allows_release_ingress(){', 1)[1].split('\n}', 1)[0] + '\n}'
    inbox = tmp_path / 'Inbox'
    inbox.mkdir()
    journal = inbox / 'atomic_app_swap_state.json'
    lock = inbox / '.atomic_app_swap.lock'

    def allowed(state: str) -> bool:
        journal.write_text(json.dumps({'state': state}), encoding='utf-8')
        script = f'''{function}\nATOMIC_SWAP_LOCK="{lock}"\nATOMIC_SWAP_JOURNAL="{journal}"\natomic_swap_allows_release_ingress'''
        return subprocess.run(['sh', '-c', script], check=False).returncode == 0

    assert allowed('LIVE_ACCEPTANCE') is False
    assert allowed('ACCEPTED') is True
