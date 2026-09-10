from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json
from development_build_contract import normalize_build_metadata

REQUIRED_DOD_GATES = (
    'code_ready',
    'tests_green',
    'functional_validation_green',
    'kb_updated',
    'roadmap_updated',
    'handover_updated',
    'release_ready',
    'no_blockers',
)
VALID_TASK_STATUSES = {'ACTIVE', 'PAUSED', 'BLOCKED', 'WAITING_APPROVAL', 'DONE', 'SUPERSEDED'}


def _valid_payload(data):
    if not isinstance(data, dict) or not isinstance(data.get('tasks', []), list):
        return False
    return all(isinstance(task, dict) and task.get('status') in VALID_TASK_STATUSES for task in data.get('tasks', []))


def definition_of_done(gates: dict) -> dict:
    missing = [name for name in REQUIRED_DOD_GATES if gates.get(name) is not True]
    return {'done': not missing, 'missing': missing}


class TaskStore:
    def __init__(self, path):
        self.path = Path(path)

    def _load(self):
        return load_json(
            self.path,
            default={'schema': 1, 'tasks': []},
            recover_corrupt=True,
            validator=_valid_payload,
        )

    def _save(self, data):
        atomic_write_json(self.path, data)

    def capture(self, title, goal, *, mode='USER', priority=5, intake_fingerprint, approval_required=False):
        fingerprint = str(intake_fingerprint or '').strip()
        if not fingerprint:
            raise ValueError('intake_fingerprint_required')
        data = self._load()
        for task in data.setdefault('tasks', []):
            if task.get('intake_fingerprint') == fingerprint:
                return dict(task)
        now = datetime.now(timezone.utc).isoformat()
        task = {
            'id': uuid4().hex, 'title': str(title), 'goal': str(goal),
            'mode': str(mode), 'status': 'PAUSED', 'step': 1, 'steps_total': 1,
            'priority': int(priority), 'next_action': '', 'blockers': [],
            'changes': ['captured from conversation intake'], 'evidence_refs': [],
            'intake_fingerprint': fingerprint, 'approval_required': bool(approval_required), 'progress_history': [{'step': 1, 'at': now}], 'created_at': now, 'updated_at': now,
        }
        data['tasks'].append(task)
        self._save(data)
        return dict(task)


    def next_captured(self, *, mode=None):
        candidates = [
            task for task in self._load().get('tasks', [])
            if task.get('status') == 'PAUSED'
            and task.get('intake_fingerprint')
            and task.get('approval_required') is not True
            and (mode is None or task.get('mode') == mode)
        ]
        if not candidates:
            return None
        return dict(sorted(candidates, key=lambda task: (task.get('priority', 99), task.get('created_at', '')))[0])

    def resume_captured(self, task_id: str, *, reason: str):
        data = self._load()
        task = self._find(data, task_id)
        if task.get('status') != 'PAUSED' or not task.get('intake_fingerprint'):
            raise ValueError('captured_task_not_paused')
        if task.get('approval_required') is True:
            raise ValueError('captured_task_requires_approval')
        if any(item.get('status') in {'ACTIVE', 'BLOCKED', 'WAITING_APPROVAL'} for item in data.get('tasks', []) if item.get('id') != task_id):
            raise ValueError('another_task_is_active')
        now = datetime.now(timezone.utc).isoformat()
        task['status'] = 'ACTIVE'
        task.setdefault('changes', []).append(f'resumed from conversation backlog: {reason}')
        task['updated_at'] = now
        self._save(data)
        return dict(task)

    def start(self, title: str, goal: str, *, mode: str, steps_total: int, priority: int = 2, build_metadata=None):
        data = self._load()
        now = datetime.now(timezone.utc).isoformat()
        task = {
            'id': uuid4().hex,
            'title': title,
            'goal': goal,
            'mode': mode,
            'status': 'ACTIVE',
            'step': 1,
            'steps_total': int(steps_total),
            'priority': int(priority),
            'next_action': '',
            'blockers': [],
            'changes': [],
            'evidence_refs': [],
            'progress_history': [{'step': 1, 'at': now}],
            'created_at': now,
            'updated_at': now,
        }
        if build_metadata is not None:
            task['build_contract_required'] = True
            task['build_metadata'] = normalize_build_metadata(build_metadata, steps_total=steps_total)
        for existing in data.get('tasks', []):
            if existing.get('status') == 'ACTIVE':
                existing['status'] = 'PAUSED'
                existing['updated_at'] = now
        data.setdefault('tasks', []).append(task)
        self._save(data)
        return dict(task)

    def progress(self, task_id: str, *, step=None, steps_total=None, next_action=None, change=None, evidence_ref=None):
        data = self._load()
        task = self._find(data, task_id)
        previous_step = int(task.get('step') or 1)
        if step is not None:
            task['step'] = int(step)
        if steps_total is not None:
            task['steps_total'] = int(steps_total)
        if next_action is not None:
            task['next_action'] = next_action
        if change:
            task.setdefault('changes', []).append(change)
        if evidence_ref:
            task.setdefault('evidence_refs', []).append(evidence_ref)
        updated_at = datetime.now(timezone.utc).isoformat()
        if int(task.get('step') or 1) != previous_step:
            task.setdefault('progress_history', []).append({'step': int(task.get('step') or 1), 'at': updated_at})
        task['updated_at'] = updated_at
        self._save(data)
        return dict(task)

    def pause(self, task_id: str, reason: str):
        data = self._load()
        task = self._find(data, task_id)
        if task.get('status') == 'DONE':
            return dict(task)
        task['status'] = 'PAUSED'
        task.setdefault('changes', []).append(f'paused: {reason}')
        task['updated_at'] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        return dict(task)

    def supersede(self, task_id: str, *, reason: str, evidence_refs: list, superseded_by=None, now=None):
        reason = str(reason or '').strip()
        refs = list(dict.fromkeys(str(item).strip() for item in (evidence_refs or []) if str(item).strip()))
        if not reason:
            raise ValueError('supersede_reason_required')
        if not refs:
            raise ValueError('supersede_evidence_required')
        data = self._load()
        task = self._find(data, task_id)
        if task.get('status') == 'SUPERSEDED':
            return dict(task)
        if task.get('status') == 'DONE':
            return dict(task)
        stamp = (now or datetime.now(timezone.utc)).isoformat()
        task['status'] = 'SUPERSEDED'
        task['superseded_at'] = stamp
        task['superseded_reason'] = reason
        task['superseded_evidence_refs'] = refs
        if superseded_by is not None and str(superseded_by).strip():
            task['superseded_by'] = str(superseded_by).strip()
        task.setdefault('changes', []).append(f'superseded: {reason}')
        for ref in refs:
            if ref not in task.setdefault('evidence_refs', []):
                task['evidence_refs'].append(ref)
        task['updated_at'] = stamp
        self._save(data)
        return dict(task)

    def resume_handoff(self, task_id: str, *, reason: str, evidence_refs: list, now=None):
        reason = str(reason or '').strip()
        refs = list(dict.fromkeys(str(item).strip() for item in (evidence_refs or []) if str(item).strip()))
        if not reason:
            raise ValueError('handoff_resume_reason_required')
        if not refs:
            raise ValueError('handoff_resume_evidence_required')
        data = self._load()
        task = self._find(data, task_id)
        if task.get('status') != 'PAUSED':
            raise ValueError(f"handoff task cannot resume from {task.get('status')}")
        if not str(task.get('next_action') or '').startswith('handoff:'):
            raise ValueError('task is not a handoff task')
        stamp = (now or datetime.now(timezone.utc)).isoformat()
        task['status'] = 'ACTIVE'
        task.setdefault('changes', []).append(f'handoff resumed: {reason}')
        for ref in refs:
            if ref not in task.setdefault('evidence_refs', []):
                task['evidence_refs'].append(ref)
        task['updated_at'] = stamp
        self._save(data)
        return dict(task)

    def block(self, task_id: str, reason: str):
        data = self._load()
        task = self._find(data, task_id)
        if task.get('status') == 'DONE':
            return dict(task)
        task['status'] = 'BLOCKED'
        if reason not in task.setdefault('blockers', []):
            task['blockers'].append(reason)
        task['updated_at'] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        return dict(task)

    def mark_release_ready(self, task_id: str):
        data = self._load()
        task = self._find(data, task_id)
        task['status'] = 'WAITING_APPROVAL'
        task['updated_at'] = datetime.now(timezone.utc).isoformat()
        self._save(data)
        return dict(task)

    def complete(self, task_id: str, gates: dict):
        result = definition_of_done(gates)
        if not result['done']:
            raise ValueError(f"definition of done missing: {', '.join(result['missing'])}")
        data = self._load()
        task = self._find(data, task_id)
        if task.get('status') == 'DONE':
            return dict(task)
        task['status'] = 'DONE'
        task['completed_at'] = datetime.now(timezone.utc).isoformat()
        task['updated_at'] = task['completed_at']
        self._save(data)
        return dict(task)

    def complete_handoff(self, task_id: str, *, summary: str, evidence_refs: list, gates=None):
        summary = str(summary or '').strip()
        refs = [str(item).strip() for item in (evidence_refs or []) if str(item).strip()]
        if not summary:
            raise ValueError('handoff summary required')
        if not refs:
            raise ValueError('handoff completion requires evidence')
        data = self._load()
        task = self._find(data, task_id)
        if task.get('status') == 'DONE':
            return dict(task)
        if task.get('mode') == 'DEVELOPMENT':
            dod_gates = dict(gates or {})
            result = definition_of_done(dod_gates)
            if not result['done']:
                raise ValueError(f"definition of done missing: {', '.join(result['missing'])}")
            task['dod_gates'] = dod_gates
        if not str(task.get('next_action') or '').startswith('handoff:'):
            raise ValueError('task is not a handoff task')
        if task.get('status') not in {'ACTIVE', 'BLOCKED'}:
            raise ValueError(f"handoff task cannot complete from {task.get('status')}")
        now = datetime.now(timezone.utc).isoformat()
        task['status'] = 'DONE'
        task['step'] = max(int(task.get('step') or 1), int(task.get('steps_total') or 1))
        task['next_action'] = ''
        task.setdefault('changes', []).append(f'handoff completed: {summary}')
        for ref in refs:
            if ref not in task.setdefault('evidence_refs', []):
                task['evidence_refs'].append(ref)
        task['blockers'] = []
        task['completed_at'] = now
        task['updated_at'] = now
        self._save(data)
        return dict(task)

    def get(self, task_id: str):
        data = self._load()
        return dict(self._find(data, task_id))

    def active(self):
        tasks = self._load().get('tasks', [])
        candidates = [task for task in tasks if task.get('status') in {'ACTIVE', 'BLOCKED', 'WAITING_APPROVAL'}]
        if not candidates:
            return None
        return dict(sorted(candidates, key=lambda t: (t.get('priority', 99), t.get('created_at', '')))[0])

    def all(self):
        return [dict(task) for task in self._load().get('tasks', [])]

    @staticmethod
    def _find(data, task_id):
        for task in data.get('tasks', []):
            if task.get('id') == task_id:
                return task
        raise KeyError(task_id)
