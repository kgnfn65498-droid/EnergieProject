from datetime import datetime, timezone
from pathlib import Path

OWNED_RETENTION_DIRS = {'audit', 'logs', 'snapshots', 'notifications'}
PROTECTED_DIRS = {'state', 'handover', 'decisions', 'opportunities', 'status', 'heartbeat'}


def retention_candidates(runtime_root, *, now=None, keep_days: int = 30) -> list[str]:
    root = Path(runtime_root).resolve()
    now = now or datetime.now(timezone.utc)
    cutoff = now.timestamp() - max(0, int(keep_days)) * 86400
    candidates = []
    for dirname in OWNED_RETENTION_DIRS:
        directory = root / dirname
        if not directory.is_dir():
            continue
        for path in directory.rglob('*'):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if root not in resolved.parents:
                continue
            relative_parts = resolved.relative_to(root).parts
            if any(part in PROTECTED_DIRS for part in relative_parts):
                continue
            if path.stat().st_mtime < cutoff:
                candidates.append(str(path))
    return sorted(candidates)


def apply_retention(runtime_root, *, now=None, keep_days: int = 30, confirmed_owned_scope: bool = False) -> dict:
    if confirmed_owned_scope is not True:
        return {'deleted': [], 'blocked': True, 'reason': 'owned_scope_not_confirmed'}
    deleted = []
    for candidate in retention_candidates(runtime_root, now=now, keep_days=keep_days):
        path = Path(candidate)
        path.unlink()
        deleted.append(candidate)
    return {'deleted': deleted, 'blocked': False}
