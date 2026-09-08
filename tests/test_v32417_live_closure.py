import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))

from release_health import release_health_checks


def _by_name(checks):
    return {item['name']: item for item in checks}


def _runtime(*, release='32.4.17', publisher_status='error', publisher_version='32.4.10', contract_pending=False, contract_version=None):
    return {
        'release': {
            'version': release,
            'ha_runtime_version': release,
            'nas_version': release,
            'rollback_version': '32.4.16',
            'rollback_versions': ['32.4.16'],
        },
        'release_chain': {
            'watcher': {'active': True, 'heartbeat_age_seconds': 1},
            'incoming': {'count': 0},
            'processing': {'stuck_count': 0},
            'installer_lock': {'active': False},
            'atomic_swap': {'exists': True, 'state': 'ACCEPTED', 'age_seconds': 1},
            'publisher': {
                'status': publisher_status,
                'version': publisher_version,
                'message': 'remote branch not found',
            },
            'github_publication': {
                'status': publisher_status,
                'version': contract_version or publisher_version,
                'contract_pending': contract_pending,
                'contract_version': contract_version,
            },
        },
    }


def test_old_publisher_error_cannot_poison_current_release_health():
    checks = _by_name(release_health_checks(_runtime()))
    assert checks['release_publisher']['status'] == 'GREEN', checks['release_publisher']
    assert checks['release_publisher']['reason'] == 'stale_previous_publisher_state_ignored'
    assert checks['release_github_publication']['status'] == 'GREEN', checks['release_github_publication']
    assert checks['release_github_publication']['reason'] == 'stale_previous_publication_state_ignored'


def test_current_release_publisher_error_remains_fail_closed():
    checks = _by_name(release_health_checks(_runtime(publisher_version='32.4.17')))
    assert checks['release_publisher']['status'] == 'RED'
    assert checks['release_github_publication']['status'] == 'RED'


def test_pending_current_publication_remains_non_green_even_if_old_publisher_state_exists():
    checks = _by_name(release_health_checks(_runtime(contract_pending=True, contract_version='32.4.17')))
    assert checks['release_github_publication']['status'] == 'ORANGE'
    assert checks['release_github_publication']['reason'] == 'github_publication_pending'


def test_watcher_has_bounded_external_gate_execution():
    text = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    assert 'run_bounded(){' in text
    mode = text.split('mode_allows(){', 1)[1].split('\n}', 1)[0]
    assert 'run_bounded "$MODE_GATE_TIMEOUT" python3 "$MODE_GATE"' in mode


def test_watcher_bounded_runner_actually_terminates_hung_command(tmp_path):
    text = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    if 'run_bounded(){' not in text:
        raise AssertionError('run_bounded missing')
    fn = 'run_bounded(){' + text.split('run_bounded(){', 1)[1].split('\n}', 1)[0] + '\n}'
    started = time.monotonic()
    proc = subprocess.run(
        ['sh', '-c', fn + '\nrun_bounded 1 sleep 10'],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=4,
    )
    elapsed = time.monotonic() - started
    assert proc.returncode != 0
    assert elapsed < 3.0, (elapsed, proc.stdout, proc.stderr)


def _write_json(path: Path, payload: dict):
    import json
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _pm_acceptance_result(tmp_path, checks):
    import os
    sys.path.insert(0, str(APP))
    from operating_mode_runtime import _projectmanager_self_audit_check
    root = tmp_path / 'energy'
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    _write_json(runtime / 'status/current.json', {
        'release': {'version': '32.4.17'},
        'health': {'status': 'RED', 'checks': checks},
    })
    _write_json(runtime / 'self_audit/current.json', {'status': 'GREEN', 'invalid': [], 'warnings': []})
    version = root / 'App/VERSIE.txt'
    version.parent.mkdir(parents=True, exist_ok=True)
    version.write_text('32.4.17\n', encoding='utf-8')
    stat = (runtime / 'status/current.json').stat()
    os.utime(runtime / 'self_audit/current.json', (stat.st_atime + 1, stat.st_mtime + 1))
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.16', 'to_version': '32.4.17'
    })
    return _projectmanager_self_audit_check(root)


def test_current_release_hold_orange_is_allowed_only_during_own_live_acceptance(tmp_path):
    checks = [
        {'name': 'release_validation_hold', 'status': 'ORANGE', 'reason': 'missing_active_or_unvalidated',
         'details': {'active': True, 'validation_status': 'blocked'}},
        {'name': 'release_atomic_state', 'status': 'RED', 'reason': 'live_acceptance_blocks_release_ingress',
         'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE'}}},
    ]
    result = _pm_acceptance_result(tmp_path, checks)
    assert result['ok'] is True, result


def test_current_release_hold_plus_one_waiting_next_release_can_close_atomically(tmp_path):
    checks = [
        {'name': 'release_validation_hold', 'status': 'ORANGE', 'reason': 'missing_active_or_unvalidated',
         'details': {'active': True, 'validation_status': 'blocked'}},
        {'name': 'release_incoming', 'status': 'ORANGE', 'reason': 'release_waiting_incoming',
         'details': {'count': 1}},
        {'name': 'release_atomic_state', 'status': 'RED', 'reason': 'live_acceptance_blocks_release_ingress',
         'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE'}}},
    ]
    result = _pm_acceptance_result(tmp_path, checks)
    assert result['ok'] is True, result


def test_release_hold_exception_never_hides_unrelated_red(tmp_path):
    checks = [
        {'name': 'release_validation_hold', 'status': 'ORANGE', 'reason': 'missing_active_or_unvalidated',
         'details': {'active': True, 'validation_status': 'blocked'}},
        {'name': 'release_atomic_state', 'status': 'RED', 'reason': 'live_acceptance_blocks_release_ingress',
         'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE'}}},
        {'name': 'release_watcher', 'status': 'RED', 'reason': 'watcher_inactive_or_stale', 'details': {}},
    ]
    result = _pm_acceptance_result(tmp_path, checks)
    assert result['ok'] is False
