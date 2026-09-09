import json
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(APP))
sys.path.insert(0, str(PM))

import operating_mode_runtime as mode_runtime
import operating_mode_auto_release as auto_release
from release_validation_hold import (
    activate_release_hold,
    load_release_hold,
    record_hold_validation,
    release_hold,
)
from runtime_sources import RuntimeCollector
from release_health import release_health_checks


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _validated_hold(root: Path, version: str, *, active=True):
    activate_release_hold(root, version, 'release_install')
    record_hold_validation(
        root,
        version,
        {'all': {'ok': True, 'detail': 'green'}},
        'ok',
    )
    if not active:
        release_hold(root, version, issued_by='test')
    return load_release_hold(root, version)


def _journal(root: Path, version: str, state='LIVE_ACCEPTANCE', source='32.4.17'):
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': state,
        'from_version': source,
        'to_version': version,
    })


def test_restart_recovers_inactive_validated_hold_plus_live_acceptance(monkeypatch, tmp_path):
    version = '32.4.18'
    _validated_hold(tmp_path, version, active=False)
    _journal(tmp_path, version)
    calls = []

    def accept(root, expected):
        calls.append((Path(root), expected))
        payload = json.loads((Path(root) / 'Inbox/atomic_app_swap_state.json').read_text())
        payload['state'] = 'ACCEPTED'
        _write_json(Path(root) / 'Inbox/atomic_app_swap_state.json', payload)
        return {'status': 'accepted', 'state': 'ACCEPTED', 'version': expected}

    monkeypatch.setattr(mode_runtime, 'finalize_validated_atomic_release', accept)
    def validate(app, root, expected):
        record_hold_validation(Path(root), expected, {'all': {'ok': True}}, 'ok')
        return {'status': 'ok', 'version': expected, 'checks': {'all': {'ok': True}}, 'reconcile_status': 'ok', 'drift': []}

    monkeypatch.setattr(mode_runtime, 'validate_release_hold', validate)

    result = mode_runtime.attempt_release_hold(object(), tmp_path, version, issued_by='projectmanager_auto')

    assert result['status'] == 'released'
    assert calls == [(tmp_path, version)]
    assert json.loads((tmp_path / 'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
    assert load_release_hold(tmp_path, version).active is False


def test_inactive_unvalidated_hold_never_auto_accepts_live_acceptance(monkeypatch, tmp_path):
    version = '32.4.18'
    activate_release_hold(tmp_path, version, 'release_install')
    # Simulate an invalid manual/emergency-style inactive marker with no validated provenance.
    state_path = tmp_path / 'Inbox/operating_mode/release_validation_hold.json'
    raw = json.loads(state_path.read_text())
    raw['active'] = False
    raw['validation_status'] = 'required'
    raw['reconcile_status'] = 'required'
    _write_json(state_path, raw)
    _journal(tmp_path, version)

    accepted = []
    monkeypatch.setattr(mode_runtime, 'finalize_validated_atomic_release', lambda *args: accepted.append(args))

    result = mode_runtime.attempt_release_hold(object(), tmp_path, version, issued_by='projectmanager_auto')

    assert result['status'] == 'blocked_atomic_recovery'
    assert accepted == []
    assert json.loads((tmp_path / 'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'LIVE_ACCEPTANCE'


def test_normal_closure_accepts_atomic_before_releasing_hold(monkeypatch, tmp_path):
    version = '32.4.18'
    _validated_hold(tmp_path, version, active=True)
    _journal(tmp_path, version)
    order = []

    monkeypatch.setattr(mode_runtime, 'validate_release_hold', lambda *args, **kwargs: {
        'status': 'ok', 'version': version, 'checks': {}, 'reconcile_status': 'ok', 'drift': []
    })

    def accept(root, expected):
        order.append('atomic')
        payload = json.loads((Path(root) / 'Inbox/atomic_app_swap_state.json').read_text())
        payload['state'] = 'ACCEPTED'
        _write_json(Path(root) / 'Inbox/atomic_app_swap_state.json', payload)
        return {'status': 'accepted', 'state': 'ACCEPTED', 'version': expected}

    real_release = mode_runtime.release_hold

    def release(root, expected, **kwargs):
        order.append('hold')
        return real_release(root, expected, **kwargs)

    monkeypatch.setattr(mode_runtime, 'finalize_validated_atomic_release', accept)
    monkeypatch.setattr(mode_runtime, 'release_hold', release)

    result = mode_runtime.attempt_release_hold(object(), tmp_path, version, issued_by='projectmanager_auto')

    assert result['status'] == 'released'
    assert order == ['atomic', 'hold']
    assert load_release_hold(tmp_path, version).active is False


def test_restart_after_atomic_acceptance_finishes_remaining_active_hold(monkeypatch, tmp_path):
    version = '32.4.18'
    _validated_hold(tmp_path, version, active=True)
    _journal(tmp_path, version, state='ACCEPTED')
    monkeypatch.setattr(mode_runtime, 'validate_release_hold', lambda *args, **kwargs: {
        'status': 'ok', 'version': version, 'checks': {}, 'reconcile_status': 'ok', 'drift': []
    })
    monkeypatch.setattr(mode_runtime, 'finalize_validated_atomic_release', lambda *args: {
        'status': 'already_accepted', 'state': 'ACCEPTED', 'version': version
    })

    result = mode_runtime.attempt_release_hold(object(), tmp_path, version, issued_by='projectmanager_auto')

    assert result['status'] == 'released'
    assert load_release_hold(tmp_path, version).active is False


def test_auto_release_does_not_stop_at_inactive_hold_when_atomic_is_still_live(monkeypatch, tmp_path):
    version = '32.4.18'
    _validated_hold(tmp_path, version, active=False)
    _journal(tmp_path, version)
    seen = []
    monkeypatch.setattr(auto_release, 'attempt_release_hold', lambda *args, **kwargs: seen.append(args) or {'status': 'released'})

    result = auto_release.automatic_release_hold_once(object(), tmp_path, version)

    assert result['status'] == 'released'
    assert seen


def test_runtime_collector_prefers_current_canonical_ha_publication_over_stale_legacy(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.18\n', encoding='utf-8')
    _write_json(project / 'Inbox/github_publisher_state.json', {
        'status': 'error', 'version': '32.4.10', 'message': 'remote branch not found'
    })
    canonical = tmp_path / 'github_publication_state.json'
    _write_json(canonical, {
        'published': True,
        'version': '32.4.18',
        'remote_head': 'abc123',
        'local_head': 'abc123',
        'publication_contract_removed': True,
        'message': 'GitHub-publicatie geslaagd',
    })

    runtime = RuntimeCollector(
        project,
        running_release_version='32.4.18',
        github_publication_state_path=canonical,
    ).collect()
    chain = runtime['release_chain']

    assert chain['publisher']['status'] == 'published'
    assert chain['publisher']['version'] == '32.4.18'
    assert chain['publisher']['source'] == str(canonical)
    assert chain['github_publication']['status'] == 'published'
    checks = {c['name']: c for c in release_health_checks(runtime)}
    assert checks['release_publisher']['status'] == 'GREEN'
    assert checks['release_github_publication']['status'] == 'GREEN'


def test_current_canonical_publication_failure_stays_red(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.18\n', encoding='utf-8')
    canonical = tmp_path / 'github_publication_state.json'
    _write_json(canonical, {'published': False, 'version': '32.4.18', 'message': 'push failed'})

    runtime = RuntimeCollector(
        project,
        running_release_version='32.4.18',
        github_publication_state_path=canonical,
    ).collect()
    checks = {c['name']: c for c in release_health_checks(runtime)}

    assert checks['release_publisher']['status'] == 'RED'
    assert checks['release_github_publication']['status'] == 'RED'


def test_watcher_kills_process_that_ignores_sigterm():
    text = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    assert 'run_bounded(){' in text
    fn = 'run_bounded(){' + text.split('run_bounded(){', 1)[1].split('\n}', 1)[0] + '\n}'
    cmd = (
        fn
        + "\nrun_bounded 1 python3 -c 'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)'"
    )
    started = time.monotonic()
    proc = subprocess.run(
        ['sh', '-c', cmd],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
    )
    elapsed = time.monotonic() - started

    assert proc.returncode != 0
    assert elapsed < 4.0, (elapsed, proc.stdout, proc.stderr)
    assert 'kill -KILL' in fn


def test_two_consecutive_release_restart_matrix_contract_is_present():
    source = (ROOT / 'slimmemeterportal_import/rootfs/app/operating_mode_runtime.py').read_text(encoding='utf-8')
    auto = (ROOT / 'slimmemeterportal_import/rootfs/app/operating_mode_auto_release.py').read_text(encoding='utf-8')
    assert 'blocked_atomic_recovery' in source
    assert 'finalize_validated_atomic_release' in source
    assert 'already_released' in auto


def test_inactive_validated_live_acceptance_rearms_hold_before_blocked_revalidation(monkeypatch, tmp_path):
    version = '32.4.18'
    _validated_hold(tmp_path, version, active=False)
    _journal(tmp_path, version)
    monkeypatch.setattr(mode_runtime, 'validate_release_hold', lambda *args, **kwargs: {
        'status': 'blocked', 'version': version, 'checks': {'pm': {'ok': False}},
        'reconcile_status': 'blocked', 'drift': ['pm'],
    })

    result = mode_runtime.attempt_release_hold(object(), tmp_path, version, issued_by='projectmanager_auto')

    assert result['status'] == 'blocked_atomic_recovery'
    hold = load_release_hold(tmp_path, version)
    assert hold.active is True
    assert hold.activated_reason == 'startup_recovery:inactive_hold_live_acceptance'
    assert json.loads((tmp_path / 'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'LIVE_ACCEPTANCE'


def test_published_flag_without_remote_or_exact_target_proof_is_not_green(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.18\n', encoding='utf-8')
    canonical = tmp_path / 'github_publication_state.json'
    _write_json(canonical, {
        'published': True,
        'version': '32.4.18',
        'publication_contract_removed': True,
        'message': 'claimed published but proof missing',
    })

    runtime = RuntimeCollector(
        project,
        running_release_version='32.4.18',
        github_publication_state_path=canonical,
    ).collect()
    checks = {c['name']: c for c in release_health_checks(runtime)}

    assert runtime['release_chain']['github_publication']['status'] == 'error'
    assert checks['release_github_publication']['status'] == 'RED'


def test_two_consecutive_releases_close_with_restart_between_hold_and_atomic(monkeypatch, tmp_path):
    accepted = []

    def validate(app, root, version):
        # Production validate_release_hold persists these fields; mirror that real side effect.
        record_hold_validation(Path(root), version, {'all': {'ok': True}}, 'ok')
        return {'status': 'ok', 'version': version, 'checks': {'all': {'ok': True}}, 'reconcile_status': 'ok', 'drift': []}

    def accept(root, version):
        path = Path(root) / 'Inbox/atomic_app_swap_state.json'
        payload = json.loads(path.read_text())
        assert payload['to_version'] == version
        payload['state'] = 'ACCEPTED'
        _write_json(path, payload)
        accepted.append(version)
        return {'status': 'accepted', 'state': 'ACCEPTED', 'version': version}

    monkeypatch.setattr(mode_runtime, 'validate_release_hold', validate)
    monkeypatch.setattr(mode_runtime, 'finalize_validated_atomic_release', accept)

    # Release A follows the normal 32.4.18 order.
    a = '32.4.18'
    activate_release_hold(tmp_path, a, 'release_install')
    _journal(tmp_path, a, source='32.4.17')
    first = auto_release.automatic_release_hold_once(object(), tmp_path, a)
    assert first['status'] == 'released'
    assert load_release_hold(tmp_path, a).active is False
    assert json.loads((tmp_path / 'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'

    # Release B simulates the old crash window: validation was green and hold became
    # inactive, but the process restarted before atomic acceptance persisted.
    b = '32.4.19'
    _validated_hold(tmp_path, b, active=False)
    _journal(tmp_path, b, source=a)
    second = auto_release.automatic_release_hold_once(object(), tmp_path, b)
    assert second['status'] == 'released'
    assert load_release_hold(tmp_path, b).active is False
    assert json.loads((tmp_path / 'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
    assert accepted == [a, b]


def test_ha_publisher_writes_local_and_shared_canonical_state():
    text = (ROOT / 'slimmemeterportal_import/rootfs/app/main.py').read_text(encoding='utf-8')
    assert 'GITHUB_CANONICAL_PUBLISH_STATE = NAS_RELEASE_ROOT / "github_publication_state.json"' in text
    writer = text.split('def _write_github_publish_state(payload):', 1)[1].split('\n\ndef ', 1)[0]
    assert '(GITHUB_PUBLISH_STATE, GITHUB_CANONICAL_PUBLISH_STATE)' in writer
    assert 'os.replace(tmp, path)' in writer


def test_pending_current_contract_cannot_be_satisfied_by_previous_release_publication(tmp_path):
    project = tmp_path / 'energy'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.18\n', encoding='utf-8')
    _write_json(project / 'Inbox/github_publication_state.json', {
        'published': True,
        'version': '32.4.17',
        'remote_head': 'old123',
        'local_head': 'old123',
        'publication_contract_removed': True,
        'message': 'previous release published',
    })
    _write_json(project / 'Inbox/ha_publication_required.json', {
        'status': 'publication_required',
        'version': '32.4.18',
    })

    runtime = RuntimeCollector(project, running_release_version='32.4.18').collect()
    checks = {c['name']: c for c in release_health_checks(runtime)}

    assert runtime['release_chain']['github_publication']['version'] == '32.4.17'
    assert runtime['release_chain']['github_publication']['contract_version'] == '32.4.18'
    assert checks['release_github_publication']['status'] == 'ORANGE'
    assert checks['release_github_publication']['reason'] == 'github_publication_pending'


def _pm_release_gate_result(tmp_path, checks, *, health_status='RED', audit_status='GREEN'):
    import os
    root = tmp_path / 'energy'
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    _write_json(runtime / 'status/current.json', {
        'release': {'version': '32.4.18'},
        'health': {'status': health_status, 'checks': checks},
    })
    _write_json(runtime / 'self_audit/current.json', {
        'status': audit_status, 'invalid': [], 'warnings': [], 'missing': []
    })
    version_path = root / 'App/VERSIE.txt'
    version_path.parent.mkdir(parents=True, exist_ok=True)
    version_path.write_text('32.4.18\n', encoding='utf-8')
    stat = (runtime / 'status/current.json').stat()
    os.utime(runtime / 'self_audit/current.json', (stat.st_atime + 1, stat.st_mtime + 1))
    _write_json(root / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'from_version': '32.4.17', 'to_version': '32.4.18'
    })
    return mode_runtime._projectmanager_self_audit_check(root)


def test_operational_energy_red_does_not_deadlock_release_acceptance(tmp_path):
    checks = [
        {
            'name': 'current_quarter_hour_snapshot',
            'status': 'RED',
            'reason': 'missing_invalid_or_stale',
            'details': {'age_seconds': 1834.3},
        },
        {
            'name': 'release_validation_hold',
            'status': 'ORANGE',
            'reason': 'missing_active_or_unvalidated',
            'details': {'active': True, 'validation_status': 'blocked'},
        },
        {
            'name': 'release_atomic_state',
            'status': 'RED',
            'reason': 'live_acceptance_blocks_release_ingress',
            'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE'}},
        },
    ]
    result = _pm_release_gate_result(tmp_path, checks)
    assert result['ok'] is True, result


def test_release_watcher_red_remains_release_blocking_even_with_operational_red(tmp_path):
    checks = [
        {
            'name': 'current_quarter_hour_snapshot',
            'status': 'RED',
            'reason': 'missing_invalid_or_stale',
            'details': {'age_seconds': 1834.3},
        },
        {
            'name': 'release_validation_hold',
            'status': 'ORANGE',
            'reason': 'missing_active_or_unvalidated',
            'details': {'active': True, 'validation_status': 'blocked'},
        },
        {
            'name': 'release_watcher',
            'status': 'RED',
            'reason': 'watcher_inactive_or_stale',
            'details': {'heartbeat_age_seconds': 1014.5, 'stale_after_seconds': 60},
        },
        {
            'name': 'release_atomic_state',
            'status': 'RED',
            'reason': 'live_acceptance_blocks_release_ingress',
            'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE'}},
        },
    ]
    result = _pm_release_gate_result(tmp_path, checks)
    assert result['ok'] is False
    assert 'release_watcher' in result['detail']
