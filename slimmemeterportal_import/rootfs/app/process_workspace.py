from __future__ import annotations

"""Canonical transient workspace for EnergieProject development/runtime work.

The module is intentionally narrow: it registers temporary/cache artifacts so
CLEARUP can quarantine only material with explicit ownership. Unknown material
is reported as hygiene debt and is never auto-moved.
"""

import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "energie_process_workspace_v1"
PROCESS_ROOT_REL = "Inbox/process"
PROCESS_MAP_REL = "Inbox/process/process_map.json"
ALLOWED_NAMESPACES = ("tmp", "cache", "active")
CLEANABLE_NAMESPACES = {"tmp", "cache"}


def _utc_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(now: datetime | None = None) -> str:
    return _utc_now(now).isoformat()


def _project_root(project_root: Path) -> Path:
    return Path(project_root).absolute()


def _process_root(project_root: Path) -> Path:
    return _project_root(project_root) / PROCESS_ROOT_REL


def _process_map_path(project_root: Path) -> Path:
    return _project_root(project_root) / PROCESS_MAP_REL


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o777)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        os.fchmod(fd, 0o666)
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            fd = -1
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        os.chmod(path, 0o666)
    finally:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def _empty_map() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "root": PROCESS_ROOT_REL,
        "allowed_namespaces": list(ALLOWED_NAMESPACES),
        "entries": {},
    }


def _load_map(project_root: Path) -> dict[str, Any]:
    path = _process_map_path(project_root)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty_map()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"process workspace map unreadable: {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        raise RuntimeError(f"process workspace map invalid: {path}")
    entries = value.get("entries")
    if not isinstance(entries, dict):
        raise RuntimeError(f"process workspace entries invalid: {path}")
    return value


def ensure_process_workspace(project_root: Path) -> dict[str, Any]:
    root = _process_root(project_root)
    if root.is_symlink():
        raise RuntimeError(f"process workspace root is symlink: {root}")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o777)
    for name in ALLOWED_NAMESPACES:
        path = root / name
        if path.is_symlink():
            raise RuntimeError(f"process workspace namespace is symlink: {path}")
        path.mkdir(exist_ok=True)
        path.chmod(0o777)
    map_path = _process_map_path(project_root)
    if not map_path.exists():
        _atomic_write_json(map_path, _empty_map())
    payload = _load_map(project_root)
    return {"root": PROCESS_ROOT_REL, "map": PROCESS_MAP_REL, "entries": len(payload["entries"])}


def _validated_artifact(project_root: Path, artifact_path: Path, *, kind: str | None = None) -> tuple[Path, str, str]:
    root = _process_root(project_root)
    path = Path(artifact_path).absolute()
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"artifact must live under {PROCESS_ROOT_REL}: {path}") from exc
    if not relative.parts:
        raise ValueError(f"artifact must live below {PROCESS_ROOT_REL}")
    namespace = relative.parts[0]
    if namespace not in ALLOWED_NAMESPACES:
        raise ValueError(f"unsupported process namespace: {namespace}")
    if kind is not None and namespace != str(kind):
        raise ValueError(f"artifact namespace {namespace} does not match kind {kind}")
    if path.is_symlink():
        raise ValueError(f"process artifact may not be a symlink: {path}")
    rel_project = path.relative_to(_project_root(project_root)).as_posix()
    return path, rel_project, namespace


def register_process_artifact(
    project_root: Path,
    artifact_path: Path,
    *,
    owner: str,
    purpose: str,
    kind: str = "tmp",
    now: datetime | None = None,
) -> dict[str, Any]:
    ensure_process_workspace(project_root)
    path, relative, namespace = _validated_artifact(project_root, artifact_path, kind=kind)
    if not str(owner or "").strip() or not str(purpose or "").strip():
        raise ValueError("owner and purpose are required")
    if not path.exists():
        raise FileNotFoundError(path)
    payload = _load_map(project_root)
    row = {
        "source_path": relative,
        "namespace": namespace,
        "owner": str(owner).strip(),
        "purpose": str(purpose).strip(),
        "state": "ACTIVE",
        "registered_at": _iso(now),
        "released_at": None,
    }
    payload["entries"][relative] = row
    _atomic_write_json(_process_map_path(project_root), payload)
    return dict(row)


