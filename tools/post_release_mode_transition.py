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


def _closure_green(project: Path, release_version: str) -> bool:
    status_path = project / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
    try:
        payload = json.loads(status_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return False
    closure = payload.get('series_324_live_closure') if isinstance(payload, dict) else None
    return (
        isinstance(closure, dict)
        and closure.get('status') == 'GREEN'
        and str(closure.get('release_version') or '') == str(release_version)
    )


def apply(root: Path | str) -> dict:
    project = Path(root).resolve()
    marker_path = project / MARKER_REL
    transition_path = project / 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json'
    try:
        transition = json.loads(transition_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, UnicodeError):
        transition = None
    if isinstance(transition, dict) and str(transition.get('lifecycle_state') or '') not in {'COMPLETE','ROLLED_BACK','CANCELLED'}:
        return {'status':'COORDINATOR_OWNED','changed':False,'generation_id':transition.get('generation_id'),'phase':transition.get('phase')}
    if not marker_path.is_file() or marker_path.is_symlink():
        return {'status': 'NO_REQUEST', 'changed': False}
    marker = json.loads(marker_path.read_text(encoding='utf-8'))
    if marker.get('schema') != 'energie_post_release_maintenance_v1':
        raise RuntimeError('post-release maintenance marker schema ongeldig')
    expected = str(marker.get('release_version') or '')
    actual = (project / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    if not expected or expected != actual:
        raise RuntimeError('post-release maintenance marker release mismatch')

    app = project / 'App/slimmemeterportal_import/rootfs/app'
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))
    from operating_modes import (
        Mode, begin_temporary_mode, end_temporary_mode, load_mode_state, save_mode_state, set_base_mode,
    )

    status = str(marker.get('status') or '')
    transition_id = str(marker.get('transition_id') or f'post-release-maintenance:{expected}')

    if status == 'COMPLETED':
        return {**marker, 'changed': False}

    if status == 'APPLIED':
        temp_transition = str(marker.get('temporary_transition_id') or '')
        if not temp_transition:
            # Legacy/non-development behavior: APPLIED remains idempotent.
            return {**marker, 'changed': False}
        if not _closure_green(project, expected):
            return {**marker, 'changed': False}
        state = load_mode_state(project)
        if state.active_transition_id == temp_transition:
            restored = end_temporary_mode(state, temp_transition)
            if restored.active_transition_id or restored.effective_mode is not restored.base_mode:
                raise RuntimeError('post-release tijdelijke MAINTENANCE kon niet fail-closed worden beëindigd')
            save_mode_state(project, restored)
        elif not (
            state.development_session_active
            and state.base_mode is Mode.DEVELOPMENT
            and state.effective_mode is Mode.DEVELOPMENT
            and not state.active_transition_id
        ):
            raise RuntimeError('post-release tijdelijke MAINTENANCE state/marker mismatch')
        readback = load_mode_state(project)
        if not (
            readback.development_session_active
            and readback.base_mode is Mode.DEVELOPMENT
            and readback.effective_mode is Mode.DEVELOPMENT
            and not readback.active_transition_id
        ):
            raise RuntimeError('post-release DEVELOPMENT readback niet GREEN')
        result = {
            **marker, 'status': 'COMPLETED', 'changed': True,
            'completed_at': datetime.now(timezone.utc).isoformat(),
            'mode': 'DEVELOPMENT',
        }
        _atomic(marker_path, result)
        return result

    if status != 'REQUIRED':
        raise RuntimeError('post-release maintenance marker status ongeldig')

    state = load_mode_state(project)
    if state.development_session_active and state.base_mode is Mode.DEVELOPMENT:
        updated = begin_temporary_mode(
            state, Mode.MAINTENANCE,
            reason=f'post-release closure {expected}',
            transition_id=transition_id,
        )
        if (
            updated.base_mode is not Mode.DEVELOPMENT
            or updated.effective_mode is not Mode.MAINTENANCE
            or not updated.development_session_active
            or updated.active_transition_id != transition_id
        ):
            raise RuntimeError('post-release tijdelijke MAINTENANCE werd fail-closed geweigerd')
        save_mode_state(project, updated)
        readback = load_mode_state(project)
        if (
            readback.base_mode is not Mode.DEVELOPMENT
            or readback.effective_mode is not Mode.MAINTENANCE
            or not readback.development_session_active
            or readback.active_transition_id != transition_id
        ):
            raise RuntimeError('post-release tijdelijke MAINTENANCE readback niet GREEN')
        result = {
            **marker, 'status': 'APPLIED', 'changed': True,
            'applied_at': datetime.now(timezone.utc).isoformat(),
            'mode': 'MAINTENANCE',
            'temporary_transition_id': transition_id,
            'base_mode_preserved': 'DEVELOPMENT',
        }
    else:
        updated = set_base_mode(state, Mode.MAINTENANCE, confirmed_by_user=True)
        if updated.effective_mode is not Mode.MAINTENANCE or updated.base_mode is not Mode.MAINTENANCE:
            raise RuntimeError('post-release overgang naar MAINTENANCE werd fail-closed geweigerd')
        save_mode_state(project, updated)
        readback = load_mode_state(project)
        if readback.effective_mode is not Mode.MAINTENANCE or readback.base_mode is not Mode.MAINTENANCE:
            raise RuntimeError('post-release MAINTENANCE readback niet GREEN')
        result = {
            **marker, 'status': 'APPLIED', 'changed': True,
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
