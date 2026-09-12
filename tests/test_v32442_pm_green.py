
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
TOOLS = ROOT / "tools"
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

from approved_action_store import ApprovedActionStore
from command_store import CommandStore
from conversation_approval import ConversationApprovalCoordinator
from decision_queue import DecisionQueue
from handover_snapshot import HandoverSnapshotService
from protected_action_executor import ProtectedActionExecutor
from series_324_live_closure import evaluate, next_action
from state_reconciliation import StateReconciler
from task_engine import TaskStore


def _write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class _EmptyStore:
    def all(self): return []
    def open_items(self): return []


def test_32442_contract_bakes_in_exact_previous_zip_rule():
    from development_build_contract import canonical_contract
    rules = canonical_contract()["process_rules"]
    assert "exact_previous_verified_zip_required" in rules
    assert "ask_peter_for_exact_zip_if_unavailable" in rules
    assert "no_github_or_reconstruction_as_build_basis" in rules


def test_32442_pm_technical_green_is_separate_from_deferred_project_close():
    checks = [
        {"name": "watcher_container_contract", "status": "GREEN"},
        {"name": "native_mcp_runtime", "status": "GREEN"},
        {"name": "project_crash_recovery_set", "status": "ORANGE"},
        {"name": "nas_container_crash_recovery_retention", "status": "ORANGE"},
        {"name": "project_structure_hygiene", "status": "ORANGE"},
    ]
    result = evaluate(checks, clearup={}, release_version="32.4.42")
    assert result["pm_status"] == "GREEN"
    assert result["project_close_status"] == "RED"
    assert result["status"] == "RED"
    by_name = {item["name"]: item["status"] for item in checks}
    assert next_action(by_name, clearup_done=False, project_close_deferred=True) == "DEFER_PROJECT_CLOSE"


def test_32442_pending_count_includes_interrupted_same_as_self_audit(tmp_path):
    store = CommandStore(tmp_path / "commands.json")
    item = store.enqueue({"intent": "status_query"})
    claimed = store.claim_next()
    assert claimed["id"] == item["id"]
    store.recover_interrupted()
    assert store.get(item["id"])["status"] == "INTERRUPTED"
    assert store.pending_count() == 1


def test_32442_narrow_legacy_release_ingress_task_is_superseded_from_runtime(tmp_path):
    tasks = TaskStore(tmp_path / "tasks.json")
    task = tasks.start(
        "32.4.41 release-ingress hervatten",
        "Release-ingress hervatten nadat 32.4.41 reeds live staat",
        mode="DEVELOPMENT",
        steps_total=1,
    )
    reconciler = StateReconciler(tasks, _EmptyStore(), _EmptyStore(), None, None)
    runtime = {
        "release": {"version": "32.4.41", "source": "/project/App/VERSIE.txt"},
        "release_chain": {
            "atomic_swap": {
                "state": "LIVE_ACCEPTANCE",
                "source": "/project/Inbox/atomic_app_swap_state.json",
                "raw": {"to_version": "32.4.41"},
            }
        },
    }
    result = reconciler.reconcile(runtime=runtime)
    assert result["changed_count"] == 1
    assert tasks.get(task["id"])["status"] == "SUPERSEDED"


