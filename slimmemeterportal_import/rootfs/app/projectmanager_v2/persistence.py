import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

KNOWN_RUNTIME_CHILD_DIRS = {
    'state', 'status', 'heartbeat', 'handover', 'audit', 'notifications',
    'opportunities', 'snapshots', 'self_audit', 'issues', 'market',
    'decisions', 'locks', 'commands', 'roadmap', 'quarantine',
}


def _path(value) -> Path:
    return value if isinstance(value, Path) else Path(value)


def _fsync_parent(path: Path) -> None:
    try:
        fd = os.open(str(path.parent), os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(fd)
        except OSError:
            pass
    finally:
        os.close(fd)


def atomic_write_text(path, content: str) -> None:
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=str(target.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
        _fsync_parent(target)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n')


def _clone_default(default):
    return deepcopy(default)


def _runtime_root_for(target: Path) -> Path:
    for parent in target.parents:
        if parent.name == 'RuntimeV2':
            return parent
    if target.parent.name in KNOWN_RUNTIME_CHILD_DIRS:
        return target.parent.parent
    if target.parent.parent.name in KNOWN_RUNTIME_CHILD_DIRS:
        return target.parent.parent.parent
    return target.parent


def _quarantine(target: Path, quarantine_root=None, *, reason='invalid_json') -> str:
    root = _path(quarantine_root) if quarantine_root is not None else _runtime_root_for(target)
    quarantine = root / 'quarantine'
    quarantine.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    dest = quarantine / f'{target.name}.{stamp}.corrupt'
    os.replace(target, dest)
    meta = quarantine / f'{dest.name}.meta.json'
    atomic_write_json(meta, {
        'schema': 1,
        'source': str(target),
        'quarantined_to': str(dest),
        'reason': reason,
        'quarantined_at': datetime.now(timezone.utc).isoformat(),
    })
    return str(dest)


def load_json(path, default=None, *, recover_corrupt: bool = False, quarantine_root=None, validator=None):
    target = _path(path)
    if not target.exists():
        return _clone_default(default)
    try:
        raw = target.read_text(encoding='utf-8')
    except OSError:
        # Permission/I-O failures are operational failures, not corrupt data.
        # Never move/quarantine a file merely because it cannot be read.
        raise
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        if not recover_corrupt:
            raise
        _quarantine(target, quarantine_root=quarantine_root, reason=f'{type(exc).__name__}: {exc}')
        return _clone_default(default)
    if validator is not None:
        try:
            valid = bool(validator(data))
        except Exception as exc:
            if not recover_corrupt:
                raise
            _quarantine(target, quarantine_root=quarantine_root, reason=f'validator_error:{type(exc).__name__}')
            return _clone_default(default)
        if not valid:
            if not recover_corrupt:
                raise ValueError('json schema validation failed')
            _quarantine(target, quarantine_root=quarantine_root, reason='json_schema_validation_failed')
            return _clone_default(default)
    return data


def append_jsonl(path, payload: Any) -> None:
    target = _path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, ensure_ascii=False, sort_keys=True) + '\n'
    with target.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())
