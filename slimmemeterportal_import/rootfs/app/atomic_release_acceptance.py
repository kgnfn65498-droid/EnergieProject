from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return payload if isinstance(payload, dict) else None


def finalize_validated_atomic_release(project_root: Path | str, expected_version: str) -> dict[str, Any]:
    """Finalize the QNAP atomic swap only after release validation already passed.

    The canonical atomic_app_swap.py remains the single implementation of physical
    validation and journal mutation. This adapter only resolves the exact current
    release parameters and invokes the tool without a shell.
    """
    root = Path(project_root)
    journal_path = root / 'Inbox' / 'atomic_app_swap_state.json'
    journal = _read_json(journal_path)
    if journal is None:
        return {'status': 'not_required', 'reason': 'atomic_journal_missing'}

    state = str(journal.get('state') or '').strip().upper()
    target = str(journal.get('to_version') or '').strip()
    source = str(journal.get('from_version') or '').strip()
    expected = str(expected_version or '').strip()

    if state == 'ACCEPTED' and target == expected:
        return {'status': 'already_accepted', 'state': state, 'version': target}
    if state != 'LIVE_ACCEPTANCE':
        raise RuntimeError(f'atomic_acceptance_not_ready:{state or "MISSING"}')
    if target != expected:
        raise RuntimeError(f'atomic_acceptance_target_mismatch:{target or "MISSING"}:{expected}')
    if not source:
        raise RuntimeError('atomic_acceptance_source_missing')

    pm_version_path = root / 'App' / 'slimmemeterportal_import' / 'rootfs' / 'app' / 'projectmanager_v2' / 'VERSION.txt'
    tool_path = root / 'App' / 'tools' / 'atomic_app_swap.py'
    try:
        pm_version = pm_version_path.read_text(encoding='utf-8').strip()
    except OSError as exc:
        raise RuntimeError(f'atomic_acceptance_pm_version_unavailable:{type(exc).__name__}') from exc
    if not pm_version:
        raise RuntimeError('atomic_acceptance_pm_version_missing')
    if not tool_path.is_file():
        raise RuntimeError('atomic_acceptance_tool_missing')

    command = [
        sys.executable,
        str(tool_path),
        'accept',
        '--root', str(root),
        '--from-version', source,
        '--to-version', expected,
        '--to-pm-version', pm_version,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or '').strip()[-1000:]
        raise RuntimeError(f'atomic_acceptance_failed:{result.returncode}:{detail}')

    final = _read_json(journal_path)
    if not isinstance(final, dict) or str(final.get('state') or '').upper() != 'ACCEPTED':
        raise RuntimeError('atomic_acceptance_not_persisted')
    if str(final.get('to_version') or '') != expected:
        raise RuntimeError('atomic_acceptance_persisted_target_mismatch')
    return {
        'status': 'accepted',
        'state': 'ACCEPTED',
        'version': expected,
        'from_version': source,
        'pm_version': pm_version,
    }