def test_32442_native_reload_rejects_stale_release_before_request(tmp_path):
    project = tmp_path / "project"
    (project / "App").mkdir(parents=True)
    (project / "App/VERSIE.txt").write_text("32.4.42\n", encoding="utf-8")
    _write(project / "Inbox/native_mcp_runtime/runtime_guard.json", {
        "status": "RELOAD_REQUIRED",
        "ready": False,
        "reload_required": True,
        "expected_fingerprint": "a" * 64,
        "runtime_fingerprint": "b" * 64,
    })
    approved = ApprovedActionStore(tmp_path / "approved.json")
    commands = CommandStore(tmp_path / "commands.json")
    decisions = DecisionQueue(tmp_path / "decisions.json")
    command = commands.enqueue({
        "intent": "native_mcp_reload",
        "release_version": "32.4.41",
        "source": "projectmanager_auto",
    })
    decision = decisions.request(
        "PRODUCTION_RESTART",
        "reload?",
        fingerprint="reload-old",
        context={"command_id": command["id"], "intent": "native_mcp_reload", "release_version": "32.4.41"},
    )
    decision = decisions.resolve(decision["id"], approved=True, approved_by="Peter")
    commands.wait_for_approval(command["id"], decision_id=decision["id"])
    commands.mark_approved_ready(command["id"])
    command = commands.wait_for_executor(command["id"], approved_action={"id": "x"}, result={})
    action = approved.add(decision=decision, command=command, action="native_mcp_reload")

    executor = ProtectedActionExecutor(project, approved, commands, decisions)
    with pytest.raises(RuntimeError, match="actuele release"):
        executor._queue_native_mcp_reload(action, command, decision)
    assert not (project / "Inbox/control_plane/requests/native_mcp_reload.json").exists()


def test_32442_native_reload_request_binds_release_command_and_decision(tmp_path):
    project = tmp_path / "project"
    (project / "App").mkdir(parents=True)
    (project / "App/VERSIE.txt").write_text("32.4.42\n", encoding="utf-8")
    _write(project / "Inbox/native_mcp_runtime/runtime_guard.json", {
        "status": "RELOAD_REQUIRED",
        "ready": False,
        "reload_required": True,
        "expected_fingerprint": "a" * 64,
        "runtime_fingerprint": "b" * 64,
    })
    approved = ApprovedActionStore(tmp_path / "approved.json")
    commands = CommandStore(tmp_path / "commands.json")
    decisions = DecisionQueue(tmp_path / "decisions.json")
    command = commands.enqueue({
        "intent": "native_mcp_reload",
        "release_version": "32.4.42",
        "source": "projectmanager_auto",
    })
    decision = decisions.request(
        "PRODUCTION_RESTART",
        "reload?",
        fingerprint="reload-current",
        context={"command_id": command["id"], "intent": "native_mcp_reload", "release_version": "32.4.42"},
    )
    decision = decisions.resolve(decision["id"], approved=True, approved_by="Peter")
    command = commands.wait_for_approval(command["id"], decision_id=decision["id"])
    command = commands.mark_approved_ready(command["id"])
    command = commands.wait_for_executor(command["id"], approved_action={"id": "x"}, result={})
    action = approved.add(decision=decision, command=command, action="native_mcp_reload")

    executor = ProtectedActionExecutor(project, approved, commands, decisions)
    result = executor._queue_native_mcp_reload(action, command, decision)
    assert result["restart_queued"] is True
    payload = json.loads((project / "Inbox/control_plane/requests/native_mcp_reload.json").read_text())
    assert payload["release_version"] == "32.4.42"
    assert payload["command_id"] == command["id"]
    assert payload["decision_id"] == decision["id"]


def test_32442_plain_ja_and_akkoord_confirm_exact_existing_pending_decision(tmp_path):
    decisions = DecisionQueue(tmp_path / "decisions.json")
    commands = CommandStore(tmp_path / "commands.json")
    command = commands.enqueue({
        "intent": "native_mcp_reload",
        "release_version": "32.4.42",
        "source": "projectmanager_auto",
    })
    decision = decisions.request(
        "PRODUCTION_RESTART",
        "Native MCP opnieuw laden?",
        fingerprint="native-existing",
        context={"command_id": command["id"], "intent": "native_mcp_reload", "release_version": "32.4.42"},
    )
    command = commands.wait_for_approval(command["id"], decision_id=decision["id"])
    coordinator = ConversationApprovalCoordinator(
        tmp_path / "challenges.json", decisions, commands=commands
    )
    before = len(decisions.all())
    challenge = coordinator.request(
        action="native_mcp_reload",
        parameters={"version": "32.4.42", "target": "energie-filesystem-mcp"},
        source_channel="voice",
    )["challenge"]
    assert challenge["decision_id"] == decision["id"]
    assert challenge["command_id"] == command["id"]
    assert len(decisions.all()) == before
    assert coordinator.confirm(challenge["id"], "ja", source_channel="voice")["status"] == "approved"

    # A second independent challenge proves the other short token as well.
    command2 = commands.enqueue({
        "intent": "native_mcp_reload",
        "release_version": "32.4.42",
        "source": "projectmanager_auto",
        "ingress_id": "native-2",
    })
    decision2 = decisions.request(
        "PRODUCTION_RESTART",
        "Native MCP opnieuw laden 2?",
        fingerprint="native-existing-2",
        context={"command_id": command2["id"], "intent": "native_mcp_reload", "release_version": "32.4.42"},
    )
    commands.wait_for_approval(command2["id"], decision_id=decision2["id"])
    challenge2 = coordinator.request(
        action="native_mcp_reload",
        parameters={"version": "32.4.42", "target": "energie-filesystem-mcp"},
        source_channel="chatgpt",
    )["challenge"]
    assert coordinator.confirm(challenge2["id"], "akkoord", source_channel="chatgpt")["status"] == "approved"


