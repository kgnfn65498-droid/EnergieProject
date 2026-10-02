from __future__ import annotations
from system_path_contract import project_system_path

import hashlib
import json
import os
import re
import tempfile
import time
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
        self.workspace_root = self.project_root / 'Data/03_Systeem/Projectmanager/Staging/PlatformTest'

    @property
    def request_path(self):
        return project_system_path(self.project_root, 'Inbox/control_plane/requests/platformtest_run.json')

    @property
    def result_path(self):
        return project_system_path(self.project_root, 'Inbox/control_plane/results/platformtest_run.json')

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


PREPARED_REQUEST_SCHEMA = 'energie_prepared_job_request_v2'
PREPARED_AUTH_SCHEMA = 'energie_prepared_job_authorization_v1'
PREPARED_MANIFEST_SCHEMA = 'energie_prepared_job_manifest_v1'
PREPARED_RESULT_SCHEMA = 'energie_prepared_job_result_v2'
PREPARED_ACTION = 'prepared_job_run'
PREPARED_OPERATIONS = {'AUDIT', 'TEST', 'BUILD'}
PREPARED_ID_RE = re.compile(r'^[0-9a-f]{32}$')
PREPARED_SHA_RE = re.compile(r'^[0-9a-f]{64}$')
PREPARED_VERSION_RE = re.compile(r'^[0-9]+[.][0-9]+[.][0-9]+$')
PREPARED_LEASE_SECONDS = 900


