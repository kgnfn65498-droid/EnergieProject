from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any

RETENTION = 3
STORE_RELATIVE = Path('Data/03_Systeem/Projectmanager/ReleaseArtifacts')
REGISTRY_NAME = 'registry.json'


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _zip_green(path: Path) -> bool:
    try:
        if path.is_symlink() or not path.is_file():
            return False
        with zipfile.ZipFile(path, 'r') as archive:
            return archive.testzip() is None
    except Exception:
        return False


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError('unsafe registry path')
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=path.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _read_registry(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _entry_from_file(path: Path, *, official: bool, validated_at_epoch: float | None = None) -> dict[str, Any]:
    return {
        'name': path.name,
        'official_name': official,
        'sha256': _sha(path),
        'size': path.stat().st_size,
        'validated_at_epoch': float(validated_at_epoch or time.time()),
    }


def _archive_name(slot: int, original_name: str, sha256: str) -> str:
    return f'previous_{slot}__{Path(original_name).stem}__{sha256[:12]}.zip'


def retain_release_artifact(
    project_root: Path | str,
    source_zip: Path | str,
    *,
    expected_sha256: str,
    expected_size: int,
    retention: int = RETENTION,
) -> dict[str, Any]:
    root = Path(project_root)
    source = Path(source_zip)
    retention = max(1, int(retention))
    if source.is_symlink() or not source.is_file():
        raise RuntimeError('source release artifact missing or unsafe')
    if source.stat().st_size != int(expected_size):
        raise RuntimeError('source release artifact size mismatch')
    actual_sha = _sha(source)
    if actual_sha != str(expected_sha256).lower():
        raise RuntimeError('source release artifact sha mismatch')
    if not _zip_green(source):
        raise RuntimeError('source release artifact ZIP integrity RED')

    store = root / STORE_RELATIVE
    store.mkdir(parents=True, exist_ok=True)
    if store.is_symlink() or not store.is_dir():
        raise RuntimeError('release artifact store unsafe')
    registry_path = store / REGISTRY_NAME

    # Idempotent exact-current case.
    official_path = store / source.name
    if official_path.is_file() and not official_path.is_symlink():
        if _sha(official_path) == actual_sha and official_path.stat().st_size == int(expected_size) and _zip_green(official_path):
            current = _read_registry(registry_path)
            entries = current.get('entries') if isinstance(current.get('entries'), list) else []
            if entries and entries[0].get('sha256') == actual_sha and entries[0].get('name') == source.name:
                return {'status': 'GREEN', 'idempotent': True, 'store': str(store), 'registry': current}

    # First copy and verify new bytes before changing existing official/archive names.
    staged = store / ('.stage__' + source.name)
    if staged.exists():
        staged.unlink()
    shutil.copy2(source, staged)
    if staged.stat().st_size != int(expected_size) or _sha(staged) != actual_sha or not _zip_green(staged):
        staged.unlink(missing_ok=True)
        raise RuntimeError('staged release artifact verification failed')

    current = _read_registry(registry_path)
    previous_entries = current.get('entries') if isinstance(current.get('entries'), list) else []
    preserved: list[dict[str, Any]] = []

    # Recover valid registered entries from disk. Never trust registry identity without readback.
    for item in previous_entries:
        if not isinstance(item, dict):
            continue
        name = str(item.get('name') or '')
        if not name:
            continue
        path = store / name
        if path == staged or not path.is_file() or path.is_symlink():
            continue
        try:
            digest = _sha(path)
        except OSError:
            continue
        if digest != str(item.get('sha256') or '') or path.stat().st_size != int(item.get('size') or -1) or not _zip_green(path):
            continue
        if digest == actual_sha:
            continue
        preserved.append({**item, 'name': name, 'sha256': digest, 'size': path.stat().st_size})

    # Include a valid existing official file even if registry was stale/missing.
    if official_path.is_file() and not official_path.is_symlink():
        digest = _sha(official_path)
        if digest != actual_sha and _zip_green(official_path):
            if not any(e.get('sha256') == digest for e in preserved):
                preserved.insert(0, _entry_from_file(official_path, official=False))

    # Move old official/archives to deterministic previous slots. No deletion yet.
    candidates = preserved[:]
    physical_by_sha: dict[str, Path] = {}
    for item in candidates:
        path = store / str(item.get('name') or '')
        if path.is_file() and not path.is_symlink():
            physical_by_sha[str(item.get('sha256') or '')] = path

    temp_old_paths: list[Path] = []
    for digest, path in list(physical_by_sha.items()):
        tmp = store / f'.old__{digest[:12]}.zip'
        if path != tmp:
            if tmp.exists():
                tmp.unlink()
            os.replace(path, tmp)
            physical_by_sha[digest] = tmp
            temp_old_paths.append(tmp)

    os.replace(staged, official_path)
    if _sha(official_path) != actual_sha or official_path.stat().st_size != int(expected_size) or not _zip_green(official_path):
        raise RuntimeError('official release artifact readback failed')

    kept_previous: list[dict[str, Any]] = []
    for index, item in enumerate(candidates[: max(0, retention - 1)], start=1):
        digest = str(item.get('sha256') or '')
        src = physical_by_sha.get(digest)
        if src is None or not src.is_file():
            continue
        archive_name = _archive_name(index, str(item.get('name') or 'EnergieProject_previous.zip'), digest)
        dst = store / archive_name
        if dst.exists():
            if dst.is_symlink() or not dst.is_file() or _sha(dst) != digest:
                raise RuntimeError('archive retention destination conflict')
            src.unlink(missing_ok=True)
        else:
            os.replace(src, dst)
        kept_previous.append({
            **item,
            'name': archive_name,
            'official_name': False,
            'size': dst.stat().st_size,
            'sha256': digest,
        })

    now = time.time()
    official_entry = {
        'name': source.name,
        'official_name': True,
        'sha256': actual_sha,
        'size': int(expected_size),
        'validated_at_epoch': now,
    }
    pre_cleanup_entries = [official_entry] + kept_previous
    # Manifest/registry is committed and read back before any obsolete bytes are deleted.
    pre_registry = {
        'schema': 'energie_release_artifact_registry_v1',
        'retention': retention,
        'updated_at_epoch': now,
        'entries': pre_cleanup_entries,
    }
    _atomic_json(registry_path, pre_registry)
    readback = _read_registry(registry_path)
    if readback != pre_registry:
        raise RuntimeError('release artifact registry readback mismatch')

    keep_names = {entry['name'] for entry in pre_cleanup_entries}
    removed: list[str] = []
    for path in sorted(store.glob('*.zip')):
        if path.name in keep_names:
            continue
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('unsafe extra release artifact')
        path.unlink()
        removed.append(path.name)
    for path in sorted(store.glob('.old__*.zip')):
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('unsafe temporary release artifact')
        path.unlink()
        removed.append(path.name)

    final_registry = {
        **pre_registry,
        'cleanup_removed': removed,
        'entries': pre_cleanup_entries[:retention],
    }
    _atomic_json(registry_path, final_registry)
    if _read_registry(registry_path) != final_registry:
        raise RuntimeError('final release artifact registry readback mismatch')

    return {
        'status': 'GREEN',
        'idempotent': False,
        'store': str(store),
        'official': source.name,
        'official_sha256': actual_sha,
        'retention': retention,
        'entries': final_registry['entries'],
        'removed': removed,
        'registry': final_registry,
    }
