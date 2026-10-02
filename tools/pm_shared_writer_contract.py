from __future__ import annotations

import os
from pathlib import Path


_SHARED_PM_WRITER_DIRECTORIES = (
    "Data/03_Systeem/Projectmanager/Handover",
    "Data/03_Systeem/Projectmanager/ClearUp/Recovery",
    "Data/03_Systeem/Projectmanager/ClearUp/Exports",
    "Data/03_Systeem/Projectmanager/ClearUp/State",
)


def normalize_pm_shared_writer_contract(root: Path | str) -> dict:
    """Normalize the fixed cross-identity Projectmanager writer directories."""
    root = Path(root)
    normalized = []
    for rel in _SHARED_PM_WRITER_DIRECTORIES:
        path = root / rel
        if path.exists() and (path.is_symlink() or not path.is_dir()):
            raise RuntimeError("projectmanager_shared_writer_directory_unsafe:" + rel)
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o1777)
        if (path.stat().st_mode & 0o7777) != 0o1777:
            raise RuntimeError("projectmanager_shared_writer_mode_mismatch:" + rel)
        normalized.append(rel)
    return {"status": "GREEN", "directory_mode": "1777", "directories": normalized}
