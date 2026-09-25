#!/usr/bin/env python3
from __future__ import annotations
from system_path_contract import project_system_path

import argparse
import hashlib
import json
import os
import shutil
import stat
import time
import zipfile
from pathlib import Path
from typing import Any

SCHEMA = 'energie_release_ingress_recovery_v1'
DEFAULT_STALE_SECONDS = 600
_ALLOWED_LOCK_FILES = {'owner.json', 'heartbeat'}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f'unsafe symlink evidence path: {path}')
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write('\n')
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _regular_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError(f'unsafe recovery directory: {path}')
    result: list[Path] = []
    for item in path.glob('*.zip'):
        st = item.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise RuntimeError(f'unsafe release item: {item}')
        result.append(item)
    return sorted(result, key=lambda p: p.name)


def _age_seconds(path: Path, now: float) -> float:
    try:
        return max(0.0, now - path.stat().st_mtime)
    except FileNotFoundError:
        return float('inf')


def _zip_integral(path: Path) -> bool:
    try:
        with zipfile.ZipFile(path, 'r') as archive:
            return archive.testzip() is None
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return False


def _installer_owner_state(lock: Path) -> str:
    owner = lock / 'owner.json'
    try:
        st = owner.lstat()
    except FileNotFoundError:
        return 'absent'
    except OSError:
        return 'unsafe'
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return 'unsafe'
    try:
        payload = json.loads(owner.read_text(encoding='utf-8'))
        pid = int(payload.get('pid')) if isinstance(payload, dict) else 0
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return 'unsafe'
    if pid <= 1:
        return 'unsafe'
    return 'alive' if (Path('/proc') / str(pid)).is_dir() else 'dead'


def _lock_freshness(lock: Path, *, now: float, stale_seconds: int) -> tuple[str, float]:
    try:
        st = lock.lstat()
    except FileNotFoundError:
        return 'absent', float('inf')
    except OSError:
        return 'unsafe', 0.0
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        return 'unsafe', 0.0
    owner_state = _installer_owner_state(lock)
    if owner_state == 'unsafe':
        return 'unsafe', 0.0
    if owner_state == 'alive':
        return 'owner_alive', 0.0
    heartbeat = lock / 'heartbeat'
    newest_epoch = st.st_mtime
    try:
        hb_st = heartbeat.lstat()
    except FileNotFoundError:
        hb_st = None
    except OSError:
        return 'unsafe', 0.0
    if hb_st is not None:
        if stat.S_ISLNK(hb_st.st_mode) or not stat.S_ISREG(hb_st.st_mode):
            return 'unsafe', 0.0
        newest_epoch = max(newest_epoch, hb_st.st_mtime)
        try:
            value = float(heartbeat.read_text(encoding='utf-8').strip())
        except (OSError, ValueError):
            value = 0.0
        if 0 < value <= now + 300:
            newest_epoch = max(newest_epoch, value)
    age = max(0.0, now - newest_epoch)
    return ('fresh' if age < stale_seconds else 'stale'), age


def _remove_stale_lock(lock: Path) -> None:
    if lock.is_symlink() or not lock.is_dir():
        raise RuntimeError('installer lock is not a regular directory')
    names = {p.name for p in lock.iterdir()}
    unexpected = sorted(names - _ALLOWED_LOCK_FILES)
    if unexpected:
        raise RuntimeError('installer lock contains unexpected entries: ' + ','.join(unexpected))
    for name in sorted(names):
        path = lock / name
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise RuntimeError(f'unsafe installer lock entry: {name}')
        path.unlink()
    lock.rmdir()


