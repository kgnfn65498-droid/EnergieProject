import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(APP))

from runtime_sources import RuntimeCollector
from release_health import release_health_checks


def _touch_heartbeat_function():
    text = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    return 'touch_heartbeat(){' + text.split('touch_heartbeat(){', 1)[1].split('\n}', 1)[0] + '\n}'


def _run_two_heartbeat_writes(tmp_path: Path):
    heartbeat = tmp_path / 'writer/Inbox/.watcher.heartbeat'
    heartbeat_v2 = tmp_path / 'writer/Inbox/watcher_heartbeat.v2'
    observer = tmp_path / 'observer/Inbox/.watcher.heartbeat'
    observer.parent.mkdir(parents=True)
    functions = _touch_heartbeat_function()
    script = f'''
set -eu
HEARTBEAT="{heartbeat}"
HEARTBEAT_V2="{heartbeat_v2}"
mkdir -p "$(dirname "$HEARTBEAT")"
{functions}
touch_heartbeat
ln "$HEARTBEAT" "{observer}"
inode1="$(stat -c %i "$HEARTBEAT")"
first="$(cat "$HEARTBEAT")"
sleep 1.1
touch_heartbeat
inode2="$(stat -c %i "$HEARTBEAT")"
writer="$(cat "$HEARTBEAT")"
observer="$(cat "{observer}")"
printf 'inode1=%s\\ninode2=%s\\nfirst=%s\\nwriter=%s\\nobserver=%s\\n' \
  "$inode1" "$inode2" "$first" "$writer" "$observer"
'''
    proc = subprocess.run(['sh', '-c', script], text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    values = {}
    for line in proc.stdout.splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            values[key] = value
    return values, heartbeat, observer


def test_heartbeat_update_preserves_inode_for_cross_mount_observers(tmp_path):
    values, heartbeat, observer = _run_two_heartbeat_writes(tmp_path)

    assert values['writer'] != values['first']
    assert values['inode2'] == values['inode1']
    assert values['observer'] == values['writer']
    assert os.stat(heartbeat).st_ino == os.stat(observer).st_ino


def test_cross_mount_cached_inode_sees_fresh_payload_and_release_health_green(tmp_path):
    values, _, observer = _run_two_heartbeat_writes(tmp_path)
    pm_project = tmp_path / 'observer'

    (pm_project / 'App').mkdir(parents=True)
    (pm_project / 'App/VERSIE.txt').write_text('32.4.20\n', encoding='utf-8')
    now = datetime.now(timezone.utc)
    runtime = RuntimeCollector(
        pm_project,
        running_release_version='32.4.20',
    ).collect(now=now)
    watcher = runtime['release_chain']['watcher']
    checks = {item['name']: item for item in release_health_checks(runtime)}

    assert watcher['heartbeat_source'] == 'content_epoch'
    assert watcher['active'] is True
    assert watcher['heartbeat_age_seconds'] < 60
    assert checks['release_watcher']['status'] == 'GREEN'
    assert observer.read_text(encoding='utf-8').strip() == values['writer']


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(__import__('json').dumps(payload), encoding='utf-8')


def test_cross_mount_fresh_heartbeat_allows_exact_live_acceptance_gate(tmp_path):
    import operating_mode_runtime as mode_runtime

    values, _, _ = _run_two_heartbeat_writes(tmp_path)
    project = tmp_path / 'observer'
    version = '32.4.20'
    (project / 'App').mkdir(parents=True, exist_ok=True)
    (project / 'App/VERSIE.txt').write_text(version + '\n', encoding='utf-8')

    now = datetime.now(timezone.utc)
    runtime = RuntimeCollector(project, running_release_version=version).collect(now=now)
    release_checks = {item['name']: item for item in release_health_checks(runtime)}
    assert release_checks['release_watcher']['status'] == 'GREEN'

    pm_root = project / 'Inbox/projectmanager_v2/RuntimeV2'
    status_path = pm_root / 'status/current.json'
    audit_path = pm_root / 'self_audit/current.json'
    _write_json(status_path, {
        'release': {'version': version},
        'health': {
            'status': 'RED',
            'checks': [
                {
                    'name': 'current_quarter_hour_snapshot',
                    'status': 'RED',
                    'reason': 'missing_invalid_or_stale',
                    'details': {},
                },
                {
                    'name': 'release_validation_hold',
                    'status': 'ORANGE',
                    'reason': 'missing_active_or_unvalidated',
                    'details': {'active': True, 'validation_status': 'blocked'},
                },
                release_checks['release_watcher'],
                {
                    'name': 'release_atomic_state',
                    'status': 'RED',
                    'reason': 'live_acceptance_blocks_release_ingress',
                    'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE'}},
                },
            ],
        },
    })
    _write_json(audit_path, {
        'status': 'GREEN',
        'invalid': [],
        'warnings': [],
        'missing': [],
    })
    st = status_path.stat()
    os.utime(audit_path, (st.st_atime + 1, st.st_mtime + 1))
    _write_json(project / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE',
        'from_version': '32.4.19',
        'to_version': version,
    })

    result = mode_runtime._projectmanager_self_audit_check(project)
    assert result['ok'] is True, result
    assert values['observer'] == values['writer']


