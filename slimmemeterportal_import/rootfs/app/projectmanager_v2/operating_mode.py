from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json, load_json

VALID_MODES = {'USER', 'DEVELOPMENT', 'MAINTENANCE'}


def _valid_state(data):
    return isinstance(data, dict) and data.get('mode') in VALID_MODES


def transition(current: str, event: str) -> str:
    if current not in VALID_MODES:
        raise ValueError(f'invalid mode: {current}')
    if event == 'development_started':
        return 'DEVELOPMENT'
    if event in {'maintenance_started', 'incident_started', 'crash_recovery_started'}:
        return 'MAINTENANCE'
    if event in {'definition_of_done_met', 'maintenance_resolved_verified', 'production_deployed_verified'}:
        return 'USER'
    if event in {'user_query', 'release_ready', 'chat_started', 'chat_ended'}:
        return current
    return current


class ModeStore:
    def __init__(self, path):
        self.path = Path(path)

    def get(self):
        return load_json(
            self.path,
            default={
                'schema': 1,
                'mode': 'USER',
                'reason': 'default',
                'updated_at': None,
            },
            recover_corrupt=True,
            validator=_valid_state,
        )

    def set(self, mode: str, *, reason: str, source: str = 'projectmanager'):
        if mode not in VALID_MODES:
            raise ValueError(f'invalid mode: {mode}')
        state = {
            'schema': 1,
            'mode': mode,
            'reason': reason,
            'source': source,
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        atomic_write_json(self.path, state)
        return state