class ConfiguredPreparedJobService:
    """Typed PM bridge to the bounded prepared-job executor."""

    def __init__(self, project_root: Path | str):
        self.project_root = Path(project_root).resolve()
        self.jobs_root = self.project_root / 'Data/03_Systeem/Projectmanager/Staging/PreparedJobs'
        self.artifacts_root = self.project_root / 'Data/03_Systeem/Projectmanager/ReleaseArtifacts'

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open('rb') as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _canonical(payload: dict) -> bytes:
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')

    @staticmethod
    def _load_json(path: Path) -> dict | None:
        if path.is_symlink() or not path.is_file():
            return None
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    @staticmethod
    def _write_immutable_json(path: Path, payload: dict, *, mode: int = 0o644) -> None:
        if path.is_symlink():
            raise RuntimeError('prepared_job unsafe symlink target')
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = ConfiguredPreparedJobService._load_json(path)
        if existing is not None:
            if existing != payload:
                raise RuntimeError('prepared_job immutable identity conflict')
            return
        if path.exists():
            raise RuntimeError('prepared_job existing non-JSON target')
        raw = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(raw)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(path, mode)
        except Exception:
            try:
                path.unlink()
            except OSError:
                pass
            raise

    def _runtime_path(self, kind: str, request_id: str) -> Path:
        return project_system_path(
            self.project_root,
            f'Inbox/control_plane/{kind}/prepared_job_run.{request_id}.json',
        )

    def _live_release(self) -> str:
        path = self.project_root / 'App/VERSIE.txt'
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('prepared_job live release authority missing/unsafe')
        value = path.read_text(encoding='utf-8').strip()
        if PREPARED_VERSION_RE.fullmatch(value) is None:
            raise RuntimeError('prepared_job live release invalid')
        return value

    @staticmethod
    def _result_exact(result: dict, request: dict) -> bool:
        return bool(
            result.get('schema') == PREPARED_RESULT_SCHEMA
            and result.get('action') == PREPARED_ACTION
            and result.get('request_id') == request['request_id']
            and result.get('task_id') == request['task_id']
            and result.get('operation') == request['operation']
            and result.get('target_release') == request['target_release']
            and result.get('predecessor_release') == request['predecessor_release']
            and result.get('predecessor_sha256') == request['predecessor_sha256']
            and result.get('runner_sha256') == request['runner_sha256']
            and result.get('manifest_sha256') == request['manifest_sha256']
            and result.get('authorization_sha256') == request['authorization_sha256']
            and result.get('network_mode') == 'none'
            and result.get('project_mount') == 'read_only'
            and result.get('production_modified') is False
            and result.get('container_removed') is True
        )

    def run(
        self,
        *,
        task: dict,
        artifact_path: str,
        artifact_sha256: str,
        target_release: str,
        operation: str,
    ) -> dict:
        task = task if isinstance(task, dict) else {}
        task_id = str(task.get('id') or '').strip()
        if not task_id or task.get('mode') != 'DEVELOPMENT' or task.get('status') != 'ACTIVE':
            raise RuntimeError('prepared_job active DEVELOPMENT task required')

        operation = str(operation or '').strip().upper()
        if operation not in PREPARED_OPERATIONS:
            raise RuntimeError('prepared_job operation invalid')
        target_release = str(target_release or '').strip()
        if PREPARED_VERSION_RE.fullmatch(target_release) is None:
            raise RuntimeError('prepared_job target release invalid')
        runner_sha = str(artifact_sha256 or '').strip().lower()
        if PREPARED_SHA_RE.fullmatch(runner_sha) is None:
            raise RuntimeError('prepared_job runner SHA invalid')

        relative = Path(str(artifact_path or '').replace('\\', '/'))
        if relative.is_absolute() or '..' in relative.parts or relative.name != 'runner.py':
            raise RuntimeError('prepared_job runner path invalid')
        runner = (self.project_root / relative).resolve()
        jobs_root = self.jobs_root.resolve()
        if runner.parent.parent != jobs_root or PREPARED_ID_RE.fullmatch(runner.parent.name) is None:
            raise RuntimeError('prepared_job runner path outside bounded job root')
        request_id = runner.parent.name
        if runner.is_symlink() or not runner.is_file() or self._sha256(runner) != runner_sha:
            raise RuntimeError('prepared_job runner identity mismatch')

        predecessor_release = self._live_release()
        predecessor = self.artifacts_root / f'EnergieProject_v{predecessor_release}.zip'
        if predecessor.is_symlink() or not predecessor.is_file():
            raise RuntimeError('prepared_job predecessor artifact missing/unsafe')
        predecessor_sha = self._sha256(predecessor)

        manifest_path = runner.parent / 'job_manifest.json'
        manifest = self._load_json(manifest_path)
        expected_manifest = {
            'schema': PREPARED_MANIFEST_SCHEMA,
            'request_id': request_id,
            'task_id': task_id,
            'operation': operation,
            'target_release': target_release,
            'predecessor_release': predecessor_release,
            'predecessor_sha256': predecessor_sha,
            'runner_sha256': runner_sha,
        }
        if manifest != expected_manifest:
            raise RuntimeError('prepared_job manifest identity mismatch')
        manifest_sha = self._sha256(manifest_path)

        issued = time.time()
        authorization = {
            **expected_manifest,
            'schema': PREPARED_AUTH_SCHEMA,
            'status': 'AUTHORIZED',
            'issued_by': 'projectmanager',
            'issued_at_epoch': issued,
            'expires_at_epoch': issued + PREPARED_LEASE_SECONDS,
        }
        authorization_sha = hashlib.sha256(self._canonical(authorization)).hexdigest()
        authorization['authorization_sha256'] = authorization_sha
        request = {
            **expected_manifest,
            'schema': PREPARED_REQUEST_SCHEMA,
            'action': PREPARED_ACTION,
            'manifest_sha256': manifest_sha,
            'authorization_sha256': authorization_sha,
        }

        result_path = self._runtime_path('results', request_id)
        result = self._load_json(result_path)
        if result is not None:
            if not self._result_exact(result, request):
                raise RuntimeError('prepared_job result identity/safety mismatch')
            return dict(result)

        auth_path = self._runtime_path('authorizations', request_id)
        claim_path = self._runtime_path('claims', request_id)
        existing_claim = self._load_json(claim_path)
        if existing_claim is not None:
            if existing_claim != authorization:
                raise RuntimeError('prepared_job claimed authorization identity mismatch')
        else:
            self._write_immutable_json(auth_path, authorization, mode=0o644)

        request_path = self._runtime_path('requests', request_id)
        self._write_immutable_json(request_path, request, mode=0o644)
        return {
            'status': 'PENDING',
            'ok': None,
            'executed': False,
            'awaiting_executor': True,
            'request_id': request_id,
            'task_id': task_id,
            'operation': operation,
            'target_release': target_release,
            'predecessor_release': predecessor_release,
            'predecessor_sha256': predecessor_sha,
            'runner_sha256': runner_sha,
            'manifest_sha256': manifest_sha,
            'authorization_sha256': authorization_sha,
            'request_path': str(request_path),
        }
