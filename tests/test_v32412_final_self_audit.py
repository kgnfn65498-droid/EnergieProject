import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from self_audit import SelfAuditor


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _final_runtime(root, *, active='32.4.11', nas='32.4.12', manager='2.0.0-rc9'):
    now = datetime.now(timezone.utc).isoformat()
    progress = {
        'step_label': 'Stap 2/4', 'step': 2, 'steps_total': 4,
        'completed_steps': 1, 'remaining_steps': 3, 'next_step': 'audit',
        'elapsed_seconds': 60, 'estimated_remaining_seconds': 180,
        'blockers': [], 'status_color': 'GREEN', 'progress_percent': 50,
        'planning_trend': 'stable',
    }
    task = {
        'id': 't1', 'title': 'closure', 'goal': 'closure', 'mode': 'DEVELOPMENT',
        'status': 'ACTIVE', 'step': 2, 'steps_total': 4, 'next_action': 'audit',
        'blockers': [], 'priority': 1, 'created_at': now, 'updated_at': now,
    }
    intake = {'schema': 1, 'total': 2, 'classification_counts': {'hard_requirement': 1, 'action_item': 1}}
    canonical = {'schema': 3, 'version': '32.4.12', 'sha256': 'abc'}
    reconciliation = {'schema': 1, 'counts': {'ACTIVE_KEEP': 1}, 'items': []}
    issues = [{'id': 'i1', 'status': 'OPEN', 'severity': 'ORANGE'}]
    release = {
        'version': active, 'ha_runtime_version': active, 'nas_version': nas,
        'available_update': nas if active != nas else None, 'active_verified': True,
        'rollback_versions': ['32.4.10'],
    }
    status = {
        'schema': 'energie_projectmanager_status_v2', 'updated_at': now,
        'project_id': 'energie', 'mode': 'DEVELOPMENT', 'health': {'status': 'GREEN'},
        'release': release, 'manager': {'version': manager}, 'active_task': task,
        'progress': progress, 'conversation_intake': intake, 'canonical_roadmap': canonical,
        'state_reconciliation': reconciliation, 'open_issues': issues,
        'pending_commands': 0, 'handoffs': [], 'approved_actions': [],
    }
    handover = {
        'schema': 'energie_projectmanager_handover_v2', 'mode': 'DEVELOPMENT',
        'release': release, 'manager': {'version': manager},
        'active_task': {k: task.get(k) for k in ('id','title','goal','status','step','steps_total','blockers')},
        'progress': progress, 'conversation_intake': intake, 'canonical_roadmap': canonical,
        'state_reconciliation': reconciliation, 'open_issues': issues,
        'handoffs': [], 'approved_actions': [],
    }
    _write(root / 'status/current.json', status)
    _write(root / 'heartbeat/manager.json', {'mode': 'DEVELOPMENT', 'health': 'GREEN', 'heartbeat_at': now})
    _write(root / 'handover/current.json', handover)
    (root / 'audit').mkdir(parents=True, exist_ok=True)
    (root / 'audit/events.jsonl').write_text(json.dumps({'event_type': 'test'}) + '\n', encoding='utf-8')
    _write(root / 'state/tasks.json', {'schema': 1, 'tasks': [task]})
    _write(root / 'commands/queue.json', {'schema': 1, 'items': []})
    _write(root / 'handoffs/queue.json', {'schema': 1, 'items': []})
    _write(root / 'approved_actions/queue.json', {'schema': 1, 'items': []})
    _write(root / 'roadmap/queue.json', {'schema': 2, 'canonical': canonical, 'items': []})
    _write(root / 'intake/items.json', {'schema': 1, 'items': []})
    return status, handover


def test_self_audit_distinguishes_running_ha_release_from_nas_release(tmp_path):
    root = tmp_path / 'RuntimeV2'
    _final_runtime(root, active='32.4.11', nas='32.4.12')
    nas_version = tmp_path / 'VERSIE.txt'
    nas_version.write_text('32.4.12\n', encoding='utf-8')

    result = SelfAuditor(
        root, production_version_path=nas_version, running_release_version='32.4.11'
    ).run(require_coordination=True)

    assert result['status'] == 'GREEN', result


def test_self_audit_rejects_nas_version_drift_without_marking_ha_runtime_as_nas(tmp_path):
    root = tmp_path / 'RuntimeV2'
    _final_runtime(root, active='32.4.11', nas='32.4.13')
    nas_version = tmp_path / 'VERSIE.txt'
    nas_version.write_text('32.4.12\n', encoding='utf-8')

    result = SelfAuditor(
        root, production_version_path=nas_version, running_release_version='32.4.11'
    ).run(require_coordination=True)

    assert result['status'] == 'RED'
    assert any(item['reason'] == 'nas_release_mismatch' for item in result['invalid'])
    assert not any(item['reason'] == 'release_mismatch' for item in result['invalid'])


def test_final_self_audit_rejects_late_manager_and_handover_divergence(tmp_path):
    root = tmp_path / 'RuntimeV2'
    _, handover = _final_runtime(root)
    handover['manager'] = {'version': '2.0.0-rc8'}
    _write(root / 'handover/current.json', handover)

    result = SelfAuditor(root, running_release_version='32.4.11').run(require_coordination=True)

    assert result['status'] == 'RED'
    assert any(item['reason'] == 'manager_version_mismatch' for item in result['invalid'])


def test_final_self_audit_rejects_late_progress_or_intake_divergence(tmp_path):
    root = tmp_path / 'RuntimeV2'
    _, handover = _final_runtime(root)
    handover['progress']['step'] = 3
    handover['conversation_intake']['total'] = 99
    _write(root / 'handover/current.json', handover)

    result = SelfAuditor(root, running_release_version='32.4.11').run(require_coordination=True)

    reasons = {item['reason'] for item in result['invalid']}
    assert 'progress_mismatch' in reasons
    assert 'conversation_intake_mismatch' in reasons


def test_orchestrator_runs_coordination_self_audit_after_final_refresh():
    source = (PM / 'orchestrator.py').read_text(encoding='utf-8')
    run_once = source.split('    def run_once(self, *, now=None):', 1)[1].split('\n    def _finalize_coordination_audit', 1)[0]
    assert 'self._refresh_coordination(status)' in run_once
    assert 'self._finalize_coordination_audit(status, now=now)' in run_once
    assert run_once.index('self._finalize_coordination_audit(status, now=now)') > run_once.index('self._refresh_coordination(status)')


def test_32440_coordination_requires_matrix_efficiency_and_context(tmp_path):
    root = tmp_path / 'RuntimeV2'
    _final_runtime(root, active='32.4.40', nas='32.4.40', manager='2.0.0-rc27')
    result = SelfAuditor(root, running_release_version='32.4.40').run(require_coordination=True)
    reasons = {item['reason'] for item in result['invalid']}
    assert 'final_field_missing:acceptance_matrix' in reasons
    assert 'final_field_missing:development_efficiency' in reasons
    assert 'final_field_missing:development_context' in reasons