def test_32442_plain_yes_is_only_followup_when_exactly_one_pending_challenge(tmp_path):
    decisions = DecisionQueue(tmp_path / "decisions.json")
    coordinator = ConversationApprovalCoordinator(tmp_path / "challenges.json", decisions)
    assert coordinator.handles_followup("ja") is False
    coordinator.request(
        action="production_deploy",
        parameters={"version": "32.4.42", "target": "Home Assistant"},
        source_channel="chatgpt",
    )
    assert coordinator.handles_followup("ja") is True
    assert coordinator.handles_followup("akkoord") is True


def test_32442_handover_carries_development_context_contract_and_true_percentage(tmp_path):
    project = tmp_path / "project"
    runtime = tmp_path / "runtime"
    (project / "App").mkdir(parents=True)
    (project / "App/VERSIE.txt").write_text("32.4.42\n", encoding="utf-8")
    pm_version = project / "App/slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt"
    pm_version.parent.mkdir(parents=True)
    pm_version.write_text("2.0.0-rc29\n", encoding="utf-8")
    _write(runtime / "status/current.json", {
        "schema": "energie_projectmanager_status_v2",
        "mode": "DEVELOPMENT",
        "release": {"version": "32.4.42"},
        "release_chain": {"atomic_swap": {"state": "LIVE_ACCEPTANCE"}},
        "progress": {
            "step": 2,
            "steps_total": 6,
            "step_label": "Stap 2/6",
            "progress_percent": 16.7,
            "next_action": "repareren",
        },
        "active_task": {"id": "t1", "status": "ACTIVE", "step": 2, "steps_total": 6},
        "next_action": "repareren",
        "decisions_needed": [],
        "development_context": {
            "active_context": "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_ACTIVE_DEVELOPMENT_CONTEXT.md",
            "manifest": "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_DEVELOPMENT_MANIFEST.md",
            "ledger": "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/01_UNIFIED_DEVELOPMENT_LEDGER.md",
            "live_handover_primary": True,
        },
        "development_build_contract": {
            "contract_version": "2026-09-11.v3",
            "process_rules": ["exact_previous_verified_zip_required"],
        },
    })
    service = HandoverSnapshotService(runtime, project_root=project)
    snap = service.create(source_channel="chatgpt", trigger_text="nieuwe chat", trigger_id="x")
    assert snap["development_context"]["live_handover_primary"] is True
    assert snap["development_context"]["ledger"].endswith("01_UNIFIED_DEVELOPMENT_LEDGER.md")
    assert snap["development_build_contract"]["process_rules"] == ["exact_previous_verified_zip_required"]
    markdown = (runtime / "handover/ready/current.md").read_text(encoding="utf-8")
    assert "(16.7%)" in markdown


def test_32442_orchestrator_routes_plain_followup_and_defers_cr_auto_queue():
    source = (PM / "orchestrator.py").read_text(encoding="utf-8")
    assert "self.conversation.handles_followup(text)" in source
    assert "project_close_deferred=True" in source
    assert "_queue_324_action_once('project_cr_create'" not in source
    assert "_queue_324_action_once('nas_container_cr_create'" not in source