def test_runtime_prefers_fresh_v2_heartbeat_over_stale_legacy_path(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.20\n', encoding='utf-8')
    inbox = project / 'Inbox'
    inbox.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    (inbox / '.watcher.heartbeat').write_text(
        str(int(now.timestamp()) - 1200),
        encoding='utf-8',
    )
    (inbox / 'watcher_heartbeat.v2').write_text(
        str(int(now.timestamp())),
        encoding='utf-8',
    )

    runtime = RuntimeCollector(project, running_release_version='32.4.20').collect(now=now)
    watcher = runtime['release_chain']['watcher']

    assert watcher['active'] is True
    assert watcher['heartbeat_source'] == 'content_epoch_v2'
    assert watcher['heartbeat_path'].endswith('/watcher_heartbeat.v2')
    assert watcher['heartbeat_age_seconds'] <= 1.0


def test_stale_parseable_v2_is_fail_closed_even_when_legacy_is_fresh(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.20\n', encoding='utf-8')
    inbox = project / 'Inbox'
    inbox.mkdir(parents=True)
    now = datetime.now(timezone.utc)
    (inbox / '.watcher.heartbeat').write_text(
        str(int(now.timestamp())),
        encoding='utf-8',
    )
    (inbox / 'watcher_heartbeat.v2').write_text(
        str(int(now.timestamp()) - 1200),
        encoding='utf-8',
    )

    runtime = RuntimeCollector(project, running_release_version='32.4.20').collect(now=now)
    watcher = runtime['release_chain']['watcher']

    assert watcher['active'] is False
    assert watcher['heartbeat_source'] == 'content_epoch_v2'
    assert watcher['heartbeat_age_seconds'] >= 1199


def test_touch_heartbeat_creates_v2_marker_and_keeps_its_inode_stable(tmp_path):
    heartbeat = tmp_path / 'Inbox/.watcher.heartbeat'
    heartbeat_v2 = tmp_path / 'Inbox/watcher_heartbeat.v2'
    observer = tmp_path / 'observer.v2'
    functions = _touch_heartbeat_function()
    script = f'''
set -eu
HEARTBEAT="{heartbeat}"
HEARTBEAT_V2="{heartbeat_v2}"
mkdir -p "$(dirname "$HEARTBEAT")"
{functions}
touch_heartbeat
test -f "$HEARTBEAT_V2"
ln "$HEARTBEAT_V2" "{observer}"
inode1="$(stat -c %i "$HEARTBEAT_V2")"
first="$(cat "$HEARTBEAT_V2")"
sleep 1.1
touch_heartbeat
inode2="$(stat -c %i "$HEARTBEAT_V2")"
writer="$(cat "$HEARTBEAT_V2")"
observer="$(cat "{observer}")"
printf 'inode1=%s\\ninode2=%s\\nfirst=%s\\nwriter=%s\\nobserver=%s\\n' \
  "$inode1" "$inode2" "$first" "$writer" "$observer"
'''
    proc = subprocess.run(['sh', '-c', script], text=True, capture_output=True, check=False)
    assert proc.returncode == 0, proc.stderr
    values = dict(line.split('=', 1) for line in proc.stdout.splitlines() if '=' in line)
    assert values['writer'] != values['first']
    assert values['inode2'] == values['inode1']
    assert values['observer'] == values['writer']
