from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json


def _valid_payload(data):
    return isinstance(data, dict) and isinstance(data.get('sent', {}), dict)


class AlertState:
    def __init__(self, path, *, cooldown_seconds: int = 21600):
        self.path = Path(path)
        self.cooldown_seconds = int(cooldown_seconds)

    def _load(self):
        return load_json(
            self.path,
            default={'schema': 1, 'sent': {}},
            recover_corrupt=True,
            validator=_valid_payload,
        )

    def should_send(self, event: dict, *, now=None) -> bool:
        if event.get('severity') != 'RED' and not event.get('peter_decision_needed'):
            return False
        fingerprint = event.get('fingerprint')
        if not fingerprint:
            return False
        now = now or datetime.now(timezone.utc)
        sent = self._load().get('sent', {}).get(fingerprint)
        if not sent:
            return True
        try:
            last = datetime.fromisoformat(str(sent).replace('Z', '+00:00'))
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return True
        return (now - last).total_seconds() >= self.cooldown_seconds

    def mark_sent(self, event: dict, *, now=None):
        now = now or datetime.now(timezone.utc)
        data = self._load()
        data.setdefault('sent', {})[event['fingerprint']] = now.isoformat()
        atomic_write_json(self.path, data)
        return data['sent'][event['fingerprint']]
