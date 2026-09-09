import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path


class RuntimeCollector:
    def __init__(self, project_root, *, mode_state_path=None, running_release_version=None,
                 watcher_stale_seconds=60, processing_stale_seconds=600,
                 github_publication_state_path=None, watcher_probe_seconds=20.0,
                 watcher_sleep_fn=None):
        self.project_root = Path(project_root)
        self.mode_state_path = Path(mode_state_path) if mode_state_path else None
        self.running_release_version = str(running_release_version or '').strip() or None
        self.watcher_stale_seconds = int(watcher_stale_seconds)
        self.processing_stale_seconds = int(processing_stale_seconds)
        self.watcher_probe_seconds = max(0.0, float(watcher_probe_seconds))
        self.watcher_sleep_fn = watcher_sleep_fn or time.sleep
        configured_publication_state = (
            github_publication_state_path
            or os.environ.get('ENERGIE_GITHUB_PUBLICATION_STATE')
        )
        self.github_publication_state_path = (
            Path(configured_publication_state) if configured_publication_state else None
        )

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
    def _heartbeat_age(path, now):
        """Return watcher heartbeat age from its payload, not NAS/SMB metadata.

        The watcher writes the current Unix epoch into the heartbeat file.  File
        metadata can be cached independently across the NAS/Home Assistant mount,
        so mtime is only a legacy fallback when the payload is unavailable or
        invalid.
        """
        heartbeat_path = Path(path)
        try:
            raw = heartbeat_path.read_text(encoding='utf-8').strip()
            epoch = float(raw)
            age = now.timestamp() - epoch
            if age < -30.0:
                return None, 'content_epoch_future'
            return max(0.0, age), 'content_epoch'
        except (OSError, UnicodeError, ValueError, OverflowError):
            age = RuntimeCollector._file_age(heartbeat_path, now)
            return age, 'file_mtime_fallback' if age is not None else 'missing'

    @staticmethod
    def _read_heartbeat_epoch(path):
        try:
            return float(Path(path).read_text(encoding='utf-8').strip())
        except (OSError, UnicodeError, ValueError, OverflowError):
            return None

    def _watcher_liveness(self, path, now):
        """Clock-independent watcher liveness for NAS/HA cross-host mounts.

        QNAP and Home Assistant may have different wall clocks.  Absolute epoch
        comparison is therefore only a fast path when the clocks agree closely.
        When the payload looks stale or future-dated, actively observe one watcher
        pulse.  A changed heartbeat proves liveness without trusting either host's
        wall clock; no change remains fail-closed.
        """
        heartbeat_path = Path(path)
        first = self._read_heartbeat_epoch(heartbeat_path)
        if first is None:
            age = self._file_age(heartbeat_path, now)
            active = age is not None and age <= self.watcher_stale_seconds
            return {
                'active': active,
                'heartbeat_age_seconds': round(age, 1) if age is not None else None,
                'heartbeat_source': 'file_mtime_fallback' if age is not None else 'missing',
                'heartbeat_clock_skew_detected': False,
                'heartbeat_probe_seconds': 0.0,
            }

        raw_age = now.timestamp() - first
        if -30.0 <= raw_age <= self.watcher_stale_seconds:
            return {
                'active': True,
                'heartbeat_age_seconds': round(max(0.0, raw_age), 1),
                'heartbeat_source': 'content_epoch',
                'heartbeat_clock_skew_detected': False,
                'heartbeat_probe_seconds': 0.0,
            }

        if self.watcher_probe_seconds > 0:
            self.watcher_sleep_fn(self.watcher_probe_seconds)
        second = self._read_heartbeat_epoch(heartbeat_path)
        changed = second is not None and second != first
        if changed:
            return {
                'active': True,
                'heartbeat_age_seconds': 0.0,
                'heartbeat_source': 'content_pulse_probe',
                'heartbeat_clock_skew_detected': True,
                'heartbeat_probe_seconds': self.watcher_probe_seconds,
                'reported_clock_delta_seconds': round(raw_age, 1),
            }

        source = 'content_epoch' if raw_age > self.watcher_stale_seconds else 'content_epoch_future'
        return {
            'active': False,
            'heartbeat_age_seconds': round(max(0.0, raw_age), 1) if raw_age >= 0 else None,
            'heartbeat_source': source,
            'heartbeat_clock_skew_detected': abs(raw_age) > self.watcher_stale_seconds,
            'heartbeat_probe_seconds': self.watcher_probe_seconds,
            'heartbeat_probe_result': 'no_pulse',
            'reported_clock_delta_seconds': round(raw_age, 1),
        }

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
        watcher_liveness = self._watcher_liveness(heartbeat_path, now)
        atomic_path = inbox / 'atomic_app_swap_state.json'
        legacy_publisher_path = inbox / 'github_publisher_state.json'
        shared_publication_path = inbox / 'github_publication_state.json'
        installer_lock_path = inbox / '.installer.lock'
        atomic = self._read_json(atomic_path) or {}
        publication_contract = self._read_json(inbox / 'ha_publication_required.json') or {}

        # 32.4.18 canonical publication truth: prefer the shared state written by
        # the active HA publisher, then the HA-local state, and only then the
        # historical NAS publisher state. The selected payload is normalized so
        # Projectmanager health consumes one version-scoped contract.
        publication_path = shared_publication_path
        publication = self._read_json(shared_publication_path)
        if publication is None and self.github_publication_state_path is not None:
            publication_path = self.github_publication_state_path
            publication = self._read_json(publication_path)
        if publication is None:
            publication_path = legacy_publisher_path
            publication = self._read_json(legacy_publisher_path)
        publication = publication or {}
        remote_head = str(publication.get('remote_head') or '').strip()
        local_head = str(publication.get('local_head') or '').strip()
        exact_target_proof = publication.get('already_published') is True
        pushed_target_proof = bool(remote_head and local_head and remote_head == local_head)
        publication_proven = bool(
            publication.get('published') is True
            and publication.get('publication_contract_removed') is True
            and (exact_target_proof or pushed_target_proof)
        )
        if publication_proven:
            publication_status = 'published'
        elif publication.get('published') is not None and publication:
            publication_status = 'error'
        else:
            publication_status = publication.get('status')
        legacy_publisher = self._read_json(legacy_publisher_path) or {}
        return {
            'watcher': {
                **watcher_liveness,
                'heartbeat_path': str(heartbeat_path),
                'stale_after_seconds': self.watcher_stale_seconds,
            },
            'incoming': self._zip_snapshot(inbox / 'incoming', now=now),
            'processing': self._zip_snapshot(
                inbox / 'processing', now=now, stale_after=self.processing_stale_seconds,
            ),
            'installer_lock': {
                'active': installer_lock_path.exists(),
                'path': str(installer_lock_path),
                'age_seconds': self._file_age(installer_lock_path, now),
            },
            'atomic_swap': {
                'state': atomic.get('state'),
                'raw': atomic,
                'source': str(atomic_path),
                'exists': atomic_path.is_file(),
                'age_seconds': self._file_age(atomic_path, now),
            },
            'publisher': {
                'status': publication_status,
                'version': publication.get('version'),
                'message': publication.get('message'),
                'updated_at': publication.get('updated_at'),
                'source': str(publication_path),
                'exists': publication_path.is_file(),
                'age_seconds': self._file_age(publication_path, now),
                'owner': 'home_assistant' if publication_path != legacy_publisher_path else 'legacy_nas',
            },
            'github_publication': {
                'status': publication_status,
                'version': publication.get('version'),
                'contract_pending': bool(publication_contract),
                'contract_version': publication_contract.get('version'),
                'source': str(publication_path),
                'published': publication.get('published'),
                'remote_head': publication.get('remote_head'),
                'local_head': publication.get('local_head'),
                'publication_contract_removed': publication.get('publication_contract_removed'),
            },
            'legacy_publisher': {
                'status': legacy_publisher.get('status'),
                'version': legacy_publisher.get('version'),
                'message': legacy_publisher.get('message'),
                'source': str(legacy_publisher_path),
                'exists': legacy_publisher_path.is_file(),
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
