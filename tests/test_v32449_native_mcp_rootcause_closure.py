import json
import sys
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _setup_live_acceptance(project: Path, *, release='32.4.49'):
    (project / 'App').mkdir(parents=True, exist_ok=True)
    (project / 'App/VERSIE.txt').write_text(release + '\n', encoding='utf-8')
    _write_json(project / 'Inbox/atomic_app_swap_state.json', {
        'state': 'LIVE_ACCEPTANCE', 'to_version': release, 'from_version': '32.4.48',
        'artifact_sha256': 'a' * 64,
    })
    _write_json(project / 'Inbox/operating_mode/release_validation_hold.json', {
        'active': True,
        'release_version': release,
        'validation_status': 'blocked',
        'reasons': ['projectmanager_self_audit'],
        'validation_checks': {
            'version': {'ok': True},
            'web_runtime': {'ok': True},
            'state_io': {'ok': True},
            'automatic_runtime_idle': {'ok': True},
            'release_chain': {'ok': True},
            'projectmanager_self_audit': {'ok': False},
            'production_certificate': {'ok': True},
        },
    })
    _write_json(project / 'Inbox/native_mcp_runtime/runtime_guard.json', {
        'status': 'RELOAD_REQUIRED', 'ready': False, 'reload_required': True,
        'expected_fingerprint': 'b' * 64, 'runtime_fingerprint': 'c' * 64,
    })
    _write_json(project / 'Data/03_Systeem/Projectmanager/Policies/native_mcp_self_heal_policy.json', {
        'schema': 'energie_native_mcp_self_heal_policy_v2',
        'enabled': True,
        'approved_by': 'Peter',
        'scope': 'release_bound_native_mcp_self_reload_during_live_acceptance_or_accepted',
        'authorized_for': ['native_mcp_reload'],
    })


def _queue_exact(project: Path, release='32.4.49'):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    runtime = project / 'Inbox/projectmanager_v2/RuntimeV2'
    commands = CommandStore(runtime / 'commands/queue.json')
    decisions = DecisionQueue(runtime / 'decisions/queue.json')
    command = commands.enqueue({
        'intent': 'native_mcp_reload', 'source': 'projectmanager_auto',
        'release_version': release, 'title': 'exact native self-heal',
    })
    decision = decisions.request(
        'PRODUCTION_RESTART', 'reload exact native mcp',
        fingerprint=f"command:{command['id']}:PRODUCTION_RESTART",
        context={
            'command_id': command['id'], 'intent': 'native_mcp_reload',
            'release_version': release, 'source': 'projectmanager_auto',
        },
    )
    commands.wait_for_approval(command['id'], decision_id=decision['id'])
    return commands, decisions, command, decision


def test_32449_self_heal_breaks_exact_live_acceptance_deadlock(tmp_path):
    from native_mcp_self_heal import NativeMcpSelfHealAuthorizer
    project = tmp_path / 'project'
    _setup_live_acceptance(project)
    commands, decisions, command, decision = _queue_exact(project)

    result = NativeMcpSelfHealAuthorizer(project, commands, decisions).run_once()

    assert result['status'] == 'APPROVED'
    assert result['release_phase'] == 'LIVE_ACCEPTANCE'
    assert decisions.get(decision['id'])['status'] == 'APPROVED'
    assert commands.get(command['id'])['status'] == 'APPROVED_READY'


def test_32449_live_acceptance_self_heal_fails_closed_if_any_other_hold_check_is_red(tmp_path):
    from native_mcp_self_heal import NativeMcpSelfHealAuthorizer
    project = tmp_path / 'project'
    _setup_live_acceptance(project)
    hold_path = project / 'Inbox/operating_mode/release_validation_hold.json'
    hold = json.loads(hold_path.read_text(encoding='utf-8'))
    hold['validation_checks']['release_chain'] = {'ok': False}
    hold['reasons'] = ['projectmanager_self_audit', 'release_chain']
    _write_json(hold_path, hold)
    commands, decisions, command, decision = _queue_exact(project)

    result = NativeMcpSelfHealAuthorizer(project, commands, decisions).run_once()

    assert result['status'] == 'BLOCKED'
    assert result['reason'] == 'live_acceptance_not_safe_for_native_mcp_self_heal'
    assert decisions.get(decision['id'])['status'] == 'PENDING'
    assert commands.get(command['id'])['status'] == 'WAITING_APPROVAL'


