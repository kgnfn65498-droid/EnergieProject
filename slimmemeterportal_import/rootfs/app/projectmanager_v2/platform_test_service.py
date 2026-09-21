from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

REQUEST_SCHEMA = 'energie_platformtest_run_request_v1'
RESULT_SCHEMA = 'energie_platformtest_run_result_v1'
ACTION = 'platformtest_run'
PROFILE = 'publisher_full_suite_v1'


class ConfiguredPlatformTestService:
    """Fixed-function bridge from Projectmanager to the local QNAP control-plane."""

    def __init__(self, project_root: Path | str):
        self.project_root = Path(project_root).resolve()
        self.request_path = self.project_root / 'Inbox/control_plane/requests/platformtest_run.json'
        self.result_path = self.project_root / 'Inbox/control_plane/results/platformtest_run.json'
        self.workspace_root = self.project_root / 'Data/03_Systeem/Projectmanager/Staging/PlatformTest'

    @staticmethod
    def _valid_sha(value: str) -> bool:
        return len(value) == 40 and all(ch in '0123456789abcdef' for ch in value)

    @staticmethod
    def _load(path: Path) -> dict | None:
        if not path.is_file() or path.is_symlink():
            return None
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError, UnicodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _atomic(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise RuntimeError(f'onveilig platformtest bridgepad: {path}')
        temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
        try:
            temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    def run(self, *, candidate_sha: str, test_profile: str = PROFILE) -> dict:
        candidate = str(candidate_sha or '').strip().lower()
        profile = str(test_profile or '').strip()
        if not self._valid_sha(candidate):
            raise RuntimeError('platformtest candidate_sha ongeldig')
        if profile != PROFILE:
            raise RuntimeError('platformtest test_profile niet toegestaan')

        workspace = self.workspace_root / candidate
        if workspace.is_symlink() or not workspace.is_dir():
            return {
                'status': 'PENDING', 'ok': None, 'executed': False,
                'reason': 'platformtest_workspace_not_ready',
                'candidate_sha': candidate, 'test_profile': profile,
            }

        request_id = hashlib.sha256(f'{candidate}:{profile}'.encode('utf-8')).hexdigest()[:32]
        expected = {
            'schema': REQUEST_SCHEMA,
            'request_id': request_id,
            'action': ACTION,
            'candidate_sha': candidate,
            'test_profile': profile,
        }

        result = self._load(self.result_path)
        if result and str(result.get('request_id') or '') == request_id:
            if (
                result.get('schema') != RESULT_SCHEMA
                or str(result.get('candidate_sha') or '').lower() != candidate
                or result.get('test_profile') != profile
                or result.get('network_mode') != 'none'
                or result.get('production_modified') is not False
            ):
                raise RuntimeError('platformtest resultaat identity/safety mismatch')
            return dict(result)

        pending = self._load(self.request_path)
        if pending is not None and pending != expected:
            raise RuntimeError('platformtest request conflicteert met bestaande pending request')
        if pending is None:
            self._atomic(self.request_path, expected)
        return {
            'status': 'PENDING', 'ok': None, 'executed': False,
            'request_id': request_id, 'candidate_sha': candidate,
            'test_profile': profile, 'request_path': str(self.request_path),
        }
