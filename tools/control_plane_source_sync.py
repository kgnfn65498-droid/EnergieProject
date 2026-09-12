#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

FILES = (
    'control_plane.py',
    'qnap_control_plane_bootstrap.py',
    'docker-compose.containerstation.yml',
)
SCHEMA = 'energie_control_plane_source_sync_v1'


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _atomic_copy(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise RuntimeError(f'onveilige/ontbrekende control-plane bron: {source}')
    if target.is_symlink():
        raise RuntimeError(f'onveilig control-plane doel: {target}')
    data = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(target.name + f'.tmp-{os.getpid()}')
    try:
        if temp.exists() or temp.is_symlink():
            temp.unlink()
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        try:
            with os.fdopen(fd, 'wb') as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            temp.unlink(missing_ok=True)
            raise
        os.chmod(temp, 0o644)
        os.replace(temp, target)
        os.chmod(target, 0o644)
    finally:
        temp.unlink(missing_ok=True)


def sync_control_plane_source(project_root: Path | str) -> dict:
    root = Path(project_root).resolve()
    source_root = root / 'App/tools/control_plane'
    target_root = root / 'Data/03_Systeem/Projectmanager/ControlPlane'
    if not source_root.is_dir() or source_root.is_symlink():
        raise RuntimeError('control-plane releasebron ontbreekt/onveilig')
    if target_root.exists() and (not target_root.is_dir() or target_root.is_symlink()):
        raise RuntimeError('control-plane systeemdoel is onveilig')
    target_root.mkdir(parents=True, exist_ok=True)

    changed: list[str] = []
    expected: dict[str, str] = {}
    for name in FILES:
        source = source_root / name
        target = target_root / name
        source_hash = _sha256(source)
        expected[name] = source_hash
        target_hash = _sha256(target) if target.is_file() and not target.is_symlink() else None
        if target_hash != source_hash or (target.stat().st_mode & 0o777 if target.exists() else None) != 0o644:
            _atomic_copy(source, target)
            changed.append(name)

    readback = {name: _sha256(target_root / name) for name in FILES}
    if readback != expected:
        raise RuntimeError('control-plane source sync readback mismatch')
    for name in FILES:
        target = target_root / name
        if target.is_symlink() or not target.is_file() or target.stat().st_mode & 0o777 != 0o644:
            raise RuntimeError(f'control-plane source sync mode/type mismatch: {name}')

    result = {
        'schema': SCHEMA,
        'status': 'GREEN',
        'files_total': len(FILES),
        'changed': changed,
        'readback_sha256': readback,
        'delete_performed': False,
        'target': str(target_root),
    }
    result_path = root / 'Inbox/logs/control_plane_source_sync_32.4.43.json'
    result_path.parent.mkdir(parents=True, exist_ok=True)
    temp = result_path.with_name(result_path.name + f'.tmp-{os.getpid()}')
    temp.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    os.replace(temp, result_path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    result = sync_control_plane_source(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
