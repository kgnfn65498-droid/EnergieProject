#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import errno
import fcntl
import json
import os
import re
import secrets
import sys
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUEST_SCHEMA = 'energie_nas_container_cr_local_request_v1'
RESULT_SCHEMA = 'energie_nas_container_cr_local_result_v1'
OPERATION = 'nas_container_cr_create'
REQUEST_ID = re.compile(r'^[0-9a-f]{32}$')
VERSION = re.compile(r'^\d+(?:\.\d+)+$')


def _atomic_json(path: Path, payload: dict[str, Any], *, mode: int = 0o644) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(8)
    temp = path.with_name(f'.{path.name}.tmp-{os.getpid()}-{token}')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(temp), flags, mode)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
        os.chmod(path, mode)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _fixed_paths(root: Path) -> tuple[Path, Path]:
    bridge = root / 'Inbox' / 'nas_container_cr_local'
    return bridge / 'request.json', bridge / 'result.json'


def _regular_file(path: Path) -> bool:
    return path.is_file() and not path.is_symlink()


def _load_request(root: Path) -> dict[str, Any]:
    request_path, _ = _fixed_paths(root)
    if not _regular_file(request_path):
        raise RuntimeError('NAS CR request ontbreekt of is onveilig')
    try:
        value = json.loads(request_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError('NAS CR request is geen geldige JSON') from exc
    if not isinstance(value, dict):
        raise RuntimeError('NAS CR request moet een object zijn')
    allowed = {'schema', 'request_id', 'operation', 'expected_runtime_version', 'created_at', 'command_id'}
    required = {'schema', 'request_id', 'operation', 'expected_runtime_version', 'created_at'}
    if not required <= set(value) or set(value) - allowed:
        raise RuntimeError('NAS CR request bevat ontbrekende of onverwachte velden')
    if value.get('schema') != REQUEST_SCHEMA or value.get('operation') != OPERATION:
        raise RuntimeError('NAS CR request schema/operation ongeldig')
    if not REQUEST_ID.fullmatch(str(value.get('request_id') or '')):
        raise RuntimeError('NAS CR request_id ongeldig')
    command_id = str(value.get('command_id') or '').strip()
    if command_id and not REQUEST_ID.fullmatch(command_id):
        raise RuntimeError('NAS CR command_id ongeldig')
    expected = str(value.get('expected_runtime_version') or '')
    if not VERSION.fullmatch(expected):
        raise RuntimeError('NAS CR verwachte runtimeversie ongeldig')
    actual = (root / 'App' / 'VERSIE.txt').read_text(encoding='utf-8').strip()
    if expected != actual:
        raise RuntimeError(f'NAS CR release mismatch: verwacht {expected}, actief {actual}')
    return value



@contextlib.contextmanager
def _operation_lock(root: Path):
    """Cross-watcher single-flight lock held outside the writable mailbox.

    The watcher/bootstrap owns ``Inbox`` and pre-creates this permanent lock
    inode.  Mailbox writers can therefore not unlink/rename the lock while an
    executor is active.  Kernel flock survives watcher-shell restarts and is
    released automatically when the executor exits/crashes.
    """
    root = Path(root)
    lock = root / 'Inbox' / '.nas-container-cr.operation.lock'
    if lock.is_symlink() or not lock.is_file():
        raise OSError(errno.EINVAL, 'NAS CR operation lock ontbreekt of is onveilig', str(lock))
    flags = os.O_RDWR
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
    fd = os.open(str(lock), flags)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise OSError(errno.EINVAL, 'NAS CR operation lock is not a regular file', str(lock))
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)

def execute(root: Path) -> dict[str, Any]:
    root = Path(root).resolve()
    request_path, result_path = _fixed_paths(root)
    bridge = request_path.parent
    with _operation_lock(root) as acquired:
        if not acquired:
            return {
                'schema': RESULT_SCHEMA,
                'status': 'ALREADY_RUNNING',
                'ok': None,
                'executed': False,
            }
        return _execute_locked(root, request_path, result_path)


def _execute_locked(root: Path, request_path: Path, result_path: Path) -> dict[str, Any]:
    request: dict[str, Any] | None = None
    request_id = ''
    command_id = ''
    try:
        # Preserve only validated correlation identifiers for RED evidence even
        # when the stricter request validator rejects a later field (for example
        # a stale release). This keeps the original executor error diagnosable.
        if _regular_file(request_path):
            try:
                raw_request = json.loads(request_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                raw_request = None
            if isinstance(raw_request, dict):
                raw_request_id = str(raw_request.get('request_id') or '')
                raw_command_id = str(raw_request.get('command_id') or '')
                if REQUEST_ID.fullmatch(raw_request_id):
                    request_id = raw_request_id
                if REQUEST_ID.fullmatch(raw_command_id):
                    command_id = raw_command_id
        request = _load_request(root)
        request_id = str(request['request_id'])
        command_id = str(request.get('command_id') or '')
        pm = root / 'App' / 'slimmemeterportal_import' / 'rootfs' / 'app' / 'projectmanager_v2'
        if not pm.is_dir():
            raise RuntimeError('ProjectmanagerV2 bronmap ontbreekt')
        sys.path.insert(0, str(pm))
        from docker_engine_unix_client import DockerEngineUnixClient
        from nas_container_cr_service import NasContainerCrService

        result = NasContainerCrService(root, DockerEngineUnixClient()).create()
        expected = str(request['expected_runtime_version'])
        if result.get('version') != expected:
            raise RuntimeError('NAS CR resultaatversie wijkt af van request')
        if result.get('production_containers_changed') is not False:
            raise RuntimeError('NAS CR kon onveranderde productiecontainers niet bewijzen')
        payload = {
            'schema': RESULT_SCHEMA,
            'request_id': request_id,
            'command_id': command_id,
            'status': 'GREEN',
            'ok': True,
            'version': expected,
            'production_containers_changed': False,
            'backup_dir': result.get('backup_dir'),
            'zip': result.get('zip'),
            'sha256_file': result.get('sha256_file'),
            'verify_file': result.get('verify_file'),
            'sha256': result.get('sha256'),
            'retention': result.get('retention'),
            'completed_at': datetime.now(timezone.utc).isoformat(),
        }
        _atomic_json(result_path, payload)
        return payload
    except Exception as exc:
        payload = {
            'schema': RESULT_SCHEMA,
            'request_id': request_id,
            'command_id': command_id,
            'status': 'RED',
            'ok': False,
            'production_containers_changed': None,
            'error': str(exc),
            'completed_at': datetime.now(timezone.utc).isoformat(),
        }
        _atomic_json(result_path, payload)
        raise
    finally:
        # Remove only the exact regular request this run consumed. Result remains as evidence.
        if request is not None and _regular_file(request_path):
            try:
                current = json.loads(request_path.read_text(encoding='utf-8'))
                if current.get('request_id') == request.get('request_id'):
                    request_path.unlink()
            except (OSError, json.JSONDecodeError, AttributeError):
                pass


def main() -> int:
    parser = argparse.ArgumentParser(description='Fixed local NAS Container CR executor')
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    try:
        result = execute(Path(args.root))
        if result.get('status') == 'ALREADY_RUNNING':
            print('NAS_CONTAINER_CR_LOCAL_ALREADY_RUNNING')
        return 0
    except Exception as exc:
        print(f'NAS_CONTAINER_CR_LOCAL_RED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