def test_32442_native_hotfix_replaces_older_approval_tool_instead_of_accepting_presence():
    source = (TOOLS / "native_mcp_runtime_contract_hotfix.py").read_text(encoding="utf-8")
    assert "PM_APPROVAL_TOOL_VERSION=2026-09-12.v3" in source
    assert "approval_tool_upgraded" in source


def test_32442_release_identity():
    import release_test_contract as contract
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == contract.CURRENT_RELEASE
    assert (PM / "VERSION.txt").read_text(encoding="utf-8").strip() == contract.CURRENT_PM_VERSION
    assert f'version: "{contract.CURRENT_RELEASE}"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert f'APP_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / "main.py").read_text(encoding="utf-8")
    assert f'TARGET_RELEASE_VERSION = "{contract.CURRENT_RELEASE}"' in (APP / "mode_entrypoint.py").read_text(encoding="utf-8")


def test_32442_incoming_single_release_autoroutes_existing_mode_to_development():
    from orchestrator import ProjectmanagerRuntime

    class Bridge:
        def __init__(self):
            self.calls = []
        def request_base_mode(self, mode, *, reason='', issued_by='', confirmed_by_user=False):
            row = {
                'requested_mode': mode,
                'reason': reason,
                'issued_by': issued_by,
                'confirmed_by_user': confirmed_by_user,
            }
            self.calls.append(row)
            return row

    runtime = ProjectmanagerRuntime.__new__(ProjectmanagerRuntime)
    runtime.mode_bridge = Bridge()
    result = runtime._auto_route_release_ingress({
        'operating_mode': {'effective_mode': 'MAINTENANCE'},
        'release_chain': {
            'incoming': {'count': 1, 'files': [{'name': 'EnergieProject_v32.4.42.zip'}]},
            'processing': {'count': 0, 'files': []},
        },
    })
    assert result['status'] == 'REQUESTED'
    assert result['requested_mode'] == 'DEVELOPMENT'
    assert runtime.mode_bridge.calls == [{
        'requested_mode': 'DEVELOPMENT',
        'reason': 'exactly one release ZIP waiting in Incoming',
        'issued_by': 'projectmanager',
        'confirmed_by_user': False,
    }]


def test_32442_incoming_autoroute_is_fail_closed_for_ambiguous_or_already_development():
    from orchestrator import ProjectmanagerRuntime

    class Bridge:
        def __init__(self): self.calls = []
        def request_base_mode(self, *args, **kwargs):
            self.calls.append((args, kwargs))
            return {}

    runtime = ProjectmanagerRuntime.__new__(ProjectmanagerRuntime)
    runtime.mode_bridge = Bridge()
    ambiguous = runtime._auto_route_release_ingress({
        'operating_mode': {'effective_mode': 'MAINTENANCE'},
        'release_chain': {'incoming': {'count': 2, 'files': [{'name': 'a.zip'}, {'name': 'b.zip'}]}},
    })
    assert ambiguous['status'] == 'BLOCKED_AMBIGUOUS'
    already = runtime._auto_route_release_ingress({
        'operating_mode': {'effective_mode': 'DEVELOPMENT'},
        'release_chain': {'incoming': {'count': 1, 'files': [{'name': 'one.zip'}]}},
    })
    assert already['status'] == 'ALREADY_DEVELOPMENT'
    assert runtime.mode_bridge.calls == []


