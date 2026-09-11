from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
TOOLS = ROOT / 'tools'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from persistence import atomic_write_json
from protected_action_executor import ProtectedActionExecutor
from approval_ingress import ApprovalIngressConsumer
from decision_queue import DecisionQueue
from embedded_config import build_embedded_config
from state_reconciliation import StateReconciler
from progress_truth import build_task_progress
from project_hygiene import project_hygiene_check
from project_clearup import build_clearup_plan
from nas_container_cr_service import CORE_CONTAINERS, CONTROL_PLANE_MARKER, NasContainerCrService


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')


class _Store:
    def __init__(self, item=None): self.item = item or {}
    def get(self, _): return dict(self.item)
    def open_items(self): return []
    def complete(self, *_args, **_kwargs): pass


def test_32441_packages_dedicated_control_plane_and_only_two_actions():
    cp_path = TOOLS / 'control_plane/control_plane.py'
    qnap_path = TOOLS / 'control_plane/qnap_control_plane_bootstrap.py'
    compose_path = TOOLS / 'control_plane/docker-compose.containerstation.yml'
    assert cp_path.is_file() and qnap_path.is_file() and compose_path.is_file()
    cp = _load(cp_path, 'v32441_cp')
    assert cp.ALLOWED_ACTIONS == {'watcher_recreate', 'native_mcp_reload'}
    compose = compose_path.read_text(encoding='utf-8')
    assert 'container_name: energie-control-plane' in compose
    assert '/var/run/docker.sock:/var/run/docker.sock:rw' in compose
    assert 'network_mode: none' in compose
    assert 'com.energie.cr.required: "true"' in compose


def test_32441_protected_executor_routes_watcher_and_native_to_control_plane_not_tls():
    source = (PM / 'protected_action_executor.py').read_text(encoding='utf-8')
    assert "self.control_plane_request_root" in source
    assert "energie_control_plane_request_v1" in source
    assert "DockerTlsConfig.load" not in source
    assert "docker_engine_tls_client" not in source
    assert "self.control_plane_result_root" in source
    assert "'watcher_recreate.json'" in source
    assert "'native_mcp_reload.json'" in source


def test_32441_native_runtime_already_green_never_requests_second_restart(tmp_path):
    root = tmp_path / 'project'
    runtime = root / 'Inbox/native_mcp_runtime'
    runtime.mkdir(parents=True)
    fp = 'a' * 64
    _write(runtime / 'runtime_guard.json', {
        'schema': 'energie_native_mcp_runtime_guard_v2', 'status': 'GREEN',
        'ready': True, 'reload_required': False,
        'expected_fingerprint': fp, 'runtime_fingerprint': fp,
    })
    action = {'id': 'action1', 'action': 'native_mcp_reload', 'command_id': 'cmd1', 'decision_id': 'dec1'}
    command = {'id': 'cmd1', 'intent': 'native_mcp_reload'}
    decision = {'id': 'dec1', 'status': 'APPROVED', 'approved_by': 'Peter', 'kind': 'PRODUCTION_RESTART'}
    ex = ProtectedActionExecutor(root, _Store(), _Store(command), _Store(decision))
    result = ex._queue_native_mcp_reload(action, command, decision)
    assert result['ok'] is True
    assert result['executed'] is False
    assert result['restart_performed'] is False
    assert result['already_runtime_green'] is True
    assert not (root / 'Inbox/control_plane/requests/native_mcp_reload.json').exists()


def test_32441_control_plane_request_is_exact_decision_bound(tmp_path):
    root = tmp_path / 'project'
    guard = root / 'Inbox/native_mcp_runtime/runtime_guard.json'
    fp = 'b' * 64
    _write(guard, {'status':'RELOAD_REQUIRED','reload_required':True,'expected_fingerprint':fp})
    action = {'id': 'action2', 'action': 'native_mcp_reload', 'command_id': 'cmd2', 'decision_id': 'dec2'}
    command = {'id': 'cmd2', 'intent': 'native_mcp_reload'}
    decision = {'id': 'dec2', 'status': 'APPROVED', 'approved_by': 'Peter', 'kind': 'PRODUCTION_RESTART'}
    ex = ProtectedActionExecutor(root, _Store(), _Store(command), _Store(decision))
    result = ex._queue_native_mcp_reload(action, command, decision)
    req = json.loads(Path(result['request_path']).read_text())
    assert req == {
        'schema':'energie_control_plane_request_v1',
        'request_id': result['request_id'],
        'action':'native_mcp_reload',
        'approved_by':'Peter',
        'decision_id':'dec2',
        'expected_fingerprint':fp,
    }
    assert 'control_plane/requests/native_mcp_reload.json' in result['request_path'].replace('\\','/')


