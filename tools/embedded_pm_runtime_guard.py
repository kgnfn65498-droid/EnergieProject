#!/usr/bin/env python3
from __future__ import annotations
from system_path_contract import project_system_path

import argparse
import hashlib
import json
import stat
import time
from pathlib import Path


def _fingerprint_tree(root: Path) -> str:
    base = Path(root)
    digest = hashlib.sha256()
    files = sorted(
        path for path in base.rglob('*.py')
        if '__pycache__' not in path.parts and path.is_file() and not path.is_symlink()
    )
    if not files:
        raise RuntimeError('embedded Projectmanager source set is empty')
    for path in files:
        rel = path.relative_to(base).as_posix().encode('utf-8')
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(4, 'big'))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
    return digest.hexdigest()


def _source_root(project_root: Path) -> Path:
    return project_root / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2'


def expected_fingerprint(project_root: Path | str) -> str:
    return _fingerprint_tree(_source_root(Path(project_root)))


def _red(reason: str, **extra) -> dict:
    return {'status': 'RESTART_REQUIRED', 'ready': False, 'reason': reason, **extra}


def probe(project_root: Path | str, *, now: float | None = None, stale_seconds: float = 180.0) -> dict:
    root = Path(project_root)
    marker = project_system_path(root, 'Inbox/projectmanager_v2/RuntimeV2/embedded_runtime/current.json')
    version_path = root / 'App/VERSIE.txt'
    try:
        st = marker.lstat()
    except FileNotFoundError:
        return _red('runtime_marker_missing')
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
        return _red('runtime_marker_unsafe')
    try:
        data = json.loads(marker.read_text(encoding='utf-8'))
    except Exception as exc:
        return _red('runtime_marker_invalid', error=f'{type(exc).__name__}: {exc}')
    if not isinstance(data, dict) or data.get('schema') != 'energie_embedded_pm_runtime_v1' or data.get('status') != 'GREEN':
        return _red('runtime_marker_invalid')
    observed = data.get('observed_at_epoch')
    if not isinstance(observed, (int, float)):
        return _red('runtime_marker_invalid')
    current = time.time() if now is None else float(now)
    if current - float(observed) > float(stale_seconds):
        return _red('runtime_marker_stale', age_seconds=max(0.0, current - float(observed)))
    try:
        release = version_path.read_text(encoding='utf-8').strip()
        expected = expected_fingerprint(root)
    except Exception as exc:
        return _red('source_evidence_unavailable', error=f'{type(exc).__name__}: {exc}')
    loaded = str(data.get('loaded_runtime_fingerprint') or '').strip().lower()
    if loaded != expected:
        return _red('loaded_runtime_fingerprint_mismatch', expected_fingerprint=expected, loaded_runtime_fingerprint=loaded)
    runtime_release = str(data.get('runtime_release_version') or '').strip()
    if runtime_release != release:
        return _red('runtime_release_mismatch', release_version=release, runtime_release_version=runtime_release)
    generation = str(data.get('cycle_generation') or '').strip()
    provenance = data.get('provenance') if isinstance(data.get('provenance'), dict) else {}
    if not generation or str(provenance.get('generation') or '').strip() != generation:
        return _red('runtime_generation_mismatch')
    if provenance.get('phase') != 'FINAL':
        return _red('runtime_not_final')
    return {
        'status': 'GREEN',
        'ready': True,
        'reason': 'loaded_runtime_source_release_generation_match',
        'release_version': release,
        'cycle_generation': generation,
        'expected_fingerprint': expected,
        'loaded_runtime_fingerprint': loaded,
        'age_seconds': max(0.0, current - float(observed)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only embedded Projectmanager runtime/source guard')
    parser.add_argument('--root', required=True)
    parser.add_argument('--stale-seconds', type=float, default=180.0)
    args = parser.parse_args()
    result = probe(Path(args.root), stale_seconds=args.stale_seconds)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('ready') else 3


if __name__ == '__main__':
    raise SystemExit(main())