def test_32442_approved_production_deploy_requests_existing_development_mode_before_executor(tmp_path):
    from command_processor import CommandProcessor

    class ModeStore:
        def set(self, mode, *, reason='', source=''): return {'mode': mode}
    class Bridge:
        def __init__(self): self.calls = []
        def request_base_mode(self, mode, *, reason='', issued_by='', confirmed_by_user=False):
            row = {'requested_mode': mode, 'reason': reason, 'issued_by': issued_by, 'confirmed_by_user': confirmed_by_user}
            self.calls.append(row)
            return row

    commands = CommandStore(tmp_path / 'commands.json')
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    tasks = TaskStore(tmp_path / 'tasks.json')
    approved = ApprovedActionStore(tmp_path / 'approved.json')
    bridge = Bridge()
    processor = CommandProcessor(commands, decisions, ModeStore(), tasks, mode_bridge=bridge, approved_actions=approved)
    command = commands.enqueue({
        'intent': 'production_deploy',
        'release_version': '32.4.42',
        'source': 'chatgpt',
        'text': 'Installeer 32.4.42 in Home Assistant',
    })
    waiting = processor.process_next()
    decision = decisions.resolve(waiting['approval_decision_id'], approved=True, approved_by='Peter')
    processor.resume_resolved_decisions()
    handed = processor.process_next()
    assert handed['status'] == 'APPROVED_WAITING_EXECUTOR'
    assert handed['result']['requested_mode'] == 'DEVELOPMENT'
    assert bridge.calls[-1]['requested_mode'] == 'DEVELOPMENT'
    assert bridge.calls[-1]['confirmed_by_user'] is False
    assert decision['status'] == 'APPROVED'


def test_32442_plain_verder_is_a_fresh_handover_resume_intent(tmp_path):
    from conversation_runtime import ProjectmanagerConversationRuntime

    class Intake:
        def __init__(self): self.calls = []
        def accept(self, command):
            self.calls.append(command)
            return {'status': 'accepted'}
    class Approval:
        def handles_followup(self, text): return False
        def pending(self): return []
    class Handover:
        def __init__(self): self.calls = []
        def create(self, **kwargs):
            self.calls.append(dict(kwargs))
            return {
                'handover_id': 'fresh-1', 'progress': {'step_label': 'Stap 4/6'},
                'development_context': {'ledger': '01_UNIFIED_DEVELOPMENT_LEDGER.md'},
            }

    root = tmp_path / 'runtime'
    _write(root / 'status/current.json', {
        'schema': 'energie_projectmanager_status_v2',
        'mode': 'DEVELOPMENT',
        'release': {'version': '32.4.42'},
        'release_chain': {},
        'progress': {'step_label': 'Stap 4/6'},
    })
    intake, handover = Intake(), Handover()
    runtime = ProjectmanagerConversationRuntime(root, intake=intake, approval=Approval(), handover=handover)
    assert runtime.handles('verder') is True
    result = runtime.handle(text='verder', source_channel='chatgpt', turn_id='new-chat-1', session_id='fresh-session')
    assert result['status'] == 'handover_ready'
    assert result['handover_id'] == 'fresh-1'
    assert handover.calls[-1]['trigger_id'] == 'new-chat-1'
    assert intake.calls == []


def test_32442_embedded_pm_rechecks_release_ingress_at_most_once_per_minute():
    from embedded_config import build_embedded_config
    cfg = build_embedded_config('/project', '/app/projectmanager_v2', running_release_version='32.4.42')
    assert cfg.interval_seconds == 60


