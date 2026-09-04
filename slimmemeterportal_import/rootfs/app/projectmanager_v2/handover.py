from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json
from secret_guard import redact


def build_handover(*, mode: dict, active_task: dict = None, release: dict = None, decisions=None, evidence=None, last_changes=None):
    task = active_task or {}
    payload = {
        'schema': 'energie_projectmanager_handover_v2',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'mode': mode.get('mode', 'USER'),
        'active_task': {
            'title': task.get('title'),
            'goal': task.get('goal'),
            'status': task.get('status'),
            'step': task.get('step'),
            'steps_total': task.get('steps_total'),
            'blockers': list(task.get('blockers', [])),
        } if active_task else None,
        'last_changes': list(last_changes or task.get('changes', []))[-10:],
        'evidence': list(evidence or [])[-10:],
        'release': release or {},
        'next_action': task.get('next_action'),
        'decisions_needed': [item for item in (decisions or []) if item.get('status') == 'PENDING'],
        'pending_approval': next((item.get('kind') for item in (decisions or []) if item.get('status') == 'PENDING'), None),
    }
    return redact(payload)


class HandoverStore:
    def __init__(self, path):
        self.path = Path(path)

    def save(self, payload: dict):
        cleaned = redact(payload)
        atomic_write_json(self.path, cleaned)
        return cleaned

    def load(self):
        return load_json(self.path, default={})
