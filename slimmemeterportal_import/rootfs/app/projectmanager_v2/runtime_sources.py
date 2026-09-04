import json
from pathlib import Path


class RuntimeCollector:
    def __init__(self, project_root, *, mode_state_path=None):
        self.project_root = Path(project_root)
        self.mode_state_path = Path(mode_state_path) if mode_state_path else None

    def collect(self) -> dict:
        version_path = self.project_root / 'App' / 'VERSIE.txt'
        mode_path = self.mode_state_path or (self.project_root / 'Inbox' / 'operating_mode' / 'operating_mode_state.json')
        result = {
            'release': {'version': None, 'source': str(version_path)},
            'operating_mode': {'effective_mode': None, 'source': str(mode_path)},
        }
        if version_path.is_file():
            version = version_path.read_text(encoding='utf-8').strip()
            result['release']['version'] = version or None
        else:
            result['release']['missing'] = True

        if mode_path.is_file():
            try:
                mode_data = json.loads(mode_path.read_text(encoding='utf-8'))
                result['operating_mode']['effective_mode'] = (
                    mode_data.get('effective_mode')
                    or mode_data.get('base_mode')
                    or mode_data.get('mode')
                )
                result['operating_mode']['raw'] = mode_data
            except (OSError, json.JSONDecodeError) as exc:
                result['operating_mode']['error'] = str(exc)
        else:
            result['operating_mode']['missing'] = True
        return result
