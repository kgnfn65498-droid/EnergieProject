#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

MANIFEST = '.energie-platformtest-source.json'


def _git(repo: Path, *args: str, text: bool = False):
    return subprocess.check_output(['git', '-C', str(repo), *args], text=text)


def prepare(repo: Path | str, destination_root: Path | str) -> dict:
    repo = Path(repo).resolve()
    destination_root = Path(destination_root).resolve()
    candidate = _git(repo, 'rev-parse', 'HEAD', text=True).strip().lower()
    if len(candidate) != 40 or any(ch not in '0123456789abcdef' for ch in candidate):
        raise RuntimeError('platformtest requires a SHA-1 git commit identity')
    if _git(repo, 'status', '--porcelain', '--untracked-files=no', text=True).strip():
        raise RuntimeError('platformtest source must be committed before staging')
    names = [item.decode() for item in _git(repo, 'ls-files', '-z').split(b'\0') if item]
    if MANIFEST in names:
        raise RuntimeError('platformtest manifest must not be tracked')

    destination_root.mkdir(parents=True, exist_ok=True)
    final = destination_root / candidate
    if final.exists():
        raise RuntimeError('platformtest destination already exists')
    temporary = Path(tempfile.mkdtemp(prefix=f'.{candidate}.tmp-', dir=str(destination_root)))
    try:
        entries = []
        for name in names:
            source = repo / name
            target = temporary / name
            if source.is_symlink() or not source.is_file():
                raise RuntimeError(f'platformtest tracked source unsafe: {name}')
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            mode = '100755' if source.stat().st_mode & 0o111 else '100644'
            os.chmod(target, 0o555 if mode == '100755' else 0o444)
            data = target.read_bytes()
            entries.append({'path': name, 'sha256': hashlib.sha256(data).hexdigest(), 'size': len(data), 'mode': mode})
        entries.sort(key=lambda item: item['path'])
        canonical = json.dumps(entries, separators=(',', ':'), sort_keys=True).encode()
        source_sha256 = hashlib.sha256(canonical).hexdigest()
        commit = _git(repo, 'cat-file', 'commit', candidate)
        manifest = {
            'schema': 'energie_platformtest_source_v1',
            'candidate_sha': candidate,
            'source_sha256': source_sha256,
            'git_commit_hex': commit.hex(),
            'files': entries,
        }
        (temporary / MANIFEST).write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.chmod(temporary / MANIFEST, 0o444)
        for directory in sorted((p for p in temporary.rglob('*') if p.is_dir()), reverse=True):
            os.chmod(directory, 0o555)
        os.chmod(temporary, 0o555)
        os.replace(temporary, final)
        return {'candidate_sha': candidate, 'source_sha256': source_sha256, 'workspace': str(final), 'files_total': len(entries)}
    except Exception:
        if temporary.exists():
            for path in temporary.rglob('*'):
                try:
                    if path.is_dir(): os.chmod(path, 0o755)
                    else: os.chmod(path, 0o644)
                except OSError: pass
            shutil.rmtree(temporary, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True)
    parser.add_argument('--destination-root', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.repo, args.destination_root), sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
