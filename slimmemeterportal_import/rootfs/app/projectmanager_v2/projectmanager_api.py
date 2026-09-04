from pathlib import Path

from command_store import CommandStore
from decision_queue import DecisionQueue
from persistence import load_json
from secret_guard import redact


class ProjectmanagerAPI:
    def __init__(self, runtime_root):
        self.root = Path(runtime_root)
        self.command_store = CommandStore(self.root / 'commands' / 'queue.json')
        self.decision_queue = DecisionQueue(self.root / 'decisions' / 'queue.json')

    def _not_ready(self):
        return {
            'state': 'NOT_READY',
            'project_id': 'energie',
            'mode': None,
            'health': {'status': 'ORANGE', 'attention_count': 1, 'reason': 'projectmanager_status_missing'},
            'release': {},
            'active_task': None,
            'next_action': 'start or diagnose projectmanager service',
            'needs_human': False,
            'decisions_needed': [],
        }

    def status(self):
        status = load_json(self.root / 'status' / 'current.json', default=None)
        if not isinstance(status, dict):
            return self._not_ready()
        return redact(status)

    def handover(self):
        payload = load_json(self.root / 'handover' / 'current.json', default=None)
        return redact(payload) if isinstance(payload, dict) else {'state': 'NOT_READY'}

    def decisions(self):
        return redact({'items': self.decision_queue.pending()})

    def opportunities(self):
        data = load_json(self.root / 'opportunities' / 'register.json', default={'items': []})
        items = sorted(data.get('items', []), key=lambda x: (x.get('status') != 'PROMOTED', x.get('category',''), x.get('subject','')))
        return redact({'items': items})

    def submit_command(self, command: dict):
        allowed = {
            'intent','source','text','title','goal','steps_total','priority','next_action',
        }
        payload = {key:value for key,value in (command or {}).items() if key in allowed}
        payload.setdefault('source','chat')
        return redact(self.command_store.enqueue(payload))

    def resolve_decision(self, decision_id: str, *, approved: bool, approved_by: str = 'Peter'):
        if not decision_id:
            raise ValueError('decision_id is required')
        if approved_by != 'Peter':
            raise ValueError('only Peter may resolve protected Projectmanager decisions')
        return redact(self.decision_queue.resolve(decision_id, approved=bool(approved), approved_by=approved_by))

    def nomad_context(self):
        status = self.status()
        return {
            'project_id': status.get('project_id', 'energie'),
            'mode': status.get('mode'),
            'health': status.get('health'),
            'release': status.get('release', {}),
            'active_task': status.get('active_task'),
            'next_action': status.get('next_action'),
            'needs_human': status.get('needs_human', False),
            'decisions_needed': status.get('decisions_needed', []),
        }

    def parent_summary(self):
        status = self.status()
        task = status.get('active_task') or {}
        return {
            'project_id': status.get('project_id', 'energie'),
            'mode': status.get('mode'),
            'health': (status.get('health') or {}).get('status'),
            'active_priority': task.get('priority'),
            'active_task': task.get('title'),
            'blockers': task.get('blockers', []),
            'needs_human': status.get('needs_human', False),
        }
