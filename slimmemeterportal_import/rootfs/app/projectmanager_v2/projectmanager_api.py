import json
from pathlib import Path

from secret_guard import redact
from context_package import compact_package
from context_delivery import build_delivery_receipt


class ProjectmanagerAPI:
    """Read-only presentation API for MCP/Nomad/parent summaries.

    RuntimeV2 has one writer: the embedded Projectmanager. External command
    proposals use CommandIngress, handoff results use HandoffResultIngress and
    Peter approvals use local Home Assistant ApprovalIngress.
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

    @staticmethod
    def _context_gate(status: dict) -> dict:
        development_context = status.get('development_context') if isinstance(status.get('development_context'), dict) else {}
        package = development_context.get('context_package') if isinstance(development_context.get('context_package'), dict) else {}
        preflight = status.get('new_chat_preflight') if isinstance(status.get('new_chat_preflight'), dict) else {}
        ready = bool(
            preflight.get('ready') is True
            and package.get('mandatory_context_complete') is True
            and (package.get('resume_contract') or {}).get('fail_closed') is not True
        )
        return {
            'ready': ready,
            'preflight_ready': preflight.get('ready') is True,
            'inventory_complete': package.get('inventory_complete') is True,
            'mandatory_context_complete': package.get('mandatory_context_complete') is True,
            'package_sha256': package.get('package_sha256') or '',
            'first_unproven_action': (package.get('resume_contract') or {}).get('first_unproven_action') or '',
            'conflicts_missing_evidence': package.get('conflicts_missing_evidence') or {},
        }

    def resume_context(self):
        status = self.status()
        gate = self._context_gate(status)
        development_context = status.get('development_context') if isinstance(status.get('development_context'), dict) else {}
        package = development_context.get('context_package') if isinstance(development_context.get('context_package'), dict) else {}
        return redact({
            'schema': 'energie_projectmanager_resume_delivery_v1',
            'state': 'READY' if gate.get('ready') else 'BLOCKED',
            'context_gate': gate,
            'context_package': package if gate.get('ready') else compact_package(package),
            'runtime_handover': self.handover(),
            'delivery_status': 'UNPROVEN',
            'delivery_receipt_required_at_model_boundary': True,
        })

    def delivery_receipt(self, *, invocation_id: str, final_input_sha256: str, consumer: str = 'external_model') -> dict:
        status = self.status()
        development_context = status.get('development_context') if isinstance(status.get('development_context'), dict) else {}
        package = development_context.get('context_package') if isinstance(development_context.get('context_package'), dict) else {}
        return redact(build_delivery_receipt(
            package, invocation_id=invocation_id, final_input_sha256=final_input_sha256, consumer=consumer
        ))

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

    def handoffs(self):
        data = self._read_dict('handoffs/queue.json', default={'items': []}) or {'items': []}
        items = [item for item in data.get('items', []) if isinstance(item, dict) and item.get('status') == 'OPEN']
        return redact({'items': sorted(items, key=lambda x: (x.get('priority', 99), x.get('created_at', '')))})

    def submit_command(self, command: dict):
        raise RuntimeError('direct RuntimeV2 command writes disabled; use CommandIngress')

    def submit_handoff_result(self, result: dict):
        raise RuntimeError('direct RuntimeV2 handoff writes disabled; use HandoffResultIngress')

    def resolve_decision(self, decision_id: str, *, approved: bool, approved_by: str = 'Peter'):
        raise RuntimeError('direct RuntimeV2 decision writes disabled; use authenticated Home Assistant ApprovalIngress')

    def nomad_context(self):
        # Keep the long-standing compact Nomad contract stable. New PM-specific
        # surfaces (handoffs/canonical roadmap) are available through dedicated
        # read-only API/MCP tools and are deliberately not injected here.
        status = self.status()
        return {
            'project_id': status.get('project_id', 'energie'),
            'mode': status.get('mode'),
            'health': status.get('health'),
            'release': status.get('release', {}),
            'active_task': status.get('active_task'),
            'progress': status.get('progress'),
            'development_build_contract': status.get('development_build_contract') or {},
            'development_efficiency': status.get('development_efficiency') or {},
            'acceptance_matrix': status.get('acceptance_matrix') or {},
            'development_context': status.get('development_context') or {},
            'context_gate': self._context_gate(status),
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
            'context_gate': self._context_gate(status),
            'open_handoffs': len(status.get('handoffs', [])),
        }
