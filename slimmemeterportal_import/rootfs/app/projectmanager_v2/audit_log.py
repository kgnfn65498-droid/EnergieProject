from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

from persistence import append_jsonl


class AuditLog:
    def __init__(self, path):
        self.path = Path(path)

    def write(self, event_type: str, *, actor: str, result: str, evidence_ref: Optional[str] = None, details: Optional[dict] = None):
        event = {
            'event_id': uuid4().hex,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'event_type': event_type,
            'actor': actor,
            'result': result,
            'evidence_ref': evidence_ref,
            'details': details or {},
        }
        append_jsonl(self.path, event)
        return event
