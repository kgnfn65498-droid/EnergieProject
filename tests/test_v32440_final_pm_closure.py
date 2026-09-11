from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PM_ROOT = Path(__file__).resolve().parents[1] / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM_ROOT) not in sys.path:
    sys.path.insert(0, str(PM_ROOT))

from persistence import atomic_write_json
from roadmap_regie import RoadmapRegie
from task_engine import TaskStore
from state_reconciliation import StateReconciler
from progress_truth import build_task_progress
from command_gateway import plan_command
from docker_engine_tls_client import DockerEngineTlsClient
from projectmanager_api import ProjectmanagerAPI


def test_shared_atomic_mode_is_explicit_and_private_default_stays_private(tmp_path):
    shared = tmp_path / 'canonical.json'
    atomic_write_json(shared, {'ok': True}, mode=0o644)
    assert (shared.stat().st_mode & 0o777) == 0o644
    assert json.loads(shared.read_text()) == {'ok': True}
    private = tmp_path / 'runtime.json'
    atomic_write_json(private, {'private': True})
    assert (private.stat().st_mode & 0o077) == 0


def test_roadmap_ledger_acceptance_matrix_tracks_live_proof(tmp_path):
    path = tmp_path / 'roadmap.json'
    atomic_write_json(path, {'schema': 2, 'items': [{
        'key': '32-4-closure-live', 'title': 'closure', 'priority': 1, 'mode': 'MAINTENANCE',
        'executor': 'embedded', 'auto_select': False, 'depends_on': [], 'acceptance': 'live green',
        'status': 'OPEN', 'acceptance_matrix_required': True, 'ledger_refs': ['UDL-001'],
        'required_tests': ['watcher_v3'], 'live_required': True, 'acceptance_state': 'LIVE_REQUIRED',
        'evidence_refs': [], 'carry_forward': ['watcher'],
    }]})
    regie = RoadmapRegie(path)
    summary = regie.acceptance_summary()
    assert summary['counts']['LIVE_REQUIRED'] == 1
    with pytest.raises(ValueError):
        regie.mark_done_by_key('32-4-closure-live', evidence='not live proven')
    regie.mark_acceptance('32-4-closure-live', 'LIVE_PROVEN', evidence_refs=['live:watcher'], carry_forward=[])
    done = regie.mark_done_by_key('32-4-closure-live', evidence='series closure green')
    assert done['status'] == 'DONE'
    assert done['acceptance_state'] == 'CLOSED_COLD'


class _EmptyStore:
    def all(self): return []
    def open_items(self): return []


