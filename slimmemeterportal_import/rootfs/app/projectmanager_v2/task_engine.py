from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from persistence import atomic_write_json, load_json

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
VALID_TASK_STATUSES = {'ACTIVE', 'PAUSED', 'BLOCKED', 'WAITING_APPROVAL', 'DONE'}


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

    def start(self, title: str, goal: str, *, mode: str, steps_total: int, priority: int = 2):
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
            'created_at': now,
            'updated_at': now,
        }
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
        task['updated_at'] = datetime.now(timezone.utc).isoformat()
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

    def complete_handoff(self, task_id: str, *, summary: str, evidence_refs: list):
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
