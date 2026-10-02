from __future__ import annotations

import os
from pathlib import Path

COMMON_MARKER = "# MCP_PROJECT_ROOT_ALIAS_VERSION=2026-09-30.v1"
HEALTH_MARKER = "# MCP_MASTER_HEALTH_SCAN_GUARD_VERSION=2026-09-30.v1"

COMMON_OLD = '''def _resolve_inside(root: Path, relative_path: str) -> Path:
    clean = str(relative_path).strip()
    candidate = root if clean in {"", ".", "/"} else (root / clean.lstrip("/")).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Pad valt buiten de toegestane root: {root}") from exc
    return candidate
'''

COMMON_NEW = '''def _resolve_inside(root: Path, relative_path: str) -> Path:
    # MCP_PROJECT_ROOT_ALIAS_VERSION=2026-09-30.v1
    root = root.resolve()
    clean = str(relative_path).strip()

    if clean in {"", ".", "/"}:
        candidate = root
    elif clean == str(root) or clean.startswith(f"{root}/"):
        candidate = Path(clean).resolve()
    else:
        candidate = (root / clean.lstrip("/")).resolve()

    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Pad valt buiten de toegestane root: {root}") from exc
    return candidate
'''

HEALTH_GUARD = '''from __future__ import annotations

# MCP_MASTER_HEALTH_SCAN_GUARD_VERSION=2026-09-30.v1
import os
from pathlib import Path

import tools_master_health as _health

_ORIGINAL_FILES = _health._files


def _bounded_health_files(directory: Path, recursive: bool = True) -> list[Path]:
    directory = Path(directory)
    try:
        resolved = directory.resolve()
        report_root = _health.REPORT_ROOT.resolve()
        backup_root = (report_root / _health.BACKUP_DIR_NAME).resolve()
    except OSError:
        return _ORIGINAL_FILES(directory, recursive=recursive)

    if recursive and resolved == report_root:
        items: list[Path] = []
        for current_root, directories, files in os.walk(directory):
            directories[:] = sorted(
                name for name in directories
                if name != _health.BACKUP_DIR_NAME
            )
            for filename in sorted(files):
                items.append(Path(current_root) / filename)
        return items

    if recursive and resolved == backup_root:
        return _ORIGINAL_FILES(directory, recursive=False)

    return _ORIGINAL_FILES(directory, recursive=recursive)


_health._files = _bounded_health_files
'''


def _atomic_text(path: Path, content: str) -> None:
    if path.is_symlink():
        raise RuntimeError(f"unsafe symlink target: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temp.write_text(content, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _patch_common(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if COMMON_MARKER in text:
        return False
    if text.count(COMMON_OLD) != 1:
        raise RuntimeError("common.py project-root alias anchor mismatch")
    _atomic_text(path, text.replace(COMMON_OLD, COMMON_NEW, 1))
    return True


def _patch_server(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    import_line = "import master_health_scan_guard  # noqa: F401\n"
    if import_line in text:
        return False
    anchor = "import tools_master_health  # noqa: F401\n"
    if text.count(anchor) != 1:
        raise RuntimeError("server.py master-health import anchor mismatch")
    _atomic_text(path, text.replace(anchor, anchor + import_line, 1))
    return True


def _patch_fingerprint(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    required = (
        '    "common.py",\n',
        '    "master_health_scan_guard.py",\n',
    )
    if all(item in text for item in required):
        return False
    anchor = '    "server.py",\n'
    if text.count(anchor) != 1:
        raise RuntimeError("runtime_fingerprint.py target anchor mismatch")
    addition = "".join(item for item in required if item not in text)
    _atomic_text(path, text.replace(anchor, anchor + addition, 1))
    return True


def apply(root: Path | str) -> dict:
    root = Path(root).resolve()
    native = root / "Infra/Docker/native-mcp"
    common = native / "common.py"
    server = native / "server.py"
    fingerprint = native / "runtime_fingerprint.py"
    guard = native / "master_health_scan_guard.py"

    for path in (common, server, fingerprint):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"native MCP source missing/unsafe: {path.name}")

    changed: list[str] = []
    if _patch_common(common):
        changed.append("common.py:project_root_alias")
    if not guard.is_file() or guard.is_symlink() or guard.read_text(encoding="utf-8") != HEALTH_GUARD:
        _atomic_text(guard, HEALTH_GUARD)
        changed.append("master_health_scan_guard.py")
    if _patch_server(server):
        changed.append("server.py:master_health_scan_guard_import")
    if _patch_fingerprint(fingerprint):
        changed.append("runtime_fingerprint.py:path_health_targets")

    return {
        "schema": "energie_mcp_path_health_runtime_hotfix_v1",
        "status": "GREEN",
        "changed": changed,
        "reload_required": bool(changed),
        "project_root_alias_current": COMMON_MARKER in common.read_text(encoding="utf-8"),
        "health_scan_guard_current": HEALTH_MARKER in guard.read_text(encoding="utf-8"),
        "fingerprint_covers_fix": (
            '"common.py"' in fingerprint.read_text(encoding="utf-8")
            and '"master_health_scan_guard.py"' in fingerprint.read_text(encoding="utf-8")
        ),
    }