def test_32441_chat_approval_hotfix_adds_exact_pending_decision_ingress_only(tmp_path):
    hotfix = _load(TOOLS / 'native_mcp_runtime_contract_hotfix.py', 'v32441_hotfix')
    root = tmp_path / 'project'
    native = root / 'Infra/Docker/native-mcp'
    pm_root = root / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2'
    native.mkdir(parents=True)
    pm_root.mkdir(parents=True)
    (root / 'App/VERSIE.txt').parent.mkdir(parents=True, exist_ok=True)
    (root / 'App/VERSIE.txt').write_text('32.4.41\n')
    # Minimal sources with the exact stable anchors used by the hotfix.
    (native / 'server.py').write_text('from registry import mcp\n\nif __name__ == "__main__":\n    pass\n')
    (native / 'tools_projectmanager.py').write_text(
        'from pathlib import Path\nimport os\nfrom uuid import uuid4\nfrom registry import mcp\n'
        'READ_ONLY_ANNOTATIONS = {}\nWRITE_ANNOTATIONS = {}\n'
        'source_channel = source_ref = occurred_at = classification_hint = None\n'
        'RUNTIME_ROOT = Path("/project/Inbox/projectmanager_v2/RuntimeV2")\n'
        'def _write_immutable(root, envelope, *, max_bytes): return envelope["id"]\n'
        '# Remote decision resolution, direct deploy/purchase/payment and arbitrary\n'
        '# RuntimeV2 writes are deliberately absent. Protected approval stays local HA.\n'
    )
    for name in ('registry.py','crash_recovery.py','tools_recovery.py'):
        (native / name).write_text('# x\n')
    for name in ('command_gateway.py','projectmanager_api.py','secret_guard.py'):
        (pm_root / name).write_text('# x\n')
    result = hotfix.apply(root)
    assert result['approval_ingress_tool_present'] is True
    source = (native / 'tools_projectmanager.py').read_text(encoding='utf-8')
    assert 'def projectmanager_submit_approval(' in source
    assert 'decision_id' in source
    assert 'explicit_user_text' in source
    assert 'energie_pmv2_approval_ingress_v1' in source
    assert 'APPROVAL_INGRESS_ROOT' in source
    assert 'decisions_needed' in source
    assert 'PM_REMOTE_APPROVAL_ENABLED' in source
    fn = source[source.index('def projectmanager_submit_approval('):source.index('def projectmanager_submit_approval(')+5000]
    assert "item.get('status') == 'PENDING'" in source
    assert 'approved_by' in fn and "'Peter'" in fn
    assert '.resolve(' not in fn



def test_32441_embedded_pm_consumes_local_and_remote_approval_ingress(tmp_path):
    config = build_embedded_config(tmp_path / 'project', tmp_path / 'pm', running_release_version='32.4.41')
    roots = [item for item in str(config.approval_ingress_root).split(':') if item]
    normalized = [item.replace('\\', '/') for item in roots]
    assert any(item.endswith('/Inbox/projectmanager_v2/ApprovalIngress') for item in normalized)
    assert any(item.endswith('/Data/03_Systeem/Projectmanager/ApprovalIngress') for item in normalized)


def test_32441_approval_consumer_accepts_two_roots_exactly_once(tmp_path):
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    one = decisions.request('PRODUCTION_RESTART', 'one', fingerprint='one')
    two = decisions.request('PRODUCTION_RESTART', 'two', fingerprint='two')
    roots = [tmp_path / 'local', tmp_path / 'remote']
    for root in roots:
        root.mkdir()
    _write(roots[0] / 'local1.json', {
        'schema':'energie_pmv2_approval_ingress_v1','id':'local1',
        'decision_id':one['id'],'approved':True,'approved_by':'Peter',
    })
    _write(roots[1] / 'remote1.json', {
        'schema':'energie_pmv2_approval_ingress_v1','id':'remote1',
        'decision_id':two['id'],'approved':True,'approved_by':'Peter',
    })
    consumer = ApprovalIngressConsumer(':'.join(str(p) for p in roots), tmp_path / 'receipts.json', decisions)
    first = consumer.consume(max_items=20)
    second = consumer.consume(max_items=20)
    assert [x['status'] for x in first] == ['APPLIED','APPLIED']
    assert second == []
    assert decisions.get(one['id'])['status'] == 'APPROVED'
    assert decisions.get(two['id'])['status'] == 'APPROVED'


