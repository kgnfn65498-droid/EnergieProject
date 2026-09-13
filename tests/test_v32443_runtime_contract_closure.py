import json
import os
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for path in (str(APP), str(PM), str(TOOLS)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def test_32443_uploaded_build_basis_identity_is_exact_32442():
    evidence = json.loads((ROOT / 'docs/32.4.43-build-basis.json').read_text(encoding='utf-8'))
    assert evidence['target_release'] == '32.4.43'
    assert evidence['previous_release'] == '32.4.42'
    assert evidence['artifact_sha256'] == 'a5cf6a3135580df504a1a70b71708b477ba247141d8262585c4f544423b2f9fc'
    assert evidence['verified_against_live_atomic_swap'] is True
    assert evidence['manifest_files_verified'] == 419


def test_32443_project_close_missing_or_stale_is_fail_closed_deferred(tmp_path):
    from project_close_state import load_project_close, write_project_close

    missing = load_project_close(tmp_path, active_release='32.4.43')
    assert missing['state'] == 'DEFERRED'
    assert missing['current'] is False
    write_project_close(tmp_path, release_version='32.4.42', state='REQUESTED', reason='old')
    stale = load_project_close(tmp_path, active_release='32.4.43')
    assert stale['state'] == 'DEFERRED'
    assert stale['reason'] == 'release_mismatch'


def test_32443_project_close_current_requested_roundtrip(tmp_path):
    from project_close_state import load_project_close, write_project_close

    saved = write_project_close(tmp_path, release_version='32.4.43', state='REQUESTED', reason='closure incomplete')
    loaded = load_project_close(tmp_path, active_release='32.4.43')
    assert saved['state'] == loaded['state'] == 'REQUESTED'
    assert loaded['current'] is True
    assert loaded['release_version'] == '32.4.43'


def test_32443_clearup_deferred_short_circuits_before_expensive_or_mutating_gates(tmp_path, monkeypatch):
    import project_clearup_auto as auto
    from project_close_state import write_project_close

    write_project_close(tmp_path, release_version='32.4.43', state='DEFERRED', reason='technical gates not green')
    touched = []
    monkeypatch.setattr(auto, '_approval_ok', lambda _root: touched.append('approval') or True)
    monkeypatch.setattr(auto, '_release_accepted', lambda *_a, **_k: touched.append('accepted') or (True, {}))
    monkeypatch.setattr(auto, '_hold_released', lambda *_a, **_k: touched.append('hold') or (True, {}))
    monkeypatch.setattr(auto, '_clearup_destination_gate', lambda *_a, **_k: touched.append('destination') or {'ok': True})
    monkeypatch.setattr(auto, '_current_release_cr_gate', lambda *_a, **_k: touched.append('cr') or {'ok': True, 'fingerprint': 'x'})

    result = auto.clearup_auto_gate(tmp_path, app_version='32.4.43')
    assert result['ready'] is False
    assert result['blockers'] == ['project_close_deferred']
    assert touched == []


def test_32443_command_store_supersedes_stale_release_owned_closure_commands(tmp_path):
    from command_store import CommandStore

    store = CommandStore(tmp_path / 'commands.json')
    old_project = store.enqueue({'intent': 'project_cr_create', 'release_version': '32.4.42'})
    old_nas = store.enqueue({'intent': 'nas_container_cr_create', 'release_version': '32.4.42'})
    current = store.enqueue({'intent': 'project_cr_create', 'release_version': '32.4.43', 'ingress_id': 'current'})
    changed = store.supersede_stale_release_commands('32.4.43')
    assert {item['id'] for item in changed} == {old_project['id'], old_nas['id']}
    assert store.get(old_project['id'])['status'] == 'SUPERSEDED'
    assert store.get(old_nas['id'])['status'] == 'SUPERSEDED'
    assert store.get(current['id'])['status'] == 'PENDING'


def test_32443_command_processor_never_executes_stale_project_cr(tmp_path):
    from command_processor import CommandProcessor
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from task_engine import TaskStore

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')

    class Mode:
        def set(self, *a, **k): return None
    class CR:
        project_root = project
        def __init__(self): self.called = False
        def create(self, **kwargs):
            self.called = True
            return {'ok': True, 'status': 'GREEN', 'deep_verified': True}
    cr = CR()
    commands = CommandStore(tmp_path / 'commands.json')
    item = commands.enqueue({'intent': 'project_cr_create', 'release_version': '32.4.42'})
    processor = CommandProcessor(commands, DecisionQueue(tmp_path/'decisions.json'), Mode(), TaskStore(tmp_path/'tasks.json'), project_cr_service=cr, project_root=project)
    result = processor.process_next()
    assert result['id'] == item['id']
    assert result['status'] == 'SUPERSEDED'
    assert cr.called is False


def test_32443_cr_bridge_binds_command_id_and_expected_release(tmp_path, monkeypatch):
    from project_cr_service import ConfiguredProjectCrService

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')
    bridge = project / 'Inbox/project_cr_local'
    bridge.mkdir(parents=True)
    monkeypatch.setattr('project_cr_service.secrets.token_hex', lambda _n: 'a'*32)
    _write(bridge / 'result.json', {
        'schema': 'energie_project_cr_local_result_v1', 'request_id': 'a'*32,
        'command_id': 'b'*32, 'operation': 'project_cr_create', 'status': 'GREEN', 'ok': True,
        'version': '32.4.43', 'deep_verified': True,
    })
    service = ConfiguredProjectCrService(project, timeout_seconds=.1, poll_seconds=.005)
    result = service.create(command_id='b'*32, expected_release='32.4.43')
    request = json.loads((bridge/'request.json').read_text(encoding='utf-8'))
    assert request['command_id'] == 'b'*32
    assert request['expected_runtime_version'] == '32.4.43'
    assert result['command_id'] == 'b'*32


def test_32443_nas_cr_bridge_binds_command_id_and_expected_release(tmp_path, monkeypatch):
    from nas_container_cr_service import ConfiguredNasContainerCrService

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')
    bridge = project / 'Inbox/nas_container_cr_local'
    bridge.mkdir(parents=True)
    monkeypatch.setattr('nas_container_cr_service.secrets.token_hex', lambda _n: 'c'*32)
    _write(bridge / 'result.json', {
        'schema': 'energie_nas_container_cr_local_result_v1', 'request_id': 'c'*32,
        'command_id': 'd'*32, 'status': 'GREEN', 'ok': True, 'version': '32.4.43',
        'production_containers_changed': False,
    })
    service = ConfiguredNasContainerCrService(project, timeout_seconds=.1, poll_seconds=.005)
    result = service.create(command_id='d'*32, expected_release='32.4.43')
    request = json.loads((bridge/'request.json').read_text(encoding='utf-8'))
    assert request['command_id'] == 'd'*32
    assert request['expected_runtime_version'] == '32.4.43'
    assert result['command_id'] == 'd'*32


def _minimal_self_audit_runtime(root: Path, generation='g1'):
    now = datetime.now(timezone.utc).isoformat()
    shared = {
        'conversation_intake': {}, 'canonical_roadmap': {}, 'state_reconciliation': {},
        'progress': {}, 'acceptance_matrix': {}, 'development_efficiency': {},
        'development_context': {},
    }
    _write(root/'status/current.json', {
        'schema':'energie_projectmanager_status_v2', 'updated_at':now, 'mode':'DEVELOPMENT',
        'health':{'status':'GREEN'}, 'release':{'version':'32.4.43','active_verified':True},
        'cycle_generation': generation, 'provenance':{'generation':generation,'phase':'FINAL'},
        'manager': {'version':'2.0.0-rc30'}, 'open_issues': [], 'active_task': None,
        'pending_commands': 0, 'handoffs': [], **shared,
    })
    _write(root/'heartbeat/manager.json', {
        'heartbeat_at':now,'mode':'DEVELOPMENT','health':'GREEN','cycle_generation':generation,
        'provenance':{'generation':generation,'phase':'FINAL'},
    })
    _write(root/'handover/current.json', {
        'mode':'DEVELOPMENT','release':{'version':'32.4.43'},'cycle_generation':generation,
        'provenance':{'generation':generation,'phase':'FINAL'},
        'manager': {'version':'2.0.0-rc30'}, 'open_issues': [], 'active_task': None,
        **shared,
    })
    (root/'audit').mkdir(parents=True, exist_ok=True)
    (root/'audit/events.jsonl').write_text(json.dumps({'event_type':'test'})+'\n', encoding='utf-8')


def test_32443_self_audit_requires_one_final_cycle_generation(tmp_path):
    from self_audit import SelfAuditor

    _minimal_self_audit_runtime(tmp_path, 'gen-1')
    audit = SelfAuditor(tmp_path, running_release_version='32.4.43').run(require_coordination=True)
    assert audit['status'] == 'GREEN'
    assert audit['cycle_generation'] == 'gen-1'
    assert audit['provenance']['phase'] == 'FINAL'

    hb = json.loads((tmp_path/'heartbeat/manager.json').read_text())
    hb['cycle_generation'] = 'wrong'
    _write(tmp_path/'heartbeat/manager.json', hb)
    red = SelfAuditor(tmp_path, running_release_version='32.4.43').run(require_coordination=True)
    assert red['status'] == 'RED'
    assert any(item['reason'] == 'cycle_generation_mismatch' for item in red['invalid'])


def test_32443_release_hold_self_audit_rejects_generation_mismatch(tmp_path):
    from operating_mode_runtime import _projectmanager_self_audit_check

    runtime = tmp_path / 'Inbox/projectmanager_v2/RuntimeV2'
    _minimal_self_audit_runtime(runtime, 'gen-current')
    (tmp_path/'App').mkdir(parents=True)
    (tmp_path/'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')
    status = json.loads((runtime/'status/current.json').read_text())
    status['health'] = {'status':'GREEN','checks':[]}
    _write(runtime/'status/current.json', status)
    _write(runtime/'self_audit/current.json', {
        'status':'GREEN', 'status_updated_at':status['updated_at'], 'cycle_generation':'wrong',
        'provenance':{'generation':'wrong','phase':'FINAL'}, 'invalid':[], 'warnings':[],
    })
    result = _projectmanager_self_audit_check(tmp_path)
    assert result['ok'] is False
    assert 'generation mismatch' in result['detail']


def test_32443_manager_document_sync_permission_failure_is_best_effort(tmp_path):
    from manager_service import ManagerService

    class Issues:
        def __init__(self): self.opened=[]; self.resolved=[]
        def open(self, fingerprint, **kwargs): self.opened.append((fingerprint, kwargs))
        def resolve_fingerprint(self, fingerprint, **kwargs): self.resolved.append((fingerprint, kwargs))

    service = ManagerService.__new__(ManagerService)
    service.root = tmp_path/'RuntimeV2'
    service.root.mkdir(parents=True)
    service.issues = Issues()
    service._sync_managed_documents = lambda _status: (_ for _ in ()).throw(PermissionError('static KB read-only'))
    service._sync_development_context_documents = lambda _status: (_ for _ in ()).throw(PermissionError('static development lessons read-only'))
    result = service._sync_documents_best_effort({'release':{'version':'32.4.43'}})
    assert result['status'] == 'ORANGE'
    assert len(result['errors']) == 2
    assert (service.root/'development_context/current.json').is_file()
    assert service.issues.opened


def test_32443_approval_ui_uses_canonical_decision_queue_not_status_snapshot(tmp_path):
    import projectmanager_web as web

    runtime = tmp_path/'Inbox/projectmanager_v2/RuntimeV2'
    _write(runtime/'status/current.json', {'decisions_needed':[{'id':'stale','status':'PENDING'}]})
    _write(runtime/'decisions/queue.json', {'schema':1,'items':[
        {'id':'canonical','kind':'PRODUCTION_RESTART','question':'q','status':'PENDING','updated_at':'2026-09-12T12:00:00+00:00'},
        {'id':'done','kind':'PRODUCTION_RESTART','question':'q2','status':'APPROVED','updated_at':'2026-09-12T11:00:00+00:00'},
    ]})
    pending = web._read_pending(tmp_path)
    assert [item['id'] for item in pending] == ['canonical']
    meta = web._pending_decision_meta(tmp_path)
    assert meta['pending_count'] == 1
    assert meta['latest_updated_at'] == '2026-09-12T12:00:00+00:00'


def test_32443_control_plane_bootstrap_precreates_cross_runtime_mailboxes(tmp_path):
    # Live-equivalent regression: bootstrap as owner, then write as another uid.
    import importlib.util

    cp_dir = TOOLS / 'control_plane'
    sys.path.insert(0, str(cp_dir))
    spec = importlib.util.spec_from_file_location('qnap_control_plane_bootstrap_v32443', cp_dir/'qnap_control_plane_bootstrap.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)

    # pytest's temp parents can be private; make this isolated branch traversable
    # so the child uid really tests the mailbox mode rather than fixture parents.
    for path in (tmp_path.parent.parent, tmp_path.parent, tmp_path):
        try:
            path.chmod(0o777)
        except OSError:
            pass
    inbox = tmp_path/'Inbox'
    result = module._ensure_control_plane_mailboxes(inbox)
    requests = inbox/'control_plane/requests'
    results = inbox/'control_plane/results'
    assert requests.is_dir() and results.is_dir()
    assert stat.S_IMODE(requests.stat().st_mode) == 0o777
    assert stat.S_IMODE(results.stat().st_mode) == 0o777
    assert result['mode'] == '0777'

    if os.geteuid() == 0 and hasattr(os, 'fork'):
        pid = os.fork()
        if pid == 0:
            try:
                os.setgid(65534)
                os.setuid(65534)
                probe = requests/'different-uid-write.json'
                probe.write_text('{"ok":true}\n', encoding='utf-8')
                ok = probe.read_text(encoding='utf-8') == '{"ok":true}\n'
                os._exit(0 if ok else 2)
            except BaseException:
                os._exit(3)
        _pid, status_code = os.waitpid(pid, 0)
        assert os.WIFEXITED(status_code)
        assert os.WEXITSTATUS(status_code) == 0



def test_32443_cr_hotfix_reports_every_postcheck_predicate(tmp_path):
    import cr_standard_native_mcp_hotfix as hotfix

    # The release artifact intentionally does not contain the live Infra tree.
    # Exercise the postcheck against an isolated canonical native-MCP fixture.
    fixture = tmp_path/'project'
    payloads = {
        hotfix.TARGETS[0]: '''RETENTION_DEFAULT = 1\ndef a(retention: int = 1,): pass\ndef b(retention: int = 1,): pass\nbase_stem = f"{_local_file_stamp()} {version} {CRASH_NAME_SUFFIX}"\nCRRetentionQuarantine\nretention_delete_performed\n''',
        hotfix.TARGETS[1]: 'from pathlib import Path\n',
        hotfix.TARGETS[2]: '${VERSION} CR NAS Containers\nNAS_CR_RETENTION_MAX1_OK\n',
        hotfix.TARGETS[3]: 'NAS_CR_RETENTION_MAX1_OK\nCRRetentionQuarantine\ndelete_performed=false\n',
        hotfix.TARGETS[4]: 'retention=1,\nlist_crash_recovery_backups(recovery)["count"], 1\n',
    }
    for rel, text in payloads.items():
        path = fixture/rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
    predicates = hotfix._contract_predicates(fixture)
    expected = {
        'project_retention_max1', 'project_runtime_version_in_name', 'project_quarantine_first',
        'nas_runtime_version_in_name', 'nas_retention_max1_marker', 'nas_quarantine_first',
        'native_runtime_legacy_writer_absent', 'native_test_retention_max1',
    }
    assert expected <= set(predicates)
    assert all(predicates[name] for name in expected)

    # Failure injection proves evidence identifies the exact broken predicate.
    (fixture/hotfix.TARGETS[1]).write_text('energie_native_mcp_runtime_v1\nInbox/native_mcp_runtime/runtime_fingerprint.json\n', encoding='utf-8')
    broken = hotfix._contract_predicates(fixture)
    assert broken['native_runtime_legacy_writer_absent'] is False
    assert all(broken[name] for name in expected - {'native_runtime_legacy_writer_absent'})



def test_32443_health_surfaces_are_explicitly_scoped():
    main = (APP/'main.py').read_text(encoding='utf-8')
    web = (PM/'projectmanager_web.py').read_text(encoding='utf-8')
    assert '"scope": "workflow"' in main
    assert '"label": "Workflowgezondheid"' in main
    assert 'Projectmanager — systeem- en releasegezondheid' in web


def test_32443_release_identity_target_after_implementation():
    # Historical closure test follows the current candidate identity.
    assert (ROOT/'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.49'
    assert 'version: "32.4.49"' in (ROOT/'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.4.49"' in (APP/'main.py').read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.4.49"' in (APP/'mode_entrypoint.py').read_text(encoding='utf-8')


def _runtime_for_32443_closure(tmp_path):
    from types import SimpleNamespace
    from command_store import CommandStore
    from orchestrator import ProjectmanagerRuntime

    project = tmp_path/'project'
    (project/'App').mkdir(parents=True)
    (project/'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')
    runtime = ProjectmanagerRuntime.__new__(ProjectmanagerRuntime)
    runtime.config = SimpleNamespace(project_root=str(project))
    runtime.root = project/'Inbox/projectmanager_v2/RuntimeV2'
    runtime.root.mkdir(parents=True)
    runtime.commands = CommandStore(runtime.root/'commands/queue.json')
    class Roadmap:
        def mark_acceptance(self, *a, **k): return None
        def mark_done_by_key(self, *a, **k): return None
    runtime.roadmap = Roadmap()
    class Issues:
        def open(self, *a, **k): return None
    runtime.base = SimpleNamespace(issues=Issues())
    return runtime, project


def test_32443_project_close_requested_only_after_pm_technical_green(tmp_path):
    runtime, project = _runtime_for_32443_closure(tmp_path)
    status = {'release': {'version':'32.4.43'}, 'health': {'checks': [
        {'name':'watcher_container_contract','status':'GREEN'},
        {'name':'native_mcp_runtime','status':'GREEN'},
        {'name':'project_crash_recovery_set','status':'ORANGE'},
        {'name':'nas_container_crash_recovery_retention','status':'ORANGE'},
        {'name':'project_structure_hygiene','status':'ORANGE'},
    ]}}
    closure = runtime._reconcile_324_live_closure(status)
    state = json.loads((project/'Inbox/projectmanager_v2/RuntimeV2/state/project_close.json').read_text())
    assert state['state'] == 'REQUESTED'
    assert state['release_version'] == '32.4.43'
    assert closure['project_close_deferred'] is False
    assert closure['next_action'] == 'CREATE_PROJECT_CR'
    queued = runtime.commands.all()
    assert [(item['intent'], item['release_version']) for item in queued] == [('project_cr_create','32.4.43')]


def test_32443_project_close_deferred_while_pm_technical_red(tmp_path):
    runtime, project = _runtime_for_32443_closure(tmp_path)
    status = {'release': {'version':'32.4.43'}, 'health': {'checks': [
        {'name':'watcher_container_contract','status':'GREEN'},
        {'name':'native_mcp_runtime','status':'RED'},
        {'name':'project_crash_recovery_set','status':'ORANGE'},
        {'name':'nas_container_crash_recovery_retention','status':'ORANGE'},
        {'name':'project_structure_hygiene','status':'ORANGE'},
    ]}}
    closure = runtime._reconcile_324_live_closure(status)
    state = json.loads((project/'Inbox/projectmanager_v2/RuntimeV2/state/project_close.json').read_text())
    assert state['state'] == 'DEFERRED'
    assert closure['project_close_deferred'] is True
    assert closure['next_action'] == 'REQUEST_NATIVE_MCP_RELOAD'
    assert all(item['intent'] not in {'project_cr_create','nas_container_cr_create'} for item in runtime.commands.all())


def test_32443_refresh_coordination_preserves_final_generation_in_handover(tmp_path):
    from types import SimpleNamespace
    from command_store import CommandStore
    from orchestrator import ProjectmanagerRuntime

    runtime = ProjectmanagerRuntime.__new__(ProjectmanagerRuntime)
    runtime.root = tmp_path/'RuntimeV2'; runtime.root.mkdir(parents=True)
    runtime.commands = CommandStore(runtime.root/'commands/queue.json')
    runtime.approved_actions = SimpleNamespace(open_items=lambda: [])
    runtime.handoffs = SimpleNamespace(open_items=lambda: [])
    runtime.roadmap = SimpleNamespace(canonical_metadata=lambda: {}, acceptance_summary=lambda: {})
    runtime.conversation_intake = SimpleNamespace(summary=lambda: {})
    runtime.base = SimpleNamespace(
        mode=SimpleNamespace(get=lambda: {'mode':'DEVELOPMENT'}),
        tasks=SimpleNamespace(active=lambda: None),
        decisions=SimpleNamespace(pending=lambda: []),
        issues=SimpleNamespace(open_items=lambda: []),
    )
    status = {
        'schema':'energie_projectmanager_status_v2',
        'updated_at':datetime.now(timezone.utc).isoformat(),
        'mode':'DEVELOPMENT',
        'release':{'version':'32.4.43'},
        'health':{'status':'GREEN','checks':[]},
        'cycle_generation':'gen-final',
        'provenance':{'generation':'gen-final','phase':'FINAL'},
        'manager':{'version':'2.0.0-rc30'},
    }
    runtime._refresh_coordination(status)
    handover = json.loads((runtime.root/'handover/current.json').read_text())
    written_status = json.loads((runtime.root/'status/current.json').read_text())
    assert handover['cycle_generation'] == written_status['cycle_generation'] == 'gen-final'
    assert handover['provenance'] == written_status['provenance'] == {'generation':'gen-final','phase':'FINAL'}
    assert written_status['development_context']['runtime_truth_primary'] is True


def test_32443_embedded_base_cycle_does_not_publish_partial_current_truth(tmp_path, monkeypatch):
    """Canonical current files stay on the previous FINAL generation until orchestrator finalizes."""
    from manager_config import ManagerConfig
    from manager_service import ManagerService

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')
    reports = tmp_path / 'reports'
    reports.mkdir()

    class Runtime:
        def collect(self):
            return {
                'release': {
                    'version': '32.4.43', 'ha_runtime_version': '32.4.43',
                    'nas_version': '32.4.43', 'active_verified': True,
                },
                'release_chain': {},
                'operating_mode': {'effective_mode': 'DEVELOPMENT'},
            }

    class Health:
        def collect(self, *, now=None): return []

    config = ManagerConfig(
        project_root=str(project), system_root=str(tmp_path / 'RuntimeV2'),
        input_root=str(tmp_path / 'input'), recovery_root=str(tmp_path / 'recovery'),
        reports_root=str(reports), interval_seconds=300, timezone='Europe/Amsterdam',
        ha_base_url='', ha_token='', ha_notify_service='', market_enabled=False,
        running_release_version='32.4.43',
    )
    service = ManagerService(config, runtime_collector=Runtime(), health_collector=Health())
    service.defer_current_publication = True
    monkeypatch.setattr(service, '_sync_documents_best_effort', lambda _status: {'status':'GREEN','results':[],'errors':[]})
    monkeypatch.setattr(service, '_reconcile_document_truth', lambda _status: {
        'strategy':'runtime_first','unresolved_stale_current_claims':[],
        'superseded_stale_current_claims':[], 'provenance':{}, 'status':'GREEN',
    })

    sentinels = {
        'status/current.json': {'sentinel':'previous-final-status'},
        'heartbeat/manager.json': {'sentinel':'previous-final-heartbeat'},
        'handover/current.json': {'sentinel':'previous-final-handover'},
        'self_audit/current.json': {'sentinel':'previous-final-audit'},
    }
    for rel, payload in sentinels.items():
        _write(Path(config.system_root) / rel, payload)

    result = service.run_once(now=datetime(2026, 9, 12, 12, 0, tzinfo=timezone.utc))
    assert result['release']['version'] == '32.4.43'
    for rel, payload in sentinels.items():
        assert json.loads((Path(config.system_root) / rel).read_text(encoding='utf-8')) == payload


def test_32443_orchestrator_enables_deferred_current_publication_for_base_cycle():
    source = (PM / 'orchestrator.py').read_text(encoding='utf-8')
    assert 'defer_current_publication' in source
    assert 'self.base.run_once(now=now)' in source


def test_32443_failed_or_cancelled_current_release_action_is_not_tight_loop_requeued(tmp_path):
    runtime, _project = _runtime_for_32443_closure(tmp_path)
    failed = runtime.commands.enqueue({
        'intent':'project_cr_create','release_version':'32.4.43','source':'projectmanager_auto'
    })
    runtime.commands.fail(failed['id'], error='simulated failure')
    result = runtime._queue_324_action_once('project_cr_create', '32.4.43')
    assert result['status'] == 'previous_terminal_block'
    assert result['previous_status'] == 'FAILED'
    assert len([item for item in runtime.commands.all() if item.get('intent') == 'project_cr_create']) == 1

    cancelled = runtime.commands.enqueue({
        'intent':'native_mcp_reload','release_version':'32.4.43','source':'projectmanager_auto'
    })
    runtime.commands.cancel(cancelled['id'], reason='Peter rejected')
    result2 = runtime._queue_324_action_once('native_mcp_reload', '32.4.43')
    assert result2['status'] == 'previous_terminal_block'
    assert result2['previous_status'] == 'CANCELLED'
    assert len([item for item in runtime.commands.all() if item.get('intent') == 'native_mcp_reload']) == 1


def test_32443_self_audit_accepts_current_development_build_contract_v3(tmp_path):
    from development_build_contract import evaluate_build_contract, CONTRACT_VERSION
    from self_audit import SelfAuditor

    _minimal_self_audit_runtime(tmp_path, 'gen-contract')
    task = {
        'id':'build-current','status':'ACTIVE','step':1,'steps_total':1,
        'build_contract_required':True,
        'build_metadata': {
            'thinking_level':'HOOG','release_version':'32.4.43',
            'estimated_total_seconds':600,'estimated_test_verification_seconds':300,
            'step_estimates_seconds':[600],
            'original_estimate_recorded_at':'2026-09-12T12:00:00+00:00',
        },
    }
    status_path = tmp_path/'status/current.json'
    status = json.loads(status_path.read_text(encoding='utf-8'))
    status['active_task'] = task
    status['development_build_contract'] = evaluate_build_contract(task, {})
    _write(status_path, status)
    handover_path = tmp_path/'handover/current.json'
    handover = json.loads(handover_path.read_text(encoding='utf-8'))
    handover['active_task'] = {key:task[key] for key in ('id','status','step','steps_total')}
    _write(handover_path, handover)

    audit = SelfAuditor(tmp_path, running_release_version='32.4.43').run(require_coordination=True)
    assert CONTRACT_VERSION == '2026-09-11.v3'
    assert audit['status'] == 'GREEN', audit


def _load_tool_module(name, filename):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_32443_project_cr_executor_red_result_preserves_command_id(tmp_path):
    tool = _load_tool_module('project_cr_local_executor_32443', 'project_cr_local_executor.py')
    root = tmp_path / 'project'
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')
    bridge = root / 'Inbox/project_cr_local'
    bridge.mkdir(parents=True)
    request_id, command_id = '1' * 32, '2' * 32
    _write(bridge / 'request.json', {
        'schema': tool.REQUEST_SCHEMA,
        'request_id': request_id,
        'command_id': command_id,
        'operation': tool.OPERATION,
        'expected_runtime_version': '32.4.42',
        'created_at': '2026-09-12T12:00:00+00:00',
    })
    with pytest.raises(RuntimeError, match='runtimeversie gewijzigd'):
        tool.execute(root)
    result = json.loads((bridge / 'result.json').read_text(encoding='utf-8'))
    assert result['request_id'] == request_id
    assert result['command_id'] == command_id
    assert 'runtimeversie gewijzigd' in result['error']


def test_32443_nas_cr_executor_red_result_preserves_command_id(tmp_path):
    tool = _load_tool_module('nas_cr_local_executor_32443', 'nas_cr_local_executor.py')
    root = tmp_path / 'project'
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')
    bridge = root / 'Inbox/nas_container_cr_local'
    bridge.mkdir(parents=True)
    request_id, command_id = '3' * 32, '4' * 32
    _write(bridge / 'request.json', {
        'schema': tool.REQUEST_SCHEMA,
        'request_id': request_id,
        'command_id': command_id,
        'operation': tool.OPERATION,
        'expected_runtime_version': '32.4.42',
        'created_at': '2026-09-12T12:00:00+00:00',
    })
    with pytest.raises(RuntimeError, match='release mismatch'):
        tool.execute(root)
    result = json.loads((bridge / 'result.json').read_text(encoding='utf-8'))
    assert result['request_id'] == request_id
    assert result['command_id'] == command_id
    assert 'release mismatch' in result['error']


@pytest.mark.parametrize('intent', ['project_cr_create', 'nas_container_cr_create'])
@pytest.mark.parametrize('close_state', ['missing', 'DEFERRED', 'stale', 'REQUESTED'])
def test_32443_queued_cr_rechecks_project_close_before_side_effects(tmp_path, intent, close_state):
    from command_processor import CommandProcessor
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from project_close_state import write_project_close
    from task_engine import TaskStore

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.43\n', encoding='utf-8')
    if close_state != 'missing':
        write_project_close(
            project,
            release_version='32.4.42' if close_state == 'stale' else '32.4.43',
            state='REQUESTED' if close_state == 'stale' else close_state,
            reason='execution-boundary failure injection',
        )

    marker = project / 'cr_side_effect'

    class CR:
        def create(self, **kwargs):
            marker.write_text('CR started\n', encoding='utf-8')
            return {'ok': True, 'status': 'GREEN', 'deep_verified': True,
                    'production_containers_changed': False}

    class Mode:
        def set(self, *args, **kwargs): return None

    commands = CommandStore(tmp_path / 'commands.json')
    command = commands.enqueue({'intent': intent, 'release_version': '32.4.43'})
    processor = CommandProcessor(
        commands, DecisionQueue(tmp_path / 'decisions.json'), Mode(),
        TaskStore(tmp_path / 'tasks.json'), project_cr_service=CR(),
        nas_container_cr_service=CR(), project_root=project,
    )
    result = processor.process_next()
    assert result['id'] == command['id']
    if close_state == 'REQUESTED':
        assert result['status'] == 'DONE'
        assert marker.read_text(encoding='utf-8') == 'CR started\n'
    else:
        assert not marker.exists(), 'CR side effect executed while project close was deferred'
        assert result['status'] == 'FAILED'
        assert 'project_close_deferred' in result['error']
