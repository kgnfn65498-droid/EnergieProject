import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from runtime_sources import RuntimeCollector


def _write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def test_runtime_collector_distinguishes_nas_release_from_running_ha_addon(tmp_path):
    project = tmp_path / 'EnergieProject'
    _write(project / 'App/VERSIE.txt', '32.4.12\n')
    _write(project / 'App.__rollback_32.4.11/VERSIE.txt', '32.4.11\n')
    _write(project / 'Inbox/operating_mode/operating_mode_state.json', json.dumps({'effective_mode': 'DEVELOPMENT'}))
    _write(project / 'Inbox/.watcher.heartbeat', str(int(datetime.now(timezone.utc).timestamp())))
    _write(project / 'Inbox/atomic_app_swap_state.json', json.dumps({'state': 'ACCEPTED'}))
    _write(project / 'Inbox/github_publisher_state.json', json.dumps({'status': 'published', 'version': '32.4.12'}))

    result = RuntimeCollector(
        project,
        running_release_version='32.4.11',
    ).collect(now=datetime.now(timezone.utc))

    release = result['release']
    assert release['version'] == '32.4.11'
    assert release['ha_runtime_version'] == '32.4.11'
    assert release['nas_version'] == '32.4.12'
    assert release['available_update'] == '32.4.12'
    assert release['active_verified'] is True
    assert release['rollback_versions'] == ['32.4.11']
    assert release['source'].endswith('App/VERSIE.txt')


def test_release_chain_health_exposes_watcher_queues_lock_atomic_and_publisher(tmp_path):
    project = tmp_path / 'EnergieProject'
    _write(project / 'App/VERSIE.txt', '32.4.12\n')
    _write(project / 'Inbox/operating_mode/operating_mode_state.json', json.dumps({'effective_mode': 'DEVELOPMENT'}))
    heartbeat = project / 'Inbox/.watcher.heartbeat'
    _write(heartbeat, str(int(datetime.now(timezone.utc).timestamp())))
    now_epoch = datetime.now(timezone.utc).timestamp()
    os.utime(heartbeat, (now_epoch, now_epoch))
    _write(project / 'Inbox/incoming/EnergieProject_v32.4.12.zip', 'candidate')
    processing = project / 'Inbox/processing/EnergieProject_v32.4.10.zip'
    _write(processing, 'old')
    os.utime(processing, (now_epoch - 1200, now_epoch - 1200))
    (project / 'Inbox/.installer.lock').mkdir(parents=True)
    _write(project / 'Inbox/atomic_app_swap_state.json', json.dumps({'state': 'NEW_ACTIVE'}))
    _write(project / 'Inbox/github_publisher_state.json', json.dumps({'status': 'ready', 'version': '32.4.12'}))

    result = RuntimeCollector(project, running_release_version='32.4.11').collect(
        now=datetime.now(timezone.utc)
    )
    chain = result['release_chain']
    assert chain['watcher']['active'] is True
    assert chain['incoming']['count'] == 1
    assert chain['processing']['count'] == 1
    assert chain['processing']['stuck_count'] == 1
    assert chain['installer_lock']['active'] is True
    assert chain['atomic_swap']['state'] == 'NEW_ACTIVE'
    assert chain['publisher']['status'] == 'ready'
    assert chain['github_publication']['version'] == '32.4.12'


def test_release_chain_is_part_of_pm_health_and_stopped_watcher_is_red():
    from release_health import release_health_checks

    runtime = {
        'release_chain': {
            'watcher': {'active': False, 'heartbeat_age_seconds': 999.0},
            'incoming': {'count': 0, 'files': []},
            'processing': {'count': 1, 'stuck_count': 1, 'files': [{'name': 'old.zip', 'stuck': True}]},
            'installer_lock': {'active': False},
            'atomic_swap': {'state': 'ACCEPTED'},
            'publisher': {'status': 'error', 'version': '32.4.12'},
            'github_publication': {'status': 'error', 'version': '32.4.12'},
        }
    }
    checks = {item['name']: item for item in release_health_checks(runtime)}
    assert checks['release_watcher']['status'] == 'RED'
    assert checks['release_processing']['status'] == 'RED'
    assert checks['release_publisher']['status'] == 'RED'


def test_embedded_config_carries_running_addon_release_into_projectmanager(tmp_path):
    from embedded_config import build_embedded_config
    config = build_embedded_config(
        tmp_path / 'project',
        PM,
        running_release_version='32.4.11',
    )
    assert config.running_release_version == '32.4.11'


def test_release_health_explicitly_covers_full_release_chain_and_runtime_alignment():
    from release_health import release_health_checks

    runtime = {
        'release': {
            'version': '32.4.11',
            'ha_runtime_version': '32.4.11',
            'nas_version': '32.4.12',
            'available_update': '32.4.12',
            'rollback_version': '32.4.10',
            'rollback_versions': ['32.4.10'],
        },
        'release_chain': {
            'watcher': {'active': True, 'heartbeat_age_seconds': 1.0},
            'incoming': {'count': 1, 'files': [{'name': 'EnergieProject_v32.4.12.zip'}]},
            'processing': {'count': 0, 'stuck_count': 0, 'files': []},
            'installer_lock': {'active': False},
            'atomic_swap': {'state': 'ACCEPTED'},
            'publisher': {'status': 'ready', 'version': '32.4.12'},
            'github_publication': {
                'status': 'ready', 'version': '32.4.12',
                'contract_pending': True, 'contract_version': '32.4.12',
            },
        },
    }

    checks = {item['name']: item for item in release_health_checks(runtime)}

    assert checks['release_incoming']['details']['count'] == 1
    assert checks['release_installer_lock']['status'] == 'GREEN'
    assert checks['release_rollback']['status'] == 'GREEN'
    assert checks['release_github_publication']['status'] == 'ORANGE'
    assert checks['release_runtime_alignment']['status'] == 'ORANGE'
    assert checks['release_runtime_alignment']['details']['ha_runtime_version'] == '32.4.11'
    assert checks['release_runtime_alignment']['details']['nas_version'] == '32.4.12'
