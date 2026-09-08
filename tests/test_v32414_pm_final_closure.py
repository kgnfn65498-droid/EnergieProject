import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = RUNTIME_APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(RUNTIME_APP))

from conversation_intake import ConversationIntakeBridge, classify_intake
from task_engine import TaskStore
from operating_mode_runtime import _projectmanager_self_audit_check


def _write_json(path: Path, payload: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_architecture_changes_for_claude_cowork_always_require_approval():
    variants = [
        'Pas de architectuur aan zodat Claude Cowork erbij kan.',
        'Wijzig de opzet zodat Claude Cowork gekoppeld kan worden.',
        'Bouw de architectuur om voor Claude Cowork.',
        'Herstructureer het systeem voor Claude Cowork.',
    ]
    for text in variants:
        classified = classify_intake(text)
        assert classified['development_context'] is True, text
        assert classified['approval_required'] is True, text


def test_architecture_analysis_without_change_request_remains_autonomous_analysis():
    classified = classify_intake('Onderzoek wat een architectuurwijziging zou betekenen voor Claude Cowork.')
    assert classified['approval_required'] is False


def test_home_assistant_and_live_deploy_actions_always_require_approval():
    variants = [
        'Installeer deze release in Home Assistant.',
        'Plaats dit op de Home Assistant Green.',
        'Zet dit live in Home Assistant.',
        'Deploy deze release naar HA.',
        'Activeer deze build op de Green.',
        'Publiceer en activeer deze wijziging in productie.',
    ]
    for text in variants:
        classified = classify_intake(text)
        assert classified['development_context'] is True, text
        assert classified['approval_required'] is True, text


def test_safe_development_work_is_not_overblocked():
    classified = classify_intake('Bouw een test voor Conversation Intake.')
    assert classified['development_context'] is True
    assert classified['approval_required'] is False


def test_protected_architecture_intake_cannot_enter_autonomous_backlog(tmp_path):
    tasks = TaskStore(tmp_path / 'tasks.json')
    bridge = ConversationIntakeBridge(
        tmp_path / 'intake.json', tasks, None, tmp_path / 'reports'
    )
    result = bridge.accept({
        'text': 'Pas de architectuur aan zodat Claude Cowork erbij kan.',
        'source_channel': 'chatgpt',
        'source_ref': 'audit-32414-architecture',
    })
    assert result['approval_required'] is True
    stored = tasks._load()['tasks'][0]
    assert stored['approval_required'] is True
    assert tasks.next_captured(mode='DEVELOPMENT') is None


def _pm_runtime_files(root: Path, *, health: dict, audit_status='GREEN'):
    audit = root / 'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json'
    status = root / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
    version = root / 'App/VERSIE.txt'
    _write_json(audit, {'status': audit_status, 'invalid': [], 'warnings': []})
    _write_json(status, {
        'schema': 'energie_projectmanager_status_v2',
        'release': {'version': '32.4.14'},
        'health': health,
    })
    version.parent.mkdir(parents=True, exist_ok=True)
    version.write_text('32.4.14\n', encoding='utf-8')
    # The final self-audit must be at least as fresh as the status it validates.
    audit.touch()


def test_release_acceptance_blocks_when_pm_health_contains_real_red_check(tmp_path):
    root = tmp_path / 'energy'
    _pm_runtime_files(root, health={
        'status': 'RED',
        'checks': [
            {'name': 'release_watcher', 'status': 'RED', 'reason': 'watcher_inactive_or_stale'},
            {'name': 'release_atomic_state', 'status': 'ORANGE', 'reason': 'installer_or_atomic_transition_active'},
        ],
    })
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is False
    assert 'projectmanager health RED' in result['detail']


def test_release_acceptance_blocks_when_status_claims_red_without_red_check(tmp_path):
    root = tmp_path / 'energy'
    _pm_runtime_files(root, health={
        'status': 'RED',
        'checks': [
            {'name': 'release_atomic_state', 'status': 'ORANGE', 'reason': 'installer_or_atomic_transition_active'},
        ],
    })
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is False
    assert 'projectmanager health RED' in result['detail']


def test_release_acceptance_allows_only_expected_live_acceptance_orange_transition(tmp_path):
    root = tmp_path / 'energy'
    _pm_runtime_files(root, health={
        'status': 'ORANGE',
        'checks': [
            {'name': 'release_atomic_state', 'status': 'ORANGE', 'reason': 'installer_or_atomic_transition_active'},
        ],
    })
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is True


def test_release_acceptance_blocks_unrelated_orange_during_finalization(tmp_path):
    root = tmp_path / 'energy'
    _pm_runtime_files(root, health={
        'status': 'ORANGE',
        'checks': [
            {'name': 'release_publisher', 'status': 'ORANGE', 'reason': 'publisher_status_missing_or_unknown'},
        ],
    })
    result = _projectmanager_self_audit_check(root)
    assert result['ok'] is False
    assert 'unexpected non-green projectmanager health' in result['detail']


def test_auto_release_daemon_restarts_bounded_worker_until_released(monkeypatch):
    import operating_mode_auto_release as auto

    calls = []

    def fake_worker(stop_event, app_module, project_root, expected_version, **kwargs):
        calls.append(expected_version)
        if len(calls) < 3:
            return {'status': 'blocked', 'validation': {'status': 'blocked'}}
        return {'status': 'released', 'validation': {'status': 'ok'}}

    class StopEvent:
        def wait(self, delay):
            return False

    monkeypatch.setattr(auto, 'automatic_release_hold_worker', fake_worker)
    result = auto.automatic_release_hold_daemon(
        StopEvent(), object(), Path('/tmp/unused'), '32.4.14', cycle_delay=0.0
    )
    assert result['status'] == 'released'
    assert len(calls) == 3


def test_auto_release_daemon_stops_cleanly_while_release_remains_blocked(monkeypatch):
    import operating_mode_auto_release as auto

    calls = []

    def fake_worker(stop_event, app_module, project_root, expected_version, **kwargs):
        calls.append(expected_version)
        return {'status': 'blocked', 'validation': {'status': 'blocked'}}

    class StopEvent:
        def __init__(self):
            self.waits = 0
        def wait(self, delay):
            self.waits += 1
            return self.waits >= 3

    stop = StopEvent()
    monkeypatch.setattr(auto, 'automatic_release_hold_worker', fake_worker)
    result = auto.automatic_release_hold_daemon(
        stop, object(), Path('/tmp/unused'), '32.4.14', cycle_delay=0.0
    )
    assert result['status'] == 'stopped'
    assert len(calls) == 3

def test_projectmanager_starts_before_auto_release_daemon():
    source = (RUNTIME_APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    pm_start = source.index('start_projectmanager_v2(app.STOP, root, TARGET_RELEASE_VERSION)')
    worker_start = source.index('target=automatic_release_hold_worker')
    assert 'automatic_release_hold_daemon as automatic_release_hold_worker' in source
    assert pm_start < worker_start
