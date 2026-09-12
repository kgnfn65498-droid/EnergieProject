from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = 'energie_project_close_v1'
VALID_STATES = {'DEFERRED', 'REQUESTED'}
RELATIVE_PATH = Path('Inbox/projectmanager_v2/RuntimeV2/state/project_close.json')


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or (path.parent.exists() and path.parent.is_symlink()):
        raise RuntimeError('onveilig project-close state pad')
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    try:
        with temp.open('w', encoding='utf-8') as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def project_close_path(project_root: Path | str) -> Path:
    return Path(project_root) / RELATIVE_PATH


def _deferred(*, active_release: str, reason: str, source_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        'schema': SCHEMA,
        'release_version': str(active_release or ''),
        'state': 'DEFERRED',
        'reason': str(reason),
        'current': False,
        'source_payload': source_payload or {},
    }


def load_project_close(project_root: Path | str, *, active_release: str) -> dict[str, Any]:
    """Load the one fail-closed project-close truth for the active release.

    Missing, invalid, unsafe, or release-stale state is always interpreted as
    DEFERRED.  Nothing may infer REQUESTED from historical closure state.
    """
    path = project_close_path(project_root)
    if path.is_symlink() or not path.is_file():
        return _deferred(active_release=active_release, reason='missing')
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _deferred(active_release=active_release, reason='invalid_json')
    if not isinstance(payload, dict) or payload.get('schema') != SCHEMA:
        return _deferred(active_release=active_release, reason='invalid_schema', source_payload=payload if isinstance(payload, dict) else {})
    release = str(payload.get('release_version') or '').strip()
    if release != str(active_release or '').strip():
        return _deferred(active_release=active_release, reason='release_mismatch', source_payload=payload)
    state = str(payload.get('state') or '').strip().upper()
    if state not in VALID_STATES:
        return _deferred(active_release=active_release, reason='invalid_state', source_payload=payload)
    result = dict(payload)
    result['state'] = state
    result['current'] = True
    return result


def write_project_close(
    project_root: Path | str,
    *,
    release_version: str,
    state: str,
    reason: str,
    source: str = 'projectmanager',
) -> dict[str, Any]:
    release = str(release_version or '').strip()
    normalized = str(state or '').strip().upper()
    if not release or any(part == '' or not part.isdigit() for part in release.split('.')):
        raise ValueError('project-close release_version ongeldig')
    if normalized not in VALID_STATES:
        raise ValueError('project-close state moet DEFERRED of REQUESTED zijn')
    payload = {
        'schema': SCHEMA,
        'release_version': release,
        'state': normalized,
        'reason': str(reason or '').strip() or 'unspecified',
        'source': str(source or 'projectmanager'),
        'updated_at': datetime.now(timezone.utc).isoformat(),
        'current': True,
    }
    _atomic_json(project_close_path(project_root), payload)
    # Exact readback is part of the shared-state contract.
    readback = load_project_close(project_root, active_release=release)
    if readback.get('current') is not True or readback.get('state') != normalized:
        raise RuntimeError('project-close state readback mismatch')
    return readback