def test_32441_state_reconciliation_supersedes_pending_native_restart_when_runtime_green():
    class Dummy:
        pass
    reconciler = StateReconciler(Dummy(), Dummy(), Dummy(), None, None)
    decision = {
        'id':'dec','kind':'PRODUCTION_RESTART','status':'PENDING',
        'context':{'command_id':'cmd','intent':'native_mcp_reload'},
    }
    command = {
        'id':'cmd','status':'WAITING_APPROVAL','approval_decision_id':'dec',
        'intent':'native_mcp_reload',
    }
    fp = 'f' * 64
    runtime = {
        'native_mcp_runtime':{
            'status':'GREEN','ready':True,'reload_required':False,
            'expected_fingerprint':fp,'runtime_fingerprint':fp,
            'source':'/project/Inbox/native_mcp_runtime/runtime_guard.json',
        }
    }
    result = reconciler._evaluate_decision(decision, command, runtime, {})
    assert result['disposition'] == 'SUPERSEDED'
    assert result['changed'] is True
    assert result['evidence_refs'] == ['/project/Inbox/native_mcp_runtime/runtime_guard.json']

def test_32441_progress_percent_uses_completed_steps_not_current_step():
    now = datetime(2026, 9, 11, 19, 0, tzinfo=timezone.utc)
    task = {
        'status':'ACTIVE','step':1,'steps_total':8,
        'created_at':(now-timedelta(minutes=1)).isoformat(),
        'progress_history':[{'step':1,'at':(now-timedelta(minutes=1)).isoformat()}],
        'next_action':'first',
    }
    p = build_task_progress(task, now=now)
    assert p['completed_steps'] == 0
    assert p['remaining_steps'] == 8
    assert p['progress_percent'] == 0


def test_32441_build_contract_progress_always_surfaces_estimates_and_test_time():
    now = datetime(2026, 9, 11, 19, 0, tzinfo=timezone.utc)
    task = {
        'status':'ACTIVE','step':2,'steps_total':4,
        'created_at':(now-timedelta(minutes=10)).isoformat(),
        'progress_history':[{'step':1,'at':(now-timedelta(minutes=10)).isoformat()},{'step':2,'at':now.isoformat()}],
        'next_action':'next','build_contract_required':True,
        'build_metadata':{
            'thinking_level':'HOOG','release_version':'32.4.41','estimated_total_seconds':2400,
            'estimated_test_verification_seconds':600,'step_estimates_seconds':[450,450,450,450],
            'original_estimate_recorded_at':'2026-09-11T18:45:00+00:00',
        },
        'test_verification_actual_seconds':0,
    }
    p = build_task_progress(task, now=now)
    assert p['original_estimated_total_seconds'] == 2400
    assert p['estimated_test_verification_seconds'] == 600
    assert p['test_verification_actual_seconds'] == 0
    assert p['estimated_remaining_seconds'] is not None


def test_32441_nas_container_cr_requires_control_plane(tmp_path):
    assert 'energie-control-plane' in CORE_CONTAINERS
    service = NasContainerCrService(tmp_path / 'project', docker_client=object())
    required = {rel for _source, rel, _mode in service._required_project_files()}
    assert {
        'project/ControlPlane/control_plane.py',
        'project/ControlPlane/qnap_control_plane_bootstrap.py',
        'project/ControlPlane/docker-compose.containerstation.yml',
    }.issubset(required)
    assert CONTROL_PLANE_MARKER == 'ENERGIE_CONTROL_PLANE_INCLUDED=YES'
    source = (PM / 'nas_container_cr_service.py').read_text(encoding='utf-8')
    assert 'CONTROL_PLANE_MARKER' in source


def test_32441_hygiene_treats_inbox_develop_as_canonical_not_debt(tmp_path):
    root = tmp_path / 'project'
    (root / 'Inbox/Develop/task-a').mkdir(parents=True)
    (root / 'Inbox/Develop/task-a/work.json').write_text('{}')
    result = project_hygiene_check(root)
    assert result['details']['inbox_develop_child_count'] == 1
    assert result['details']['inbox_root_development_debt_count'] == 0


