import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from notification_router import notification_route
from persistence import atomic_write_json
from secret_guard import redact


class NotificationOutbox:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.delivered_directory = self.directory / 'delivered'

    def enqueue(self, payload: dict):
        self.directory.mkdir(parents=True, exist_ok=True)
        item = redact(dict(payload))
        item.setdefault('id', uuid4().hex)
        item.setdefault('created_at', datetime.now(timezone.utc).isoformat())
        path = self.directory / f"{item['created_at'].replace(':','').replace('+','_')}_{item['id']}.json"
        atomic_write_json(path, item)
        return {'queued': True, 'path': str(path), 'payload': item}

    def pending(self):
        if not self.directory.exists():
            return []
        result = []
        for path in sorted(self.directory.glob('*.json')):
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                continue
            result.append((path, payload))
        return result

    def mark_delivered(self, path, delivery_result: dict):
        source = Path(path)
        payload = json.loads(source.read_text(encoding='utf-8'))
        payload['delivered_at'] = datetime.now(timezone.utc).isoformat()
        payload['delivery'] = redact(delivery_result)
        self.delivered_directory.mkdir(parents=True, exist_ok=True)
        target = self.delivered_directory / source.name
        atomic_write_json(target, payload)
        source.unlink()
        return str(target)


def route_event(outbox: NotificationOutbox, event: dict) -> dict:
    severity = event.get('severity', 'GREEN')
    route = notification_route(severity, event.get('peter_decision_needed', False))
    if route == 'DIRECT':
        result = outbox.enqueue({
            'severity': severity,
            'subject': event.get('subject', 'Energie Projectmanager'),
            'detail': event.get('detail', ''),
            'route': route,
            'decision_id': event.get('decision_id'),
            'fingerprint': event.get('fingerprint'),
        })
        result['route'] = route
        return result
    return {'queued': False, 'route': route}