def test_stale_release_build_task_is_runtime_first_superseded(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    task = tasks.start('32.4.39 Definitieve closure-build', 'build 32.4.39', mode='DEVELOPMENT', steps_total=6, priority=1)
    reconciler = StateReconciler(tasks, _EmptyStore(), _EmptyStore(), None, None)
    runtime = {
        'release': {'version': '32.4.40', 'source': '/project/App/VERSIE.txt'},
        'release_chain': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE', 'source': '/project/Inbox/atomic_app_swap_state.json', 'raw': {'to_version': '32.4.40'}}},
    }
    result = reconciler.reconcile(runtime=runtime)
    assert result['changed_count'] == 1
    final = tasks.get(task['id'])
    assert final['status'] == 'SUPERSEDED'
    assert '32.4.40' in final['superseded_reason']


def test_same_release_live_acceptance_also_supersedes_preinstall_build_task(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    task = tasks.start('32.4.40 closure-build', 'build 32.4.40', mode='DEVELOPMENT', steps_total=6, priority=1)
    reconciler = StateReconciler(tasks, _EmptyStore(), _EmptyStore(), None, None)
    runtime = {
        'release': {'version': '32.4.40', 'source': '/project/App/VERSIE.txt'},
        'release_chain': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE', 'source': '/project/Inbox/atomic_app_swap_state.json', 'raw': {'to_version': '32.4.40'}}},
    }
    reconciler.reconcile(runtime=runtime)
    assert tasks.get(task['id'])['status'] == 'SUPERSEDED'


def test_progress_keeps_original_estimate_and_actual_step_timing():
    now = datetime(2026, 9, 11, 14, 10, tzinfo=timezone.utc)
    task = {
        'status': 'ACTIVE', 'step': 3, 'steps_total': 6, 'created_at': (now - timedelta(minutes=30)).isoformat(),
        'next_action': 'next', 'blockers': [],
        'progress_history': [
            {'step': 1, 'at': (now - timedelta(minutes=30)).isoformat()},
            {'step': 2, 'at': (now - timedelta(minutes=20)).isoformat()},
            {'step': 3, 'at': (now - timedelta(minutes=5)).isoformat()},
        ],
        'build_contract_required': True,
        'build_metadata': {
            'thinking_level': 'HOOG', 'release_version': '32.4.40', 'estimated_total_seconds': 2400,
            'estimated_test_verification_seconds': 600, 'step_estimates_seconds': [300]*6,
            'original_estimate_recorded_at': '2026-09-11T13:30:00+00:00',
        },
        'test_verification_actual_seconds': 480,
    }
    progress = build_task_progress(task, now=now)
    assert progress['step_actual_seconds']['1'] == 600
    assert progress['step_actual_seconds']['2'] == 900
    assert progress['test_verification_actual_seconds'] == 480
    assert progress['development_build_contract']['estimated_total_seconds'] == 2400
    assert progress['estimated_remaining_seconds'] is not None
    assert progress['estimate_variance_seconds'] == -600
    assert progress['development_efficiency']['planning_ratio'] == pytest.approx(0.75)


def _desired_watcher_info(energy_source='/share/AI Projecten/EnergieProject'):
    return {
        'Config': {'Image': 'python:3.12-slim','Cmd': ['sh', '/energy/App/tools/release_watcher.sh'],'Env': ['ENERGIE_WATCHER_CONTAINER_CONTRACT=3']},
        'HostConfig': {'NetworkMode': 'none','CapDrop': ['ALL'],'CapAdd': ['DAC_OVERRIDE', 'DAC_READ_SEARCH', 'FOWNER'],'SecurityOpt': ['no-new-privileges'],'RestartPolicy': {'Name': 'unless-stopped'}},
        'State': {'Running': True},
        'Mounts': [{'Destination': '/energy', 'Source': energy_source},{'Destination': '/var/run/docker.sock', 'Source': '/var/run/docker.sock'}],
    }


class _FakeWatcherClient(DockerEngineTlsClient):
    def __init__(self):
        self.calls = []
        self.started = False
        self.image_checked = False
        self.energy_source = '/share/AI Projecten/EnergieProject'

    def container_inspect(self, name):
        self.calls.append(('inspect', name))
        if self.started:
            return _desired_watcher_info(self.energy_source)
        current = _desired_watcher_info(self.energy_source)
        current['Mounts'] = [{'Destination': '/energy', 'Source': self.energy_source}]
        return current

    def image_inspect(self, name):
        self.calls.append(('image_inspect', name))
        self.image_checked = True
        return {'Id': 'sha256:test'}

    def _json_call(self, method, path, *, body=None, expected=(200,), allow_not_found=False):
        self.calls.append((method, path, body))
        if method == 'DELETE':
            assert self.image_checked is True
            return {}
        if method == 'POST' and '/containers/create?' in path:
            assert body['Image'] == 'python:3.12-slim'
            assert body['Cmd'] == ['sh', '/energy/App/tools/release_watcher.sh']
            assert body['HostConfig']['NetworkMode'] == 'none'
            assert set(body['HostConfig']['CapAdd']) == {'DAC_OVERRIDE','DAC_READ_SEARCH','FOWNER'}
            assert '/var/run/docker.sock:/var/run/docker.sock' in body['HostConfig']['Binds']
            return {'Id': 'new-watcher'}
        if method == 'POST' and path.endswith('/start'):
            self.started = True
            return {}
        raise AssertionError((method, path, body))


def test_watcher_recreate_is_protected_and_exact_bounded_capability():
    plan = plan_command({'intent': 'watcher_recreate', 'source': 'mcp_remote'})
    assert plan['action'] == 'watcher_recreate'
    assert plan['allowed_without_approval'] is False
    assert plan['decision_kind'] == 'PRODUCTION_RESTART'
    client = _FakeWatcherClient()
    result = client.recreate_release_watcher()
    assert result['ok'] is True
    assert result['recreated'] is True
    assert result['contract']['docker_socket'] is True


def test_orchestrator_queues_watcher_before_native_and_exports_handover_truth():
    source = (PM_ROOT / 'orchestrator.py').read_text(encoding='utf-8')
    assert "_queue_324_action_once('watcher_recreate', release_version)" in source
    watcher_pos = source.index("_queue_324_action_once('watcher_recreate', release_version)")
    native_pos = source.index("_queue_324_action_once('native_mcp_reload', release_version)")
    assert watcher_pos < native_pos
    assert "handover['acceptance_matrix']" in source
    assert "handover['development_efficiency']" in source
    assert "handover['development_context']" in source


def test_nomad_reads_same_matrix_efficiency_and_development_context(tmp_path):
    runtime = tmp_path / 'RuntimeV2'
    (runtime / 'status').mkdir(parents=True)
    status = {'project_id': 'energie','mode': 'MAINTENANCE','health': {'status':'ORANGE'},'release': {'version':'32.4.40'},'active_task': {'id':'t','step':2,'steps_total':6},'progress': {'step_label':'Stap 2/6'},'development_build_contract': {'contract_version':'2026-09-11.v2'},'development_efficiency': {'planning_ratio': 0.9},'acceptance_matrix': {'schema':'energie_roadmap_ledger_acceptance_matrix_v1'},'development_context': {'live_handover_primary': True},'next_action':'watcher','needs_human':False,'decisions_needed':[]}
    atomic_write_json(runtime / 'status/current.json', status)
    context = ProjectmanagerAPI(runtime).nomad_context()
    assert context['active_task'] == status['active_task']
    assert context['progress'] == status['progress']
    assert context['acceptance_matrix'] == status['acceptance_matrix']
    assert context['development_efficiency'] == status['development_efficiency']
    assert context['development_context'] == status['development_context']


def test_canonical_migration_requests_explicit_shared_mode():
    source = (PM_ROOT / 'canonical_roadmap_migration.py').read_text(encoding='utf-8')
    assert 'atomic_write_json(target, migrated, mode=0o644)' in source


def test_project_agreements_forbid_user_terminal_fallback():
    agreements = (Path(__file__).resolve().parents[1] / 'PROJECT_AFSPRAKEN.md').read_text(encoding='utf-8')
    section = agreements.split('## 32.4.40 stabiele ontwikkelstandaard', 1)[1]
    assert 'Terminal is uitsluitend uitzonderlijke' not in section
    assert 'geen Terminal' in section
    assert 'ontbrekende capability' in section
