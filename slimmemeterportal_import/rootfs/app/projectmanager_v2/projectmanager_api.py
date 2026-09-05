import json
from pathlib import Path

from secret_guard import redact


class ProjectmanagerAPI:
    """Read-only presentation API for MCP/Nomad/parent summaries.

    RuntimeV2 has one writer: the embedded Projectmanager. External command
    proposals use CommandIngress and Peter approvals use ApprovalIngress.
    """

    def __init__(self, runtime_root):
        self.root = Path(runtime_root)

    def _read_dict(self, rel, default=None):
        path = self.root / rel
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else default
        except (OSError, json.JSONDecodeError):
            return default

    def _not_ready(self):
        return {
            'state': 'NOT_READY',
            'project_id': 'energie',
            'mode': None,
            'health': {'status': 'ORANGE', 'attention_count': 1, 'reason': 'projectmanager_status_missing_or_invalid'},
            'release': {},
            'active_task': None,
            'next_action': 'start or diagnose projectmanager service',
            'needs_human': False,
            'decisions_needed': [],
        }

    def status(self):
        status = self._read_dict('status/current.json')
        if not isinstance(status, dict):
            return self._not_ready()
        return redact(status)

    def handover(self):
        payload = self._read_dict('handover/current.json')
        return redact(payload) if isinstance(payload, dict) else {'state': 'NOT_READY'}

    def decisions(self):
        status = self.status()
        return redact({'items': status.get('decisions_needed', [])})

    def opportunities(self):
        data = self._read_dict('opportunities/register.json', default={'items': []}) or {'items': []}
        items = sorted(
            [item for item in data.get('items', []) if isinstance(item, dict)],
            key=lambda x: (x.get('status') != 'PROMOTED', x.get('category', ''), x.get('subject', '')),
        )
        return redact({'items': items})

    def submit_command(self, command: dict):
        raise RuntimeError('direct RuntimeV2 command writes disabled; use CommandIngress')

    def resolve_decision(self, decision_id: str, *, approved: bool, approved_by: str = 'Peter'):
        raise RuntimeError('direct RuntimeV2 decision writes disabled; use authenticated Home Assistant ApprovalIngress')

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
