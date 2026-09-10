#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

MARKER_REL = Path('Inbox/operating_mode/post_release_maintenance_required.json')


def _atomic(path: Path, payload: dict) -> None:
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def apply(root: Path | str) -> dict:
    project = Path(root).resolve()
    marker_path = project / MARKER_REL
    if not marker_path.is_file() or marker_path.is_symlink():
        return {'status': 'NO_REQUEST', 'changed': False}
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    if marker.get('schema') != 'energie_post_release_maintenance_v1':
        raise RuntimeError('post-release maintenance marker schema ongeldig')
    expected = str(marker.get('release_version') or '')
    actual = (project / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    if not expected or expected != actual:
        raise RuntimeError('post-release maintenance marker release mismatch')
    if marker.get('status') == 'APPLIED':
        return {**marker, 'changed': False}
    if marker.get('status') != 'REQUIRED':
        raise RuntimeError('post-release maintenance marker status ongeldig')

    app = project / 'App/slimmemeterportal_import/rootfs/app'
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))
    from operating_modes import Mode, load_mode_state, save_mode_state, set_base_mode

    state = load_mode_state(project)
    updated = set_base_mode(state, Mode.MAINTENANCE, confirmed_by_user=True)
    if updated.effective_mode is not Mode.MAINTENANCE or updated.base_mode is not Mode.MAINTENANCE:
        raise RuntimeError('post-release overgang naar MAINTENANCE werd fail-closed geweigerd')
    save_mode_state(project, updated)
    result = {
        **marker,
        'status': 'APPLIED',
        'changed': True,
        'applied_at': datetime.now(timezone.utc).isoformat(),
        'mode': 'MAINTENANCE',
    }
    _atomic(marker_path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description='Apply exact post-release DEVELOPMENT to MAINTENANCE transition')
    parser.add_argument('--root', required=True)
    args = parser.parse_args()
    try:
        result = apply(Path(args.root))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(f'POST_RELEASE_MAINTENANCE_RED: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