def test_32449_self_audit_recomputes_build_contract_instead_of_treating_static_contract_as_result(tmp_path):
    from development_build_contract import canonical_contract
    from self_audit import SelfAuditor

    runtime = tmp_path / 'RuntimeV2'
    now = datetime.now(timezone.utc)
    release = '32.4.49'
    task = {
        'id': 'task', 'status': 'ACTIVE', 'title': '32.4.49 closure',
        'build_contract_required': True, 'step': 2, 'steps_total': 2,
        'build_metadata': {
            'contract_version': '2026-09-11.v3', 'thinking_level': 'HOOG',
            'release_version': release, 'estimated_total_seconds': 2700,
            'estimated_test_verification_seconds': 900,
            'step_estimates_seconds': [900, 1800],
            'original_estimate_recorded_at': now.isoformat(),
        },
    }
    status = {
        'mode': 'MAINTENANCE', 'health': {'status': 'RED'},
        'updated_at': now.isoformat(), 'cycle_generation': 'g',
        'provenance': {'generation': 'g', 'phase': 'FINAL'},
        'release': {'version': release, 'ha_runtime_version': release, 'nas_version': release, 'active_verified': True},
        'active_task': task,
        # This is intentionally the static contract published by the orchestrator.
        # It has no `compliant` result field and must not itself be judged as a result.
        'development_build_contract': canonical_contract(),
        'progress': {'elapsed_seconds': 10, 'estimated_remaining_seconds': 20},
    }
    heartbeat = {'mode': 'MAINTENANCE', 'health': 'RED', 'heartbeat_at': now.isoformat(), 'cycle_generation': 'g', 'provenance': {'generation': 'g', 'phase': 'FINAL'}}
    handover = {'mode': 'MAINTENANCE', 'release': {'version': release}, 'cycle_generation': 'g', 'provenance': {'generation': 'g', 'phase': 'FINAL'}}
    _write_json(runtime / 'status/current.json', status)
    _write_json(runtime / 'heartbeat/manager.json', heartbeat)
    _write_json(runtime / 'handover/current.json', handover)
    (runtime / 'audit').mkdir(parents=True, exist_ok=True)
    (runtime / 'audit/events.jsonl').write_text(json.dumps({'event_type': 'test'}) + '\n', encoding='utf-8')
    version_path = tmp_path / 'VERSIE.txt'
    version_path.write_text(release + '\n', encoding='utf-8')

    result = SelfAuditor(runtime, production_version_path=version_path, running_release_version=release).run(now=now)

    assert not any(item.get('reason') == 'build_contract_noncompliant' for item in result['invalid'])

def test_32449_self_heal_missing_live_release_fails_closed_without_exception(tmp_path):
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from native_mcp_self_heal import NativeMcpSelfHealAuthorizer
    project = tmp_path / 'project'
    _write_json(project / 'Data/03_Systeem/Projectmanager/Policies/native_mcp_self_heal_policy.json', {
        'schema': 'energie_native_mcp_self_heal_policy_v2', 'enabled': True, 'approved_by': 'Peter',
        'scope': 'release_bound_native_mcp_self_reload_during_live_acceptance_or_accepted',
        'authorized_for': ['native_mcp_reload'],
    })
    runtime = project / 'Inbox/projectmanager_v2/RuntimeV2'
    result = NativeMcpSelfHealAuthorizer(
        project, CommandStore(runtime / 'commands/queue.json'), DecisionQueue(runtime / 'decisions/queue.json')
    ).run_once()
    assert result == {'status': 'BLOCKED', 'reason': 'live_release_unreadable'}