def _unique_destination(directory: Path, name: str, suffix: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    stem = name[:-4] if name.lower().endswith('.zip') else name
    candidate = directory / f'{stem}.{suffix}.zip'
    counter = 1
    while candidate.exists():
        candidate = directory / f'{stem}.{suffix}.{counter}.zip'
        counter += 1
    return candidate


def _write_result(root: Path, result: dict[str, Any]) -> dict[str, Any]:
    path = project_system_path(root, 'Inbox/logs/release_ingress_recovery.json')
    semantic = {'schema': SCHEMA, **result}
    try:
        existing = json.loads(path.read_text(encoding='utf-8')) if path.is_file() and not path.is_symlink() else None
    except (OSError, UnicodeError, json.JSONDecodeError):
        existing = None
    if isinstance(existing, dict):
        previous_semantic = {key: value for key, value in existing.items() if key != 'observed_at_epoch'}
        if previous_semantic == semantic:
            return existing
    payload = {
        'schema': SCHEMA,
        'observed_at_epoch': int(time.time()),
        **result,
    }
    _atomic_json(path, payload)
    return payload


def reconcile(project_root: Path | str, *, stale_seconds: int = DEFAULT_STALE_SECONDS, now: float | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    now_value = float(time.time() if now is None else now)
    if stale_seconds < 30:
        raise ValueError('stale_seconds must be at least 30')
    incoming = root / 'Inbox/incoming'
    processing = root / 'Inbox/processing'
    failed = root / 'Inbox/failed'
    for path in (incoming, processing, failed, project_system_path(root, 'Inbox/logs')):
        if path.exists() and (path.is_symlink() or not path.is_dir()):
            raise RuntimeError(f'unsafe recovery directory: {path}')
        path.mkdir(parents=True, exist_ok=True)

    incoming_items = _regular_files(incoming)
    processing_items = _regular_files(processing)
    lock = root / 'Inbox/.installer.lock'
    lock_state, lock_age = _lock_freshness(lock, now=now_value, stale_seconds=stale_seconds)
    if lock_state == 'unsafe':
        return _write_result(root, {'status': 'BLOCKED', 'reason': 'installer_lock_unsafe'})
    if lock_state == 'owner_alive':
        return _write_result(root, {
            'status': 'WAITING', 'reason': 'installer_owner_alive',
        })
    if lock_state == 'fresh':
        return _write_result(root, {
            'status': 'WAITING', 'reason': 'installer_lock_fresh',
            'installer_lock_age_seconds': round(lock_age, 3),
        })

    # Different active release candidates are never resolved by guessing.
    if len(incoming_items) > 1:
        hashes = {item.name: _sha256(item) for item in incoming_items}
        if len(set(hashes.values())) != 1:
            return _write_result(root, {
                'status': 'BLOCKED', 'reason': 'multiple_distinct_incoming', 'incoming_sha256': hashes,
            })
        if not all(_zip_integral(item) for item in incoming_items):
            return _write_result(root, {
                'status': 'WAITING', 'reason': 'identical_incoming_not_integral',
                'incoming': [item.name for item in incoming_items],
            })
        canonical = incoming_items[0]
        moved: list[str] = []
        for duplicate in incoming_items[1:]:
            dest = _unique_destination(failed / 'duplicates', duplicate.name, f'duplicate-{hashes[duplicate.name][:12]}')
            os.replace(duplicate, dest)
            moved.append(str(dest.relative_to(root)))
        return _write_result(root, {
            'status': 'RECOVERED', 'action': 'DEDUPLICATED_INCOMING',
            'canonical': str(canonical.relative_to(root)), 'quarantined': moved,
        })

    # More than one Processing item is ambiguous and must remain untouched.
    if len(processing_items) > 1:
        return _write_result(root, {
            'status': 'BLOCKED', 'reason': 'multiple_processing_items',
            'processing': [p.name for p in processing_items],
        })

    if processing_items:
        item = processing_items[0]
        age = _age_seconds(item, now_value)
        if lock_state == 'stale':
            if age < stale_seconds:
                return _write_result(root, {
                    'status': 'WAITING', 'reason': 'processing_fresh_despite_stale_lock',
                    'processing_age_seconds': round(age, 3), 'installer_lock_age_seconds': round(lock_age, 3),
                })
            if incoming_items:
                return _write_result(root, {'status': 'BLOCKED', 'reason': 'incoming_and_orphan_processing_conflict'})
            _remove_stale_lock(lock)
            target = incoming / item.name
            if target.exists():
                return _write_result(root, {'status': 'BLOCKED', 'reason': 'processing_requeue_target_exists'})
            os.replace(item, target)
            return _write_result(root, {
                'status': 'RECOVERED', 'action': 'RECOVERED_STALE_LOCK_AND_PROCESSING',
                'requeued': str(target.relative_to(root)),
            })
        if lock_state == 'absent':
            if age < stale_seconds:
                return _write_result(root, {
                    'status': 'WAITING', 'reason': 'processing_recent_without_lock',
                    'processing_age_seconds': round(age, 3),
                })
            if incoming_items:
                return _write_result(root, {'status': 'BLOCKED', 'reason': 'incoming_and_orphan_processing_conflict'})
            target = incoming / item.name
            if target.exists():
                return _write_result(root, {'status': 'BLOCKED', 'reason': 'processing_requeue_target_exists'})
            os.replace(item, target)
            return _write_result(root, {
                'status': 'RECOVERED', 'action': 'REQUEUED_ORPHAN_PROCESSING',
                'requeued': str(target.relative_to(root)),
            })

    if lock_state == 'stale':
        _remove_stale_lock(lock)
        return _write_result(root, {
            'status': 'RECOVERED', 'action': 'REMOVED_STALE_INSTALLER_LOCK',
            'installer_lock_age_seconds': round(lock_age, 3),
        })

    return _write_result(root, {
        'status': 'READY' if incoming_items else 'WAITING',
        'reason': 'single_incoming_ready' if incoming_items else 'release_ingress_idle',
    })


def quarantine_corrupt(project_root: Path | str, name: str, *, stale_seconds: int = DEFAULT_STALE_SECONDS, now: float | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if stale_seconds < 30:
        raise ValueError('stale_seconds must be at least 30')
    if not name or Path(name).name != name or '/' in name or '\\' in name:
        raise ValueError('unsafe incoming filename')
    source = root / 'Inbox/incoming' / name
    if not source.exists() or source.is_symlink() or not source.is_file():
        raise RuntimeError('incoming corrupt candidate missing/unsafe')
    now_value = float(time.time() if now is None else now)
    if _age_seconds(source, now_value) < stale_seconds:
        return _write_result(root, {
            'status': 'WAITING', 'reason': 'corrupt_candidate_not_stale', 'source_name': name,
        })
    destination = _unique_destination(root / 'Inbox/failed/corrupt', name, 'corrupt')
    os.replace(source, destination)
    return _write_result(root, {
        'status': 'RECOVERED', 'action': 'QUARANTINED_CORRUPT',
        'source_name': name, 'quarantined': str(destination.relative_to(root)),
        'sha256': _sha256(destination),
    })


def main() -> int:
    parser = argparse.ArgumentParser(description='Bounded autonomous release-ingress recovery')
    sub = parser.add_subparsers(dest='command', required=True)
    reconcile_p = sub.add_parser('reconcile')
    reconcile_p.add_argument('--root', required=True)
    reconcile_p.add_argument('--stale-seconds', type=int, default=DEFAULT_STALE_SECONDS)
    corrupt_p = sub.add_parser('quarantine-corrupt')
    corrupt_p.add_argument('--root', required=True)
    corrupt_p.add_argument('--name', required=True)
    corrupt_p.add_argument('--stale-seconds', type=int, default=DEFAULT_STALE_SECONDS)
    args = parser.parse_args()
    if args.command == 'reconcile':
        result = reconcile(Path(args.root), stale_seconds=args.stale_seconds)
    else:
        result = quarantine_corrupt(Path(args.root), args.name, stale_seconds=args.stale_seconds)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if result.get('status') == 'BLOCKED':
        return 2
    if args.command == 'quarantine-corrupt' and result.get('status') == 'WAITING':
        return 3
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
