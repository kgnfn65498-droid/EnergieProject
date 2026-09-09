import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(APP))
sys.path.insert(0, str(PM))

from runtime_sources import RuntimeCollector
from release_health import release_health_checks


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_watcher_health_uses_heartbeat_payload_not_stale_file_mtime(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.19\n', encoding='utf-8')
    heartbeat = project / 'Inbox/.watcher.heartbeat'
    heartbeat.parent.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    heartbeat.write_text(str(int(now.timestamp())), encoding='utf-8')
    old = now.timestamp() - 1200
    os.utime(heartbeat, (old, old))

    runtime = RuntimeCollector(project, running_release_version='32.4.19').collect(now=now)
    watcher = runtime['release_chain']['watcher']
    checks = {item['name']: item for item in release_health_checks(runtime)}

    assert watcher['active'] is True
    assert watcher['heartbeat_source'] == 'content_epoch'
    assert watcher['heartbeat_age_seconds'] <= 1.0
    assert checks['release_watcher']['status'] == 'GREEN'


def test_stale_heartbeat_payload_stays_red_even_if_file_mtime_is_fresh(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.19\n', encoding='utf-8')
    heartbeat = project / 'Inbox/.watcher.heartbeat'
    heartbeat.parent.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    heartbeat.write_text(str(int(now.timestamp()) - 1200), encoding='utf-8')
    os.utime(heartbeat, (now.timestamp(), now.timestamp()))

    runtime = RuntimeCollector(project, running_release_version='32.4.19').collect(now=now)
    watcher = runtime['release_chain']['watcher']
    checks = {item['name']: item for item in release_health_checks(runtime)}

    assert watcher['active'] is False
    assert watcher['heartbeat_source'] == 'content_epoch'
    assert watcher['heartbeat_age_seconds'] >= 1199
    assert checks['release_watcher']['status'] == 'RED'


def _watcher_functions_text():
    text = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    run_bounded = 'run_bounded(){' + text.split('run_bounded(){', 1)[1].split('\n}', 1)[0] + '\n}'
    mode_allows = 'mode_allows(){' + text.split('mode_allows(){', 1)[1].split('\n}', 1)[0] + '\n}'
    return run_bounded + '\n' + mode_allows


def test_mode_gate_denial_rc3_is_not_misreported_as_timeout(tmp_path):
    gate = tmp_path / 'gate.py'
    gate.write_text('raise SystemExit(3)\n', encoding='utf-8')
    functions = _watcher_functions_text()
    script = f'''\nBOUNDED_TERM_GRACE_SECONDS=0\nMODE_GATE_TIMEOUT=2\nMODE_GATE={gate!s}\nROOT={tmp_path!s}\nlog(){{ printf "%s\\n" "$*"; }}\n{functions}\nmode_allows release_ingress\nrc=$?\nprintf "FINAL_RC=%s\\n" "$rc"\nexit 0\n'''
    proc = subprocess.run(['sh', '-c', script], text=True, capture_output=True, check=False)
    assert 'timeout/fout' not in proc.stdout
    assert 'FINAL_RC=1' in proc.stdout


def test_mode_gate_real_error_preserves_nonzero_return_code_in_log(tmp_path):
    gate = tmp_path / 'gate.py'
    gate.write_text('raise SystemExit(7)\n', encoding='utf-8')
    functions = _watcher_functions_text()
    script = f'''\nBOUNDED_TERM_GRACE_SECONDS=0\nMODE_GATE_TIMEOUT=2\nMODE_GATE={gate!s}\nROOT={tmp_path!s}\nlog(){{ printf "%s\\n" "$*"; }}\n{functions}\nmode_allows release_ingress\nrc=$?\nprintf "FINAL_RC=%s\\n" "$rc"\nexit 0\n'''
    proc = subprocess.run(['sh', '-c', script], text=True, capture_output=True, check=False)
    assert 'rc=7' in proc.stdout
    assert 'rc=0' not in proc.stdout
    assert 'FINAL_RC=1' in proc.stdout


def _write_pm_gate_files(root: Path, version: str, checks: list[dict]):
    import operating_mode_runtime as mode_runtime
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    _write_json(runtime / 'status/current.json', {
        'release': {'version': version},
        'health': {'status': 'RED', 'checks': checks},
    })
    _write_json(runtime / 'self_audit/current.json', {
        'status': 'GREEN', 'invalid': [], 'warnings': [], 'missing': [],
    })
    version_path = root / 'App/VERSIE.txt'
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text(version + '\n', encoding='utf-8')
    status_stat = (runtime / 'status/current.json').stat()
    os.utime(runtime / 'self_audit/current.json', (status_stat.st_atime + 1, status_stat.st_mtime + 1))
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.18', 'to_version': version,
    })
    return mode_runtime._projectmanager_self_audit_check(root)


def test_exact_live_closure_scenario_ignores_stale_mtime_when_heartbeat_payload_is_fresh(tmp_path):
    version = '32.4.19'
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text(version + '\n', encoding='utf-8')
    heartbeat = project / 'Inbox/.watcher.heartbeat'
    heartbeat.parent.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    heartbeat.write_text(str(int(now.timestamp())), encoding='utf-8')
    old = now.timestamp() - 1200
    os.utime(heartbeat, (old, old))

    runtime = RuntimeCollector(project, running_release_version=version).collect(now=now)
    watcher_check = {item['name']: item for item in release_health_checks(runtime)}['release_watcher']
    assert watcher_check['status'] == 'GREEN'

    checks = [
        {'name': 'current_quarter_hour_snapshot', 'status': 'RED', 'reason': 'missing_invalid_or_stale', 'details': {}},
        {'name': 'release_validation_hold', 'status': 'ORANGE', 'reason': 'missing_active_or_unvalidated',
         'details': {'active': True, 'validation_status': 'blocked'}},
        watcher_check,
        {'name': 'release_atomic_state', 'status': 'RED', 'reason': 'live_acceptance_blocks_release_ingress',
         'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE'}}},
    ]
    result = _write_pm_gate_files(project, version, checks)
    assert result['ok'] is True, result
