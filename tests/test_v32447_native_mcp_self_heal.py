import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _setup_release(project: Path, *, release='32.4.47', guard_status='RELOAD_REQUIRED'):
    (project / 'App').mkdir(parents=True, exist_ok=True)
    (project / 'App/VERSIE.txt').write_text(release + '\n', encoding='utf-8')
    _write_json(project / 'Inbox/atomic_app_swap_state.json', {
        'state': 'ACCEPTED', 'to_version': release, 'artifact_sha256': 'a' * 64,
    })
    _write_json(project / 'Inbox/operating_mode/release_validation_hold.json', {
        'active': False, 'release_version': release, 'validation_status': 'ok',
    })
    expected = 'b' * 64
    _write_json(project / 'Inbox/native_mcp_runtime/runtime_guard.json', {
        'status': guard_status,
        'ready': guard_status == 'GREEN',
        'reload_required': guard_status != 'GREEN',
        'expected_fingerprint': expected,
        'runtime_fingerprint': expected if guard_status == 'GREEN' else 'c' * 64,
    })
    _write_json(project / 'Data/03_Systeem/Projectmanager/Policies/native_mcp_self_heal_policy.json', {
        'schema': 'energie_native_mcp_self_heal_policy_v1',
        'enabled': True,
        'approved_by': 'Peter',
        'scope': 'release_bound_native_mcp_self_reload_after_accepted_release',
    })


def test_32447_standing_policy_auto_approves_only_exact_current_native_mcp_self_heal(tmp_path):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from native_mcp_self_heal import NativeMcpSelfHealAuthorizer

    project = tmp_path / 'project'
    _setup_release(project)
    runtime = project / 'Inbox/projectmanager_v2/RuntimeV2'
    commands = CommandStore(runtime / 'commands/queue.json')
    decisions = DecisionQueue(runtime / 'decisions/queue.json')

    command = commands.enqueue({
        'intent': 'native_mcp_reload', 'source': 'projectmanager_auto',
        'release_version': '32.4.47', 'title': 'exact self heal',
    })
    decision = decisions.request(
        'PRODUCTION_RESTART', 'reload exact native mcp',
        fingerprint=f"command:{command['id']}:PRODUCTION_RESTART",
        context={
            'command_id': command['id'], 'intent': 'native_mcp_reload',
            'release_version': '32.4.47', 'source': 'projectmanager_auto',
        },
    )
    commands.wait_for_approval(command['id'], decision_id=decision['id'])

    result = NativeMcpSelfHealAuthorizer(project, commands, decisions).run_once()

    assert result['status'] == 'APPROVED'
    assert result['decision_id'] == decision['id']
    assert decisions.get(decision['id'])['status'] == 'APPROVED'
    assert decisions.get(decision['id'])['approved_by'] == 'Peter'
    assert commands.get(command['id'])['status'] == 'APPROVED_READY'


def test_32447_self_heal_policy_fails_closed_until_release_is_accepted(tmp_path):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from native_mcp_self_heal import NativeMcpSelfHealAuthorizer

    project = tmp_path / 'project'
    _setup_release(project)
    _write_json(project / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'to_version': '32.4.47', 'artifact_sha256': 'a' * 64,
    })
    runtime = project / 'Inbox/projectmanager_v2/RuntimeV2'
    commands = CommandStore(runtime / 'commands/queue.json')
    decisions = DecisionQueue(runtime / 'decisions/queue.json')
    command = commands.enqueue({
        'intent': 'native_mcp_reload', 'source': 'projectmanager_auto', 'release_version': '32.4.47',
    })
    decision = decisions.request('PRODUCTION_RESTART', 'reload', context={
        'command_id': command['id'], 'intent': 'native_mcp_reload', 'release_version': '32.4.47',
    })
    commands.wait_for_approval(command['id'], decision_id=decision['id'])

    result = NativeMcpSelfHealAuthorizer(project, commands, decisions).run_once()

    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'release_not_accepted'
    assert decisions.get(decision['id'])['status'] == 'PENDING'
    assert commands.get(command['id'])['status'] == 'WAITING_APPROVAL'


def test_32447_self_heal_policy_never_auto_approves_generic_restart_or_remote_command(tmp_path):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from native_mcp_self_heal import NativeMcpSelfHealAuthorizer

    project = tmp_path / 'project'
    _setup_release(project)
    runtime = project / 'Inbox/projectmanager_v2/RuntimeV2'
    commands = CommandStore(runtime / 'commands/queue.json')
    decisions = DecisionQueue(runtime / 'decisions/queue.json')

    command = commands.enqueue({
        'intent': 'native_mcp_reload', 'source': 'mcp_remote', 'release_version': '32.4.47',
    })
    decision = decisions.request('PRODUCTION_RESTART', 'remote reload', context={
        'command_id': command['id'], 'intent': 'native_mcp_reload', 'release_version': '32.4.47',
    })
    commands.wait_for_approval(command['id'], decision_id=decision['id'])

    result = NativeMcpSelfHealAuthorizer(project, commands, decisions).run_once()

    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'no_exact_auto_self_heal_candidate'
    assert decisions.get(decision['id'])['status'] == 'PENDING'


def test_32447_policy_disabled_keeps_gui_approval_path_fail_closed(tmp_path):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from native_mcp_self_heal import NativeMcpSelfHealAuthorizer

    project = tmp_path / 'project'
    _setup_release(project)
    _write_json(project / 'Data/03_Systeem/Projectmanager/Policies/native_mcp_self_heal_policy.json', {
        'schema': 'energie_native_mcp_self_heal_policy_v1',
        'enabled': False,
        'approved_by': 'Peter',
        'scope': 'release_bound_native_mcp_self_reload_after_accepted_release',
    })
    runtime = project / 'Inbox/projectmanager_v2/RuntimeV2'
    commands = CommandStore(runtime / 'commands/queue.json')
    decisions = DecisionQueue(runtime / 'decisions/queue.json')

    command = commands.enqueue({'intent': 'native_mcp_reload', 'source': 'projectmanager_auto', 'release_version': '32.4.47'})
    decision = decisions.request('PRODUCTION_RESTART', 'reload', context={
        'command_id': command['id'], 'intent': 'native_mcp_reload', 'release_version': '32.4.47',
    })
    commands.wait_for_approval(command['id'], decision_id=decision['id'])

    result = NativeMcpSelfHealAuthorizer(project, commands, decisions).run_once()
    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'standing_policy_not_enabled'
    assert decisions.get(decision['id'])['status'] == 'PENDING'


def test_32447_runtime_invokes_self_heal_authorizer_before_command_processor():
    source = (PM / 'orchestrator.py').read_text(encoding='utf-8')
    assert 'from native_mcp_self_heal import NativeMcpSelfHealAuthorizer' in source
    assert 'self.native_mcp_self_heal = NativeMcpSelfHealAuthorizer(' in source
    approval_pos = source.index('self_heal_authorization = self.native_mcp_self_heal.run_once()')
    processor_pos = source.index('processed = self.processor.process_all(max_items=50)')
    assert approval_pos < processor_pos
    assert "status['native_mcp_self_heal_authorization'] = self_heal_authorization" in source
