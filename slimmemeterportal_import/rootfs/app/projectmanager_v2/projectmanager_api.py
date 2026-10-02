import json
from pathlib import Path
from uuid import uuid4

from context_delivery import build_delivery_receipt
from context_package import compact_package
from secret_guard import redact


class ProjectmanagerAPI:
    """Read-only presentation API for MCP/Nomad/parent summaries."""

    def __init__(self, runtime_root, *, project_root=None):
        self.root = Path(runtime_root)
        self.project_root = Path(project_root) if project_root is not None else None

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
        self_audit = status.get('self_audit') if isinstance(status.get('self_audit'), dict) else {}
        self_audit_status = str(self_audit.get('status') or '').strip().upper()
        release_version = str(((status.get('release') or {}).get('version')) or '').strip()
        try:
            release_tuple = tuple(int(part) for part in release_version.split('.'))
        except ValueError:
            release_tuple = ()
        budget_contract = len(release_tuple) == 3 and release_tuple >= (32, 5, 31)
        reasons = []
        if preflight.get('ready') is not True:
            reasons.append('preflight_not_ready')
        if self_audit_status != 'GREEN':
            reasons.append('self_audit_not_green')
        if package.get('inventory_complete') is not True:
            reasons.append('inventory_incomplete')
        if package.get('mandatory_context_complete') is not True:
            reasons.append('mandatory_context_incomplete')
        if budget_contract and package.get('delivery_within_budget') is not True:
            reasons.append('delivery_budget_exceeded')
        if (package.get('resume_contract') or {}).get('fail_closed') is True:
            reasons.append('resume_contract_fail_closed')
        if not str(package.get('package_sha256') or '').strip():
            reasons.append('package_identity_missing')
        return {
            'ready': not reasons,
            'preflight_ready': preflight.get('ready') is True,
            'self_audit_status': self_audit_status or 'MISSING',
            'inventory_complete': package.get('inventory_complete') is True,
            'mandatory_context_complete': package.get('mandatory_context_complete') is True,
            'delivery_within_budget': package.get('delivery_within_budget'),
            'package_sha256': package.get('package_sha256') or '',
            'first_unproven_action': (package.get('resume_contract') or {}).get('first_unproven_action') or '',
            'conflicts_missing_evidence': package.get('conflicts_missing_evidence') or {},
            'blocking_reasons': reasons,
        }

    def resume_context(self, *, consumer: str = 'chatgpt_mcp') -> dict:
        """Return one compact, fail-closed and response-bound resume context.

        The receipt is generated server-side against the exact semantic payload
        returned here. It proves the Projectmanager/MCP response boundary, not
        hidden model compliance; behavioral E2E remains a separate gate.
        """
        status = self.status()
        gate = self._context_gate(status)
        development_context = status.get('development_context') if isinstance(status.get('development_context'), dict) else {}
        package = development_context.get('context_package') if isinstance(development_context.get('context_package'), dict) else {}
        raw_handover = self.handover()
        runtime_handover = {
            'release': raw_handover.get('release') or {},
            'active_task': raw_handover.get('active_task'),
            'progress': raw_handover.get('progress'),
            'next_action': raw_handover.get('next_action'),
            'decisions_needed': raw_handover.get('decisions_needed') or [],
            'pending_approval': raw_handover.get('pending_approval'),
        }
        invocation_id = uuid4().hex
        semantic_payload = {
            'schema': 'energie_projectmanager_resume_context_payload_v1',
            'invocation_id': invocation_id,
            'state': 'READY' if gate.get('ready') else 'BLOCKED',
            'context_gate': gate,
            'context_package': package if gate.get('ready') else compact_package(package),
            'runtime_handover': runtime_handover,
            'resume_rule': (
                'Use canonical current truth and the first unproven action; never repeat '
                'proven work unless newer evidence invalidates it.'
            ),
            'behavior_status': 'UNPROVEN',
        }
        receipt = build_delivery_receipt(
            package,
            invocation_id=invocation_id,
            consumer=consumer,
            project_root=self.project_root,
            delivered_payload=semantic_payload,
        )
        return redact({
            **semantic_payload,
            'delivery_status': 'RECORDED' if receipt.get('delivery_recorded') is True else 'UNPROVEN',
            'delivery_receipt': receipt,
        })

    def delivery_receipt(self, *, invocation_id: str, final_input_sha256: str, consumer: str = 'external_model') -> dict:
        """Legacy caller-hash surface.

        Caller-asserted input hashes remain evidence-only and intentionally
        cannot produce delivery_recorded=True. Use resume_context for the
        server-bound MCP response receipt.
        """
        status = self.status()
        gate = self._context_gate(status)
        development_context = status.get('development_context') if isinstance(status.get('development_context'), dict) else {}
        package = development_context.get('context_package') if isinstance(development_context.get('context_package'), dict) else {}
        if gate.get('ready') is not True:
            return redact({
                'schema': 'energie_pm_context_delivery_receipt_blocked_v1',
                'delivery_recorded': False,
                'actual_model_boundary_verified': False,
                'reason': 'context_gate_not_ready',
                'context_gate': gate,
                'package_sha256': package.get('package_sha256') or '',
            })
        return redact(build_delivery_receipt(
            package,
            invocation_id=invocation_id,
            final_input_sha256=final_input_sha256,
            consumer=consumer,
            project_root=self.project_root,
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