def release_process_artifact(
    project_root: Path,
    artifact_path: Path,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    path, relative, _namespace = _validated_artifact(project_root, artifact_path)
    payload = _load_map(project_root)
    row = payload["entries"].get(relative)
    if not isinstance(row, dict):
        raise KeyError(f"process artifact is not registered: {relative}")
    if row.get("state") == "RELEASED":
        return dict(row)
    row = dict(row)
    row["state"] = "RELEASED"
    row["released_at"] = _iso(now)
    payload["entries"][relative] = row
    _atomic_write_json(_process_map_path(project_root), payload)
    return dict(row)


def clearup_process_candidates(
    project_root: Path,
    *,
    now: datetime | None = None,
    stale_after_seconds: float = 0.0,
) -> list[dict[str, Any]]:
    del now  # reserved for future age-based, fail-closed cleanup policy
    del stale_after_seconds
    payload = _load_map(project_root)
    result: list[dict[str, Any]] = []
    for relative, row in sorted(payload["entries"].items()):
        if not isinstance(row, dict) or row.get("state") not in {"RELEASED", "ABANDONED"}:
            continue
        namespace = str(row.get("namespace") or "")
        if namespace not in CLEANABLE_NAMESPACES:
            continue
        try:
            path, verified_relative, verified_namespace = _validated_artifact(project_root, _project_root(project_root) / relative)
        except (ValueError, OSError):
            continue
        if verified_relative != relative or verified_namespace != namespace:
            continue
        if not path.exists() and not path.is_symlink():
            continue
        result.append({
            "source_path": relative,
            "reason": "registered_process_artifact_released",
            "category": "process_workspace",
            "owner": row.get("owner"),
            "purpose": row.get("purpose"),
        })
    return result


def inspect_process_workspace(project_root: Path) -> dict[str, Any]:
    process_root = _process_root(project_root)
    if not process_root.exists():
        return {
            "exists": False,
            "active_count": 0,
            "released_count": 0,
            "unregistered_count": 0,
            "unregistered": [],
            "invalid_entry_count": 0,
        }
    try:
        payload = _load_map(project_root)
        entries = payload["entries"]
    except RuntimeError:
        return {
            "exists": True,
            "active_count": 0,
            "released_count": 0,
            "unregistered_count": 0,
            "unregistered": [],
            "invalid_entry_count": 1,
        }

    existing_registered: set[str] = set()
    active_count = 0
    released_count = 0
    invalid = 0
    for relative, row in entries.items():
        if not isinstance(row, dict):
            invalid += 1
            continue
        try:
            path, verified_relative, namespace = _validated_artifact(
                project_root, _project_root(project_root) / relative
            )
        except (ValueError, OSError):
            invalid += 1
            continue
        if verified_relative != relative or namespace != str(row.get("namespace") or ""):
            invalid += 1
            continue
        if path.exists() or path.is_symlink():
            existing_registered.add(relative)
            state = str(row.get("state") or "")
            if state == "ACTIVE":
                active_count += 1
            elif state in {"RELEASED", "ABANDONED"}:
                released_count += 1
            else:
                invalid += 1

    unregistered: list[str] = []
    for namespace in ALLOWED_NAMESPACES:
        directory = process_root / namespace
        if not directory.is_dir():
            continue
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name)
        except OSError:
            invalid += 1
            continue
        for child in children:
            relative = child.relative_to(_project_root(project_root)).as_posix()
            if relative not in existing_registered:
                unregistered.append(relative)

    return {
        "exists": True,
        "active_count": active_count,
        "released_count": released_count,
        "unregistered_count": len(unregistered),
        "unregistered": sorted(unregistered),
        "invalid_entry_count": invalid,
    }
