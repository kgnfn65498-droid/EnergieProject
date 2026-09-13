from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReleaseRecoveryService:
    """Bounded recovery analysis for the canonical release route.

    This service never deploys a ZIP, accepts an atomic swap, restarts a
    container, or bypasses approval. It only reconciles stale terminal bridge
    requests and reports the exact existing action needed next.
    """

    def __init__(self, project_root: Path | str, *, watcher_stale_seconds: int = 60):
        self.project_root = Path(project_root)
        self.inbox = self.project_root / 'Inbox'
        self.watcher_stale_seconds = max(5, int(watcher_stale_seconds))

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    def _version(self) -> str:
        for path in (self.project_root / 'App/VERSIE.txt', self.project_root / 'VERSIE.txt'):
            try:
                value = path.read_text(encoding='utf-8').strip()
            except OSError:
                continue
            if value:
                return value
        return ''

    def _watcher(self) -> dict[str, Any]:
        path = self.inbox / 'watcher_heartbeat.v2'
        if not path.is_file():
            path = self.inbox / '.watcher.heartbeat'
        try:
            epoch = float(path.read_text(encoding='utf-8').strip())
            age = max(0.0, time.time() - epoch)
        except (OSError, UnicodeError, ValueError, OverflowError):
            return {'active': False, 'reason': 'watcher_heartbeat_missing_or_invalid', 'path': str(path)}
        active = age <= self.watcher_stale_seconds
        return {
            'active': active,
            'reason': 'watcher_heartbeat_fresh' if active else 'watcher_heartbeat_stale',
            'age_seconds': round(age, 1),
            'path': str(path),
        }

    def _isolate_terminal_project_cr_request(self, version: str) -> bool:
        bridge = self.inbox / 'project_cr_local'
        request_path = bridge / 'request.json'
        request = self._load_json(request_path)
        if not request:
            return False
        result = self._load_json(bridge / 'result.json')
        same_result = bool(result and result.get('request_id') == request.get('request_id'))
        terminal_result = same_result and str(result.get('status') or '').upper() in {'GREEN', 'RED', 'FAILED'}
        stale_release = str(request.get('expected_runtime_version') or '') != str(version or '')
        if not (terminal_result or stale_release):
            return False
        quarantine = bridge / 'quarantine'
        quarantine.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        target = quarantine / f'request-{stamp}-{request.get("request_id") or "unknown"}.json'
        os.replace(request_path, target)
        return True

    def recover(self) -> dict[str, Any]:
        version = self._version()
        atomic = self._load_json(self.inbox / 'atomic_app_swap_state.json')
        hold = self._load_json(self.inbox / 'operating_mode/release_validation_hold.json')
        mode = self._load_json(self.inbox / 'operating_mode/operating_mode_state.json')
        watcher = self._watcher()
        isolated = self._isolate_terminal_project_cr_request(version)
        effective_mode = str(mode.get('effective_mode') or mode.get('base_mode') or mode.get('mode') or '')
        atomic_state = str(atomic.get('state') or '').upper()
        to_version = str(atomic.get('to_version') or '')
        return {
            'status': 'RECOVERY_ANALYZED',
            'version': version,
            'watcher': watcher,
            'atomic_state': atomic_state,
            'atomic_to_version': to_version,
            'release_hold_active': hold.get('active') is True,
            'effective_mode': effective_mode,
            'stale_project_cr_request_isolated': isolated,
            'needs_development': effective_mode != 'DEVELOPMENT',
            'needs_hold_cycle': atomic_state == 'LIVE_ACCEPTANCE' and (not to_version or to_version == version),
            'needs_watcher_recreate': watcher.get('active') is not True,
            'protected_action_required': 'watcher_recreate' if watcher.get('active') is not True else None,
            'canonical_release_route': 'ZIP -> Incoming/Home Assistant -> watcher -> installer -> live -> acceptance -> processed',
        }
