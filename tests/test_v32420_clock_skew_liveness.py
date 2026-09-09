import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(APP))
sys.path.insert(0, str(PM))

from runtime_sources import RuntimeCollector
from release_health import release_health_checks


def _collector(project: Path, sleep_fn):
    return RuntimeCollector(
        project,
        running_release_version='32.4.20',
        watcher_probe_seconds=0.01,
        watcher_sleep_fn=sleep_fn,
    )


def test_clock_skew_does_not_mark_live_watcher_dead_when_payload_pulses(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.20\n', encoding='utf-8')
    hb = project / 'Inbox/.watcher.heartbeat'
    hb.parent.mkdir(parents=True)

    # Simulate QNAP clock ~17 minutes behind the HA/PM clock.
    pm_now = datetime.now(timezone.utc)
    qnap_epoch = int(pm_now.timestamp()) - 1015
    hb.write_text(str(qnap_epoch), encoding='utf-8')
    os.utime(hb, (qnap_epoch, qnap_epoch))

    def pulse(_seconds):
        hb.write_text(str(qnap_epoch + 5), encoding='utf-8')
        os.utime(hb, (qnap_epoch + 5, qnap_epoch + 5))

    runtime = _collector(project, pulse).collect(now=pm_now)
    watcher = runtime['release_chain']['watcher']
    check = {x['name']: x for x in release_health_checks(runtime)}['release_watcher']

    assert watcher['active'] is True
    assert watcher['heartbeat_source'] == 'content_pulse_probe'
    assert watcher['heartbeat_clock_skew_detected'] is True
    assert check['status'] == 'GREEN'


def test_clock_skew_probe_fails_closed_when_heartbeat_does_not_change(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.20\n', encoding='utf-8')
    hb = project / 'Inbox/.watcher.heartbeat'
    hb.parent.mkdir(parents=True)

    pm_now = datetime.now(timezone.utc)
    qnap_epoch = int(pm_now.timestamp()) - 1015
    hb.write_text(str(qnap_epoch), encoding='utf-8')
    os.utime(hb, (qnap_epoch, qnap_epoch))

    runtime = _collector(project, lambda _seconds: None).collect(now=pm_now)
    watcher = runtime['release_chain']['watcher']
    check = {x['name']: x for x in release_health_checks(runtime)}['release_watcher']

    assert watcher['active'] is False
    assert watcher['heartbeat_source'] == 'content_epoch'
    assert watcher['heartbeat_probe_result'] == 'no_pulse'
    assert check['status'] == 'RED'


def test_future_heartbeat_from_opposite_clock_skew_uses_same_pulse_probe(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.20\n', encoding='utf-8')
    hb = project / 'Inbox/.watcher.heartbeat'
    hb.parent.mkdir(parents=True)

    pm_now = datetime.now(timezone.utc)
    remote_epoch = int(pm_now.timestamp()) + 600
    hb.write_text(str(remote_epoch), encoding='utf-8')

    def pulse(_seconds):
        hb.write_text(str(remote_epoch + 5), encoding='utf-8')

    runtime = _collector(project, pulse).collect(now=pm_now)
    watcher = runtime['release_chain']['watcher']
    assert watcher['active'] is True
    assert watcher['heartbeat_source'] == 'content_pulse_probe'


def test_live_acceptance_can_close_with_clock_skew_proven_watcher(tmp_path):
    import operating_mode_runtime as mode_runtime

    project = tmp_path / 'energy'
    version = '32.4.20'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text(version + '\n', encoding='utf-8')
    hb = project / 'Inbox/.watcher.heartbeat'
    hb.parent.mkdir(parents=True)

    pm_now = datetime.now(timezone.utc)
    qnap_epoch = int(pm_now.timestamp()) - 1015
    hb.write_text(str(qnap_epoch), encoding='utf-8')

    def pulse(_seconds):
        hb.write_text(str(qnap_epoch + 5), encoding='utf-8')

    runtime = _collector(project, pulse).collect(now=pm_now)
    watcher_check = {x['name']: x for x in release_health_checks(runtime)}['release_watcher']
    assert watcher_check['status'] == 'GREEN'

    runtime_dir = project / 'Inbox/projectmanager_v2/RuntimeV2'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    status_path = runtime_dir / 'status/current.json'
    audit_path = runtime_dir / 'self_audit/current.json'
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    checks = [
        {'name': 'release_validation_hold', 'status': 'ORANGE', 'reason': 'missing_active_or_unvalidated',
         'details': {'active': True, 'validation_status': 'blocked'}},
        watcher_check,
        {'name': 'release_atomic_state', 'status': 'RED', 'reason': 'live_acceptance_blocks_release_ingress',
         'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE'}}},
    ]
    status_path.write_text(json.dumps({'release': {'version': version}, 'health': {'status': 'RED', 'checks': checks}}), encoding='utf-8')
    audit_path.write_text(json.dumps({'status': 'GREEN', 'invalid': [], 'warnings': [], 'missing': []}), encoding='utf-8')
    st = status_path.stat()
    os.utime(audit_path, (st.st_atime + 1, st.st_mtime + 1))
    (project / 'Inbox/atomic_app_swap_state.json').write_text(json.dumps({
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.19', 'to_version': version,
    }), encoding='utf-8')

    result = mode_runtime._projectmanager_self_audit_check(project)
    assert result['ok'] is True, result