def test_32441_hygiene_flags_loose_inbox_development_artifacts(tmp_path):
    root = tmp_path / 'project'
    (root / 'Inbox').mkdir(parents=True)
    (root / 'Inbox/attempt_32441_tmp').mkdir()
    (root / 'Inbox/dev_probe.json').write_text('{}')
    result = project_hygiene_check(root)
    assert result['status'] == 'ORANGE'
    assert result['details']['inbox_root_development_debt_count'] == 2



def test_32441_clearup_quarantines_loose_inbox_development_debt_but_not_develop(tmp_path):
    root = tmp_path / 'project'
    (root / 'Inbox/Develop/live-task').mkdir(parents=True)
    (root / 'Inbox/Develop/live-task/work.json').write_text('{}')
    (root / 'Inbox/attempt_old').mkdir(parents=True)
    (root / 'Inbox/attempt_old/x.txt').write_text('x')
    (root / 'Inbox/dev_probe.json').write_text('{}')
    plan = build_clearup_plan(root, current_version='32.4.41')
    by_path = {item['source_path']: item for item in plan['items']}
    assert 'Inbox/attempt_old' in by_path
    assert 'Inbox/dev_probe.json' in by_path
    assert 'Inbox/Develop' not in by_path
    assert not any(key.startswith('Inbox/Develop/') for key in by_path)
    assert by_path['Inbox/attempt_old']['disposition'] == 'CLEARUP'
    assert by_path['Inbox/dev_probe.json']['disposition'] == 'CLEARUP'

def test_32441_release_audit_badge_counts_true_rounds_not_versions():
    from release_audit_recurrence import audit_badge
    assert audit_badge(status='GREEN', repair_round=1, label='watcher') == '🟢 1 — watcher'
    assert audit_badge(status='RED', repair_round=3, label='native MCP') == '🔴 3 — native MCP'
    assert audit_badge(status='ORANGE', repair_round=0, label='chat approval') == '🟠 0 — chat approval'
    with pytest.raises(ValueError):
        audit_badge(status='RED', repair_round=-1, label='bad')


def test_32441_release_identity():
    assert (ROOT / 'VERSIE.txt').read_text().strip() == '32.4.41'
    assert (PM / 'VERSION.txt').read_text().strip() == '2.0.0-rc28'


def test_32441_control_plane_source_sync_is_exact_atomic_and_no_delete(tmp_path):
    sync = _load(TOOLS / 'control_plane_source_sync.py', 'v32441_cp_sync')
    root = tmp_path / 'project'
    source = root / 'App/tools/control_plane'
    target = root / 'Data/03_Systeem/Projectmanager/ControlPlane'
    source.mkdir(parents=True)
    target.mkdir(parents=True)
    expected = {
        'control_plane.py': b'cp-v1\n',
        'qnap_control_plane_bootstrap.py': b'boot-v1\n',
        'docker-compose.containerstation.yml': b'compose-v1\n',
    }
    for name, data in expected.items():
        (source / name).write_bytes(data)
    extra = target / 'operator-note.txt'
    extra.write_text('keep me', encoding='utf-8')
    result = sync.sync_control_plane_source(root)
    assert result['status'] == 'GREEN'
    assert result['files_total'] == 3
    assert set(result['readback_sha256']) == set(expected)
    assert extra.read_text(encoding='utf-8') == 'keep me'
    for name, data in expected.items():
        assert (target / name).read_bytes() == data
        assert (target / name).stat().st_mode & 0o777 == 0o644


def test_32441_watcher_syncs_control_plane_source_before_contract_and_native_guard():
    source = (TOOLS / 'release_watcher.sh').read_text(encoding='utf-8')
    assert 'CONTROL_PLANE_SOURCE_SYNC=' in source
    assert 'process_control_plane_source_sync(){' in source
    startup = source[source.index('log "Release watcher gestart;'):source.index('while :; do')]
    sync_pos = startup.index('process_control_plane_source_sync')
    watcher_pos = startup.index('process_watcher_container_contract')
    native_pos = startup.index('process_native_mcp_runtime_contract_hotfix')
    assert sync_pos < watcher_pos
    assert sync_pos < native_pos
