import json
from datetime import datetime, timezone
from pathlib import Path


class RuntimeCollector:
    def __init__(self, project_root, *, mode_state_path=None, running_release_version=None,
                 watcher_stale_seconds=60, processing_stale_seconds=600):
        self.project_root = Path(project_root)
        self.mode_state_path = Path(mode_state_path) if mode_state_path else None
        self.running_release_version = str(running_release_version or '').strip() or None
        self.watcher_stale_seconds = int(watcher_stale_seconds)
        self.processing_stale_seconds = int(processing_stale_seconds)

    @staticmethod
    def _read_json(path):
        try:
            value = json.loads(Path(path).read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    @staticmethod
    def _file_age(path, now):
        try:
            return max(0.0, now.timestamp() - Path(path).stat().st_mtime)
        except OSError:
            return None

    @staticmethod
    def _zip_snapshot(directory, *, now, stale_after=None):
        root = Path(directory)
        files = []
        if root.is_dir():
            for path in sorted(root.glob('*.zip')):
                if not path.is_file():
                    continue
                age = RuntimeCollector._file_age(path, now)
                files.append({
                    'name': path.name,
                    'path': str(path),
                    'age_seconds': round(age, 1) if age is not None else None,
                    'stuck': bool(stale_after is not None and age is not None and age >= stale_after),
                })
        return {
            'path': str(root),
            'count': len(files),
            'stuck_count': sum(1 for item in files if item['stuck']),
            'files': files,
        }

    def _release_chain(self, *, now):
        inbox = self.project_root / 'Inbox'
        heartbeat_path = inbox / '.watcher.heartbeat'
        heartbeat_age = self._file_age(heartbeat_path, now)
        watcher_active = heartbeat_age is not None and heartbeat_age <= self.watcher_stale_seconds
        atomic = self._read_json(inbox / 'atomic_app_swap_state.json') or {}
        publisher = self._read_json(inbox / 'github_publisher_state.json') or {}
        publication_contract = self._read_json(inbox / 'ha_publication_required.json') or {}
        return {
            'watcher': {
                'active': watcher_active,
                'heartbeat_path': str(heartbeat_path),
                'heartbeat_age_seconds': round(heartbeat_age, 1) if heartbeat_age is not None else None,
                'stale_after_seconds': self.watcher_stale_seconds,
            },
            'incoming': self._zip_snapshot(inbox / 'incoming', now=now),
            'processing': self._zip_snapshot(
                inbox / 'processing', now=now, stale_after=self.processing_stale_seconds,
            ),
            'installer_lock': {
                'active': (inbox / '.installer.lock').exists(),
                'path': str(inbox / '.installer.lock'),
            },
            'atomic_swap': {
                'state': atomic.get('state'),
                'raw': atomic,
                'source': str(inbox / 'atomic_app_swap_state.json'),
            },
            'publisher': {
                'status': publisher.get('status'),
                'version': publisher.get('version'),
                'message': publisher.get('message'),
                'updated_at': publisher.get('updated_at'),
                'source': str(inbox / 'github_publisher_state.json'),
            },
            'github_publication': {
                'status': publisher.get('status'),
                'version': publisher.get('version') or publication_contract.get('version'),
                'contract_pending': bool(publication_contract),
                'contract_version': publication_contract.get('version'),
                'source': str(inbox / 'github_publisher_state.json'),
            },
        }

    def collect(self, *, now=None) -> dict:
        now = now or datetime.now(timezone.utc)
        version_path = self.project_root / 'App' / 'VERSIE.txt'
        mode_path = self.mode_state_path or (self.project_root / 'Inbox' / 'operating_mode' / 'operating_mode_state.json')
        nas_version = None
        if version_path.is_file():
            try:
                nas_version = version_path.read_text(encoding='utf-8').strip() or None
            except OSError:
                nas_version = None
        rollback_versions = []
        for path in sorted(self.project_root.glob('App.__rollback_*')):
            version_file = path / 'VERSIE.txt'
            try:
                version = version_file.read_text(encoding='utf-8').strip() if version_file.is_file() else ''
            except OSError:
                version = ''
            if version and version not in rollback_versions:
                rollback_versions.append(version)
        active_version = self.running_release_version
        result = {
            'release': {
                'version': active_version,
                'ha_runtime_version': active_version,
                'nas_version': nas_version,
                'available_update': nas_version if active_version and nas_version and active_version != nas_version else None,
                'rollback_version': rollback_versions[0] if rollback_versions else None,
                'rollback_versions': rollback_versions,
                'active_verified': bool(active_version),
                'active_version_source': 'running_addon' if active_version else 'unknown',
                'source': str(version_path),
            },
            'release_chain': self._release_chain(now=now),
            'operating_mode': {'effective_mode': None, 'source': str(mode_path)},
        }
        if not version_path.is_file():
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
