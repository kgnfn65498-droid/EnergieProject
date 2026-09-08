import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from handover import build_handover
from projectmanager_api import ProjectmanagerAPI
from progress_truth import build_task_progress
from task_engine import TaskStore


def test_progress_truth_contains_complete_step_timing_blocker_and_trend_fields():
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    task = {
        'id': 'task-1', 'title': '32.4.12', 'status': 'ACTIVE',
        'step': 3, 'steps_total': 7, 'next_action': 'DoD sluiten',
        'blockers': ['geen'],
        'created_at': (now - timedelta(hours=2)).isoformat(),
        'progress_history': [
            {'step': 1, 'at': (now - timedelta(hours=2)).isoformat()},
            {'step': 2, 'at': (now - timedelta(hours=1, minutes=20)).isoformat()},
            {'step': 3, 'at': (now - timedelta(minutes=50)).isoformat()},
        ],
    }

    progress = build_task_progress(task, now=now)

    assert progress['step_label'] == 'Stap 3/7'
    assert progress['step'] == 3 and progress['steps_total'] == 7
    assert progress['completed_steps'] == 2
    assert progress['remaining_steps'] == 5
    assert progress['next_step'] == 'DoD sluiten'
    assert progress['elapsed_seconds'] == 7200
    assert progress['estimated_remaining_seconds'] is not None
    assert progress['blockers'] == ['geen']
    assert progress['status_color'] == 'GREEN'
    assert progress['progress_percent'] == 43
    assert progress['planning_trend'] in {'faster', 'stable', 'slower'}


def test_task_store_records_progress_history_for_learning_curve(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    task = tasks.start('release', 'release', mode='DEVELOPMENT', steps_total=4)
    task = tasks.progress(task['id'], step=2)
    task = tasks.progress(task['id'], step=3)
    assert [item['step'] for item in task['progress_history']] == [1, 2, 3]


def test_status_handover_and_nomad_use_same_progress_payload(tmp_path):
    now = datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc)
    task = {
        'id': 'task-1', 'title': 'closure', 'goal': 'closure', 'status': 'ACTIVE',
        'step': 2, 'steps_total': 5, 'next_action': 'test', 'blockers': [],
        'created_at': (now - timedelta(minutes=30)).isoformat(),
    }
    progress = build_task_progress(task, now=now)
    handover = build_handover(
        mode={'mode': 'DEVELOPMENT'}, active_task=task,
        release={'version': '32.4.12'}, progress=progress,
    )
    runtime = tmp_path / 'RuntimeV2'
    (runtime / 'status').mkdir(parents=True)
    (runtime / 'handover').mkdir(parents=True)
    status = {
        'project_id': 'energie', 'mode': 'DEVELOPMENT', 'health': {'status': 'GREEN'},
        'release': {'version': '32.4.12'}, 'active_task': task,
        'progress': progress, 'next_action': task['next_action'],
        'needs_human': False, 'decisions_needed': [],
    }
    (runtime / 'status/current.json').write_text(json.dumps(status), encoding='utf-8')
    (runtime / 'handover/current.json').write_text(json.dumps(handover), encoding='utf-8')
    api = ProjectmanagerAPI(runtime)

    assert handover['progress'] == progress
    assert api.nomad_context()['progress'] == progress
    assert api.status()['progress'] == api.handover()['progress'] == api.nomad_context()['progress']


def test_manager_status_publishes_full_runtime_release_and_shared_progress(tmp_path):
    from manager_config import ManagerConfig
    from manager_service import ManagerService

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.12\n', encoding='utf-8')
    reports = tmp_path / 'reports'
    reports.mkdir()

    class Runtime:
        def collect(self):
            return {
                'release': {
                    'version': '32.4.11',
                    'ha_runtime_version': '32.4.11',
                    'nas_version': '32.4.12',
                    'available_update': '32.4.12',
                    'rollback_version': '32.4.10',
                    'active_verified': True,
                },
                'operating_mode': {'effective_mode': 'DEVELOPMENT'},
            }

    class Health:
        def collect(self, *, now=None):
            return []

    config = ManagerConfig(
        project_root=str(project), system_root=str(tmp_path / 'RuntimeV2'),
        input_root=str(tmp_path / 'input'), recovery_root=str(tmp_path / 'recovery'),
        reports_root=str(reports), interval_seconds=300, timezone='Europe/Amsterdam',
        ha_base_url='', ha_token='', ha_notify_service='', running_release_version='32.4.11',
    )
    service = ManagerService(config, runtime_collector=Runtime(), health_collector=Health())
    task = service.tasks.start('closure', 'closure', mode='DEVELOPMENT', steps_total=4)
    service.tasks.progress(task['id'], step=2, next_action='audit')

    status = service.run_once(now=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc))
    handover = service.handover.load()

    assert status['release']['version'] == '32.4.11'
    assert status['release']['nas_version'] == '32.4.12'
    assert status['release']['available_update'] == '32.4.12'
    assert status['progress']['step_label'] == 'Stap 2/4'
    assert handover['progress'] == status['progress']
