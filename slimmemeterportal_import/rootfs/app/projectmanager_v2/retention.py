from datetime import datetime, timezone
from pathlib import Path

# Retention is intentionally narrow. Active state/audit/outbox files are never
# candidates. Only immutable historical/delivered artifacts owned by PMV2 are.
OWNED_ARCHIVE_DIRS = (
    'snapshots/archive',
    'notifications/outbox/delivered',
    'logs/archive',
    'audit/archive',
)


def retention_candidates(runtime_root, *, now=None, keep_days: int = 30) -> list[str]:
    root = Path(runtime_root).resolve()
    now = now or datetime.now(timezone.utc)
    cutoff = now.timestamp() - max(0, int(keep_days)) * 86400
    candidates = []
    for rel in OWNED_ARCHIVE_DIRS:
        directory = (root / rel).resolve()
        if not directory.is_dir() or root not in directory.parents:
            continue
        for path in directory.rglob('*'):
            if not path.is_file():
                continue
            resolved = path.resolve()
            if root not in resolved.parents or directory not in resolved.parents:
                continue
            try:
                old = path.stat().st_mtime < cutoff
            except OSError:
                continue
            if old:
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
    return {'deleted': deleted, 'blocked': False, 'scope': list(OWNED_ARCHIVE_DIRS)}
