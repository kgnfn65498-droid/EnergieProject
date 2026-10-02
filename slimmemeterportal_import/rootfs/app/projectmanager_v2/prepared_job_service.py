from __future__ import annotations
from system_path_contract import project_system_path

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path

REQUEST_SCHEMA = 'energie_prepared_job_request_v2'
AUTH_SCHEMA = 'energie_prepared_job_authorization_v1'
MANIFEST_SCHEMA = 'energie_prepared_job_manifest_v1'
RESULT_SCHEMA = 'energie_prepared_job_result_v2'
ACTION = 'prepared_job_run'
OPERATIONS = {'AUDIT', 'TEST', 'BUILD'}
REQUEST_ID_RE = re.compile(r'^[0-9a-f]{32}$')
SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
VERSION_RE = re.compile(r'^[0-9]+[.][0-9]+[.][0-9]+$')
LEASE_SECONDS = 900


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def _load(path: Path) -> dict | None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _write_immutable(path: Path, payload: dict, *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError('prepared_job_path_symlink')
    if path.exists():
        if _load(path) != payload:
            raise RuntimeError('prepared_job_existing_identity_conflict')
        return
    fd, temp_name = tempfile.mkstemp(prefix=f'.{path.name}.tmp-', dir=str(path.parent))
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp, mode)
        try:
            os.link(temp, path)
        except FileExistsError:
            if _load(path) != payload:
                raise RuntimeError('prepared_job_publish_conflict')
        os.chmod(path, mode)
    finally:
        temp.unlink(missing_ok=True)


def _hex(value: str, regex, label: str) -> str:
    value = str(value or '').strip().lower()
    if not regex.fullmatch(value):
        raise RuntimeError(label + '_invalid')
    return value


class ConfiguredPreparedJobService:
    """Typed PM->ControlPlane bridge for bounded AUDIT/TEST/BUILD jobs."""

    def __init__(self, project_root: Path | str):
        self.project_root = Path(project_root).resolve()
        self.jobs = self.project_root / 'Data/03_Systeem/Projectmanager/Staging/PreparedJobs'
        self.artifacts = self.project_root / 'Data/03_Systeem/Projectmanager/ReleaseArtifacts'

    def _runtime_path(self, group: str, request_id: str) -> Path:
        return project_system_path(
            self.project_root,
            f'Inbox/control_plane/{group}/prepared_job_run.{request_id}.json',
        )

    @staticmethod
    def _result_exact(result: dict, request: dict) -> bool:
        return bool(
            result.get('schema') == RESULT_SCHEMA
            and result.get('action') == ACTION
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
        request_id: str,
        operation: str,
        target_release: str,
        predecessor_release: str,
        predecessor_sha256: str,
        runner_sha256: str,
        manifest_sha256: str,
    ) -> dict:
        request_id = _hex(request_id, REQUEST_ID_RE, 'prepared_job_request_id')
        operation = str(operation or '').strip().upper()
        if operation not in OPERATIONS:
            raise RuntimeError('prepared_job_operation_invalid')
        target_release = str(target_release or '').strip()
        predecessor_release = str(predecessor_release or '').strip()
        if not VERSION_RE.fullmatch(target_release) or not VERSION_RE.fullmatch(predecessor_release):
            raise RuntimeError('prepared_job_release_identity_invalid')
        predecessor_sha256 = _hex(predecessor_sha256, SHA256_RE, 'prepared_job_predecessor_sha')
        runner_sha256 = _hex(runner_sha256, SHA256_RE, 'prepared_job_runner_sha')
        manifest_sha256 = _hex(manifest_sha256, SHA256_RE, 'prepared_job_manifest_sha')

        task = task if isinstance(task, dict) else {}
        task_id = str(task.get('id') or '').strip()
        if not task_id or task.get('mode') != 'DEVELOPMENT' or task.get('status') != 'ACTIVE':
            raise RuntimeError('prepared_job_active_development_task_required')

        live_path = self.project_root / 'App/VERSIE.txt'
        if live_path.is_symlink() or not live_path.is_file():
            raise RuntimeError('prepared_job_live_release_missing')
        if live_path.read_text(encoding='utf-8').strip() != predecessor_release:
            raise RuntimeError('prepared_job_live_predecessor_mismatch')

        predecessor = self.artifacts / f'EnergieProject_v{predecessor_release}.zip'
        if predecessor.is_symlink() or not predecessor.is_file() or _sha(predecessor) != predecessor_sha256:
            raise RuntimeError('prepared_job_predecessor_artifact_mismatch')

        job = self.jobs / request_id
        runner = job / 'runner.py'
        manifest = job / 'job_manifest.json'
        if job.is_symlink() or not job.is_dir() or runner.is_symlink() or not runner.is_file():
            raise RuntimeError('prepared_job_runner_missing_or_unsafe')
        if manifest.is_symlink() or not manifest.is_file():
            raise RuntimeError('prepared_job_manifest_missing_or_unsafe')
        if _sha(runner) != runner_sha256 or _sha(manifest) != manifest_sha256:
            raise RuntimeError('prepared_job_input_sha_mismatch')

        expected_manifest = {
            'schema': MANIFEST_SCHEMA,
            'request_id': request_id,
            'task_id': task_id,
            'operation': operation,
            'target_release': target_release,
            'predecessor_release': predecessor_release,
            'predecessor_sha256': predecessor_sha256,
            'runner_sha256': runner_sha256,
        }
        if _load(manifest) != expected_manifest:
            raise RuntimeError('prepared_job_manifest_content_mismatch')

        issued = time.time()
        authorization = {
            **expected_manifest,
            'schema': AUTH_SCHEMA,
            'status': 'AUTHORIZED',
            'issued_by': 'projectmanager',
            'issued_at_epoch': issued,
            'expires_at_epoch': issued + LEASE_SECONDS,
        }
        authorization_sha256 = hashlib.sha256(_canonical(authorization)).hexdigest()
        authorization['authorization_sha256'] = authorization_sha256

        request = {
            **expected_manifest,
            'schema': REQUEST_SCHEMA,
            'action': ACTION,
            'manifest_sha256': manifest_sha256,
            'authorization_sha256': authorization_sha256,
        }

        result_path = self._runtime_path('results', request_id)
        result = _load(result_path)
        if result is not None:
            if not self._result_exact(result, request):
                raise RuntimeError('prepared_job_result_identity_or_safety_mismatch')
            return dict(result)

        claim = _load(self._runtime_path('claims', request_id))
        if claim is not None and claim != authorization:
            raise RuntimeError('prepared_job_claim_identity_conflict')

        if claim is None:
            _write_immutable(self._runtime_path('authorizations', request_id), authorization, mode=0o644)
        _write_immutable(self._runtime_path('requests', request_id), request, mode=0o644)

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
            'predecessor_sha256': predecessor_sha256,
            'runner_sha256': runner_sha256,
            'manifest_sha256': manifest_sha256,
            'authorization_sha256': authorization_sha256,
        }
