from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

REQUEST_SCHEMA = 'energie_platformtest_run_request_v1'
RESULT_SCHEMA = 'energie_platformtest_run_result_v1'
ACTION = 'platformtest_run'
PROFILE = 'publisher_full_suite_v1'
SOURCE_SCHEMA = 'energie_platformtest_source_v1'
SOURCE_MANIFEST = '.energie-platformtest-source.json'


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
        fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.tmp-', dir=str(path.parent))
        temp = Path(temp_name)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
        finally:
            temp.unlink(missing_ok=True)

    @classmethod
    def _source_identity(cls, workspace: Path, candidate: str) -> str:
        manifest_path = workspace / SOURCE_MANIFEST
        manifest = cls._load(manifest_path)
        if manifest is None:
            raise RuntimeError('platformtest source manifest ontbreekt/ongeldig')
        if set(manifest) != {'schema', 'candidate_sha', 'source_sha256', 'git_commit_hex', 'files'}:
            raise RuntimeError('platformtest source manifest velden ongeldig')
        if manifest.get('schema') != SOURCE_SCHEMA or manifest.get('candidate_sha') != candidate:
            raise RuntimeError('platformtest source identity mismatch')
        expected_files = manifest.get('files')
        if not isinstance(expected_files, list):
            raise RuntimeError('platformtest source manifest files ongeldig')
        actual = []
        for path in sorted(workspace.rglob('*')):
            if path == manifest_path:
                continue
            if path.is_symlink():
                raise RuntimeError('platformtest source identity bevat symlink')
            if path.is_dir():
                continue
            if not path.is_file():
                raise RuntimeError('platformtest source identity bevat onveilig bestand')
            relative = path.relative_to(workspace).as_posix()
            mode = '100755' if path.stat().st_mode & 0o111 else '100644'
            actual.append({'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': path.stat().st_size, 'mode': mode})
        if actual != expected_files:
            raise RuntimeError('platformtest source identity mismatch')
        canonical = json.dumps(actual, separators=(',', ':'), sort_keys=True).encode()
        digest = hashlib.sha256(canonical).hexdigest()
        if manifest.get('source_sha256') != digest:
            raise RuntimeError('platformtest source identity digest mismatch')
        try:
            commit = bytes.fromhex(str(manifest.get('git_commit_hex') or ''))
        except ValueError as exc:
            raise RuntimeError('platformtest git commit proof ongeldig') from exc
        commit_id = hashlib.sha1(b'commit ' + str(len(commit)).encode() + b'\0' + commit).hexdigest()
        if commit_id != candidate:
            raise RuntimeError('platformtest git commit identity mismatch')
        tree_line = next((line for line in commit.splitlines() if line.startswith(b'tree ')), b'')
        expected_tree = tree_line[5:].decode('ascii', errors='ignore')
        if len(expected_tree) != 40 or cls._git_tree_sha(workspace, actual) != expected_tree:
            raise RuntimeError('platformtest git tree identity mismatch')
        return digest

    @staticmethod
    def _git_tree_sha(workspace: Path, entries: list[dict], prefix: str = '') -> str:
        children: dict[str, list[dict] | dict] = {}
        for entry in entries:
            relative = str(entry['path'])
            if prefix:
                if not relative.startswith(prefix + '/'):
                    continue
                relative = relative[len(prefix) + 1:]
            head, separator, _tail = relative.partition('/')
            if separator:
                children.setdefault(head, [])
            else:
                children[head] = entry
        raw = bytearray()
        for name, value in sorted(children.items(), key=lambda item: (item[0] + ('/' if isinstance(item[1], list) else '')).encode()):
            if isinstance(value, list):
                child_prefix = f'{prefix}/{name}' if prefix else name
                object_id = ConfiguredPlatformTestService._git_tree_sha(workspace, entries, child_prefix)
                mode = '40000'
            else:
                data = (workspace / value['path']).read_bytes()
                object_id = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
                mode = str(value['mode'])
            raw.extend(mode.encode() + b' ' + name.encode() + b'\0' + bytes.fromhex(object_id))
        data = bytes(raw)
        return hashlib.sha1(b'tree ' + str(len(data)).encode() + b'\0' + data).hexdigest()

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
        source_sha256 = self._source_identity(workspace, candidate)

        request_id = hashlib.sha256(f'{candidate}:{source_sha256}:{profile}'.encode('utf-8')).hexdigest()[:32]
        expected = {
            'schema': REQUEST_SCHEMA,
            'request_id': request_id,
            'action': ACTION,
            'candidate_sha': candidate,
            'source_sha256': source_sha256,
            'test_profile': profile,
        }

        result = self._load(self.result_path)
        if result and str(result.get('request_id') or '') == request_id:
            if (
                result.get('schema') != RESULT_SCHEMA
                or str(result.get('candidate_sha') or '').lower() != candidate
                or result.get('source_sha256') != source_sha256
                or result.get('test_profile') != profile
                or result.get('network_mode') != 'none'
                or result.get('production_modified') is not False
                or result.get('container_removed') is not True
                or re.fullmatch(r'sha256:[0-9a-f]{64}', str(result.get('image_id') or '').lower()) is None
                or (result.get('status') == 'GREEN' and (result.get('ok') is not True or result.get('exit_code') != 0))
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
            'source_sha256': source_sha256,
            'test_profile': profile, 'request_path': str(self.request_path),
        }