def test_32442_new_chat_verder_e2e_uses_fresh_truth_not_old_ready_snapshot(tmp_path):
    from conversation_runtime import ProjectmanagerConversationRuntime

    project = tmp_path / 'project'
    runtime_root = tmp_path / 'RuntimeV2'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.42\n', encoding='utf-8')
    pmv = project / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt'
    pmv.parent.mkdir(parents=True)
    pmv.write_text('2.0.0-rc29\n', encoding='utf-8')

    base_status = {
        'schema': 'energie_projectmanager_status_v2',
        'mode': 'MAINTENANCE',
        'release': {'version': '32.4.42'},
        'release_chain': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE', 'to_version': '32.4.42'}},
        'progress': {'step': 1, 'steps_total': 6, 'step_label': 'Stap 1/6', 'progress_percent': 16.7, 'next_action': 'oud'},
        'active_task': {'id': 'old-task', 'status': 'ACTIVE', 'title': 'oude taak'},
        'next_action': 'oud',
        'decisions_needed': [],
        'development_context': {'ledger': 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/01_UNIFIED_DEVELOPMENT_LEDGER.md', 'live_handover_primary': True},
        'development_build_contract': {'contract_version': '2026-09-11.v3', 'process_rules': ['exact_previous_verified_zip_required']},
    }
    _write(runtime_root / 'status/current.json', base_status)
    _write(runtime_root / 'state/tasks.json', {'schema': 1, 'tasks': [{'id': 'old-task', 'status': 'ACTIVE', 'title': 'oude taak'}]})

    handover = HandoverSnapshotService(runtime_root, project_root=project)
    old = handover.create(source_channel='chatgpt', trigger_text='oude snapshot', trigger_id='old-turn')

    fresh_status = dict(base_status)
    fresh_status['mode'] = 'DEVELOPMENT'
    fresh_status['progress'] = {'step': 5, 'steps_total': 6, 'step_label': 'Stap 5/6', 'progress_percent': 83.3, 'next_action': 'exacte ZIP controleren'}
    fresh_status['active_task'] = {'id': 'fresh-task', 'status': 'ACTIVE', 'title': '32.4.42 eindcontrole'}
    fresh_status['next_action'] = 'exacte ZIP controleren'
    fresh_status['decisions_needed'] = [{'id': 'dec-current', 'status': 'PENDING', 'kind': 'PRODUCTION_RESTART'}]
    _write(runtime_root / 'status/current.json', fresh_status)
    _write(runtime_root / 'state/tasks.json', {'schema': 1, 'tasks': [{'id': 'fresh-task', 'status': 'ACTIVE', 'title': '32.4.42 eindcontrole'}]})

    class Intake:
        def accept(self, command):
            raise AssertionError('verder must not fall through to intake')
    class Approval:
        def handles_followup(self, text): return False

    conversation = ProjectmanagerConversationRuntime(runtime_root, intake=Intake(), approval=Approval(), handover=handover)
    result = conversation.handle(text='verder', source_channel='chatgpt', turn_id='fresh-turn', session_id='brand-new-chat')
    snap = result['snapshot']
    assert result['status'] == 'handover_ready'
    assert snap['handover_id'] != old['handover_id']
    assert snap['mode'] == 'DEVELOPMENT'
    assert snap['progress']['step_label'] == 'Stap 5/6'
    assert snap['progress']['progress_percent'] == 83.3
    assert snap['next_step'] == 'exacte ZIP controleren'
    assert snap['active_tasks'][0]['id'] == 'fresh-task'
    assert snap['open_approvals'][0]['id'] == 'dec-current'
    assert snap['development_context']['ledger'].endswith('01_UNIFIED_DEVELOPMENT_LEDGER.md')
    current = json.loads((runtime_root / 'handover/ready/current.json').read_text(encoding='utf-8'))
    assert current['handover_id'] == snap['handover_id']


def test_32442_projectmanager_persists_existing_development_ledger_paths(tmp_path):
    from manager_service import ManagerService
    from document_sync import ManagedDocumentSync

    class Config:
        project_root = str(tmp_path / 'project')

    service = ManagerService.__new__(ManagerService)
    service.config = Config()
    service.document_sync = ManagedDocumentSync()
    status = {
        'release': {'version': '32.4.42'},
        'development_build_contract': {
            'contract_version': '2026-09-11.v3',
            'process_rules': [
                'exact_previous_verified_zip_required',
                'ask_peter_for_exact_zip_if_unavailable',
                'no_github_or_reconstruction_as_build_basis',
            ],
        },
    }
    results = service._sync_development_context_documents(status)
    root = tmp_path / 'project/Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons'
    assert len(results) == 3
    assert (root / '00_ACTIVE_DEVELOPMENT_CONTEXT.md').is_file()
    assert (root / '00_DEVELOPMENT_MANIFEST.md').is_file()
    ledger = (root / '01_UNIFIED_DEVELOPMENT_LEDGER.md').read_text(encoding='utf-8')
    assert 'exact_previous_verified_zip_required' in ledger
    assert 'ask_peter_for_exact_zip_if_unavailable' in ledger
    assert 'no_github_or_reconstruction_as_build_basis' in ledger
    assert 'ZIP → Incoming/Home Assistant → watcher' in ledger
    assert 'geen nieuwe ontwikkelroute' in ledger.lower()
