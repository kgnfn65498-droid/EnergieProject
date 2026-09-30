from __future__ import annotations

"""32.5.30 canonical EnergieProject ROOT cleanup orchestration.

This layer never performs privileged live mutations itself. It builds an exact
hash-bound plan, prepares a recovery artifact for destructive candidates, and
hands the approved request to the existing ClearUp watcher/executor sideband.
"""

import base64
import hashlib
import json
import os
import secrets
import shutil
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import project_clearup
from root_structure_policy import root_structure_snapshot
from system_path_contract import project_system_path

MIN_VERSION = (32, 5, 30)
PLAN_SCHEMA = "energie_root_cleanup_plan_v1"
REQUEST_SCHEMA = "energie_root_cleanup_request_v1"
RESULT_SCHEMA = "energie_root_cleanup_result_v1"
WATCHER_REQUEST_REL = Path("Inbox/projectmanager_v2/RuntimeV2/clearup/project_clearup_move_request.json")
WATCHER_RESULT_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Runtime/results")
RECOVERY_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Recovery")
EXPORT_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Exports")
STATE_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/State")
LEGACY_CLEARUP_TARGET_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/LegacyRoot/CLEARUP_PRE_32_5_30")
WATCHER_TIMEOUT_SECONDS = 120.0
RECOVERY_CHUNK_MAX = 32768
CANONICAL_ROOT_NAMES = {"App", "Backups", "Data", "Inbox", "Infra", "Rollback"}


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value).strip().split("."))
    except ValueError:
        return ()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"unsafe JSON path:{path}")
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _release_version(root: Path) -> str:
    path = root / "App/VERSIE.txt"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("active_release_missing_or_unsafe")
    version = path.read_text(encoding="utf-8").strip()
    if _version_tuple(version) < MIN_VERSION:
        raise RuntimeError("ROOT cleanup requires active 32.5.30+")
    return version


def _release_controller(root: Path) -> dict[str, Any]:
    for path in (
        root / "Data/03_Systeem/Projectmanager/ReleaseController/current.json",
        Path(project_system_path(root, "Inbox/release_controller/current.json")),
    ):
        value = _json(path)
        if value:
            return value
    return {}


def _release_idle(root: Path, version: str) -> None:
    controller = _release_controller(root)
    if str(controller.get("status") or "").upper() != "COMPLETE" or str(controller.get("phase") or "").upper() != "COMPLETE":
        raise RuntimeError("release_controller_not_complete")
    if str(controller.get("to_version") or version) not in {"", version}:
        raise RuntimeError("release_controller_version_mismatch")

    processing = root / "Inbox/processing"
    if processing.exists() and (processing.is_symlink() or not processing.is_dir()):
        raise RuntimeError("processing_path_unsafe")
    if processing.is_dir() and any(processing.iterdir()):
        raise RuntimeError("processing_not_empty")

    atomic = _json(Path(project_system_path(root, "Inbox/atomic_app_swap_state.json")))
    if str(atomic.get("state") or "").upper() != "ACCEPTED" or str(atomic.get("to_version") or "") != version:
        raise RuntimeError("atomic_release_not_accepted")

    ha = _json(Path(project_system_path(root, "Inbox/ha_runtime/current.json")))
    if str(ha.get("version") or "") != version:
        raise RuntimeError("ha_runtime_not_current")

    if (root / "Inbox/.installer.lock").exists():
        raise RuntimeError("installer_lock_active")


def _tree_rows(path: Path, root: Path) -> list[dict[str, Any]]:
    if path.is_symlink():
        raise RuntimeError(f"symlink refused:{path}")
    if not path.exists():
        return []
    seq = [path] if path.is_file() else [path, *sorted(path.rglob("*"), key=lambda p: p.as_posix())]
    rows: list[dict[str, Any]] = []
    for item in seq:
        if item.is_symlink():
            raise RuntimeError(f"symlink refused:{item}")
        rel = item.relative_to(root).as_posix()
        if item.is_file():
            rows.append({"path": rel, "type": "file", "size": item.stat().st_size, "sha256": _sha(item)})
        elif item.is_dir():
            rows.append({"path": rel, "type": "directory"})
    return rows


def _rollback_inventory(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    paths = list(root.glob("App.__rollback_*"))
    canonical = root / "Rollback"
    if canonical.is_dir() and not canonical.is_symlink():
        paths.extend(canonical.glob("App.__rollback_*"))
    for path in paths:
        if path.is_symlink() or not path.is_dir():
            continue
        version_path = path / "VERSIE.txt"
        try:
            version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else path.name.split("App.__rollback_", 1)[-1]
        except OSError:
            version = ""
        rows.append({
            "source": path.relative_to(root).as_posix(),
            "name": path.name,
            "version": version,
            "version_tuple": list(_version_tuple(version)),
            "tree_sha256": project_clearup.tree_sha256(path),
            "legacy_root": path.parent == root,
        })
    rows.sort(key=lambda item: tuple(item["version_tuple"]), reverse=True)
    return rows


def _root_scoped_clearup_items(root: Path, version: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = project_clearup.build_clearup_plan(root, current_version=version, keep_rollbacks=3)
    clear: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    for item in base.get("items") or []:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source_path") or "")
        if "/" in source and not source.startswith("Rollback/App.__rollback_"):
            continue
        record = {
            "source": source,
            "kind": "quarantine",
            "tree_sha256": item.get("tree_sha256"),
            "category": item.get("category"),
            "reason": item.get("reason"),
            "active_references": item.get("active_references") or [],
            "recovery_required": str(item.get("category") or "") != "release_rollback",
            "rollback_recovery_waiver": str(item.get("category") or "") == "release_rollback",
        }
        if item.get("disposition") == "CLEARUP":
            clear.append(record)
        else:
            review.append({**record, "reason": "dependency_review_required"})
    return clear, review


def build_root_cleanup_plan(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    version = _release_version(root)
    _release_idle(root, version)

    actions, review = _root_scoped_clearup_items(root, version)
    rollback_rows = _rollback_inventory(root)

    by_version: dict[str, list[dict[str, Any]]] = {}
    for row in rollback_rows:
        by_version.setdefault(str(row.get("version") or ""), []).append(row)
    duplicate_versions = {key: rows for key, rows in by_version.items() if key and len(rows) > 1}
    for key, rows in sorted(duplicate_versions.items()):
        review.append({
            "kind": "duplicate_rollback_version",
            "version": key,
            "sources": [row["source"] for row in rows],
            "reason": "duplicate rollback version requires explicit review",
        })

    retained_versions: list[str] = []
    for row in rollback_rows:
        value = str(row.get("version") or "")
        if value and value not in retained_versions:
            retained_versions.append(value)
        if len(retained_versions) >= 3:
            break

    action_sources = {str(item.get("source") or "") for item in actions}
    for row in rollback_rows:
        if not row.get("legacy_root"):
            continue
        version_value = str(row.get("version") or "")
        source = str(row["source"])
        if version_value not in retained_versions or version_value in duplicate_versions:
            continue
        target = f"Rollback/{row['name']}"
        target_path = root / target
        if target_path.exists() or target_path.is_symlink():
            review.append({
                "kind": "migrate_rollback",
                "source": source,
                "target": target,
                "version": version_value,
                "reason": "canonical rollback target already exists",
            })
            continue
        actions.append({
            "kind": "migrate_rollback",
            "source": source,
            "target": target,
            "version": version_value,
            "tree_sha256": row["tree_sha256"],
            "recovery_required": False,
            "rollback_recovery_waiver": True,
        })
        action_sources.add(source)

    legacy_clearup = root / "CLEARUP"
    if legacy_clearup.exists() or legacy_clearup.is_symlink():
        target = root / LEGACY_CLEARUP_TARGET_REL
        if legacy_clearup.is_symlink() or not legacy_clearup.is_dir():
            review.append({"kind": "migrate_legacy_clearup", "source": "CLEARUP", "reason": "legacy CLEARUP path unsafe"})
        elif target.exists() or target.is_symlink():
            review.append({"kind": "migrate_legacy_clearup", "source": "CLEARUP", "target": LEGACY_CLEARUP_TARGET_REL.as_posix(), "reason": "legacy CLEARUP target already exists"})
        else:
            actions.append({
                "kind": "migrate_legacy_clearup",
                "source": "CLEARUP",
                "target": LEGACY_CLEARUP_TARGET_REL.as_posix(),
                "tree_sha256": project_clearup.tree_sha256(legacy_clearup),
                "recovery_required": False,
                "rollback_recovery_waiver": False,
            })
            action_sources.add("CLEARUP")

    snapshot = root_structure_snapshot(root)
    known_debt = set(str(x) for x in snapshot.get("known_debt") or [])
    covered_top = {source.split("/", 1)[0] for source in action_sources if source}
    covered_top.update(str(item.get("source") or "").split("/", 1)[0] for item in review if item.get("source"))
    unhandled_known = sorted(name for name in known_debt if name not in covered_top)
    for name in unhandled_known:
        review.append({"kind": "unhandled_root_debt", "source": name, "reason": "known root debt is not safely classified by ROOT cleanup"})

    for name in snapshot.get("unclassified_items") or []:
        review.append({"kind": "unclassified_root_item", "source": str(name), "reason": "unclassified root item"})

    actions.sort(key=lambda item: (0 if item.get("kind") == "migrate_rollback" else 1 if item.get("kind") == "migrate_legacy_clearup" else 2, str(item.get("source") or "")))
    identity = {
        "schema": PLAN_SCHEMA,
        "release_version": version,
        "canonical_root_names": sorted(CANONICAL_ROOT_NAMES),
        "rollback_keep_count": 3,
        "retained_rollback_versions": retained_versions,
        "actions": actions,
        "review": review,
    }
    plan_sha256 = _json_sha(identity)
    recovery_count = sum(1 for item in actions if item.get("recovery_required") is True)
    return {
        **identity,
        "plan_sha256": plan_sha256,
        "confirmation_required": f"APPLY ROOT CLEANUP {plan_sha256[:16]}",
        "status": "READY" if not review else "REVIEW_REQUIRED",
        "action_count": len(actions),
        "review_count": len(review),
        "recovery_required_count": recovery_count,
        "rollback_waiver_count": sum(1 for item in actions if item.get("rollback_recovery_waiver") is True),
        "delete_capability": "FINALIZE_ONLY",
    }


def inventory_root_cleanup(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_root_cleanup_plan(root)
    return {
        "schema": "energie_root_cleanup_inventory_v1",
        "status": plan["status"],
        "release_version": plan["release_version"],
        "plan_sha256": plan["plan_sha256"],
        "root_items": sorted(path.name for path in root.iterdir()),
        "canonical_root_names": sorted(CANONICAL_ROOT_NAMES),
        "retained_rollback_versions": plan["retained_rollback_versions"],
        "action_count": plan["action_count"],
        "review_count": plan["review_count"],
        "recovery_required_count": plan["recovery_required_count"],
        "actions": plan["actions"],
        "review": plan["review"],
    }


def _recovery_paths(root: Path, plan_sha256: str) -> tuple[Path, Path, Path]:
    key = plan_sha256[:24]
    stage = root / RECOVERY_ROOT_REL / f"RootCleanup_{key}"
    export = root / EXPORT_ROOT_REL / f"RootCleanup_{key}_recovery.zip"
    state = root / STATE_ROOT_REL / f"ROOT_CLEANUP_RECOVERY_{key}.json"
    return stage, export, state


def _copy_exact(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.exists():
        raise RuntimeError(f"recovery source missing/unsafe:{source}")
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, symlinks=False)


def prepare_root_recovery(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_root_cleanup_plan(root)
    if plan["review_count"]:
        return {"status": "REVIEW_REQUIRED", "executed": False, "plan_sha256": plan["plan_sha256"], "review_count": plan["review_count"]}

    required = [item for item in plan["actions"] if item.get("recovery_required") is True]
    stage, export, state_path = _recovery_paths(root, plan["plan_sha256"])
    if not required:
        state = {
            "schema": "energie_root_cleanup_recovery_state_v1",
            "status": "WAIVED",
            "plan_sha256": plan["plan_sha256"],
            "external_confirmed": True,
            "size": 0,
            "sha256": None,
        }
        _atomic_json(state_path, state)
        return {**state, "executed": True}

    if stage.exists() or stage.is_symlink():
        if stage.is_symlink() or not stage.is_dir():
            raise RuntimeError("ROOT recovery staging path unsafe")
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    manifest_items: list[dict[str, Any]] = []
    for item in required:
        source_rel = str(item["source"])
        source = root / source_rel
        rows = _tree_rows(source, root)
        if _json_sha(rows) != _json_sha(_tree_rows(source, root)):
            raise RuntimeError(f"recovery source changed during snapshot:{source_rel}")
        _copy_exact(source, stage / "original" / source_rel)
        manifest_items.append({"source": source_rel, "source_rows": rows, "tree_sha256": item.get("tree_sha256")})

    manifest = {
        "schema": "energie_root_cleanup_recovery_v1",
        "plan_sha256": plan["plan_sha256"],
        "release_version": plan["release_version"],
        "deletion_performed": False,
        "items": manifest_items,
    }
    _atomic_json(stage / "RECOVERY_MANIFEST.json", manifest)
    export.parent.mkdir(parents=True, exist_ok=True)
    temp = export.with_name(f".{export.name}.tmp-{secrets.token_hex(4)}")
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob("*"), key=lambda p: p.as_posix()):
                arc = path.relative_to(stage).as_posix()
                if path.is_symlink():
                    raise RuntimeError("recovery staging symlink refused")
                if path.is_dir():
                    archive.writestr(arc.rstrip("/") + "/", b"")
                else:
                    archive.write(path, arc)
        with zipfile.ZipFile(temp) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"recovery ZIP corrupt:{bad}")
        os.replace(temp, export)
    finally:
        temp.unlink(missing_ok=True)

    artifact_sha = _sha(export)
    state = {
        "schema": "energie_root_cleanup_recovery_state_v1",
        "status": "GREEN",
        "plan_sha256": plan["plan_sha256"],
        "artifact": export.name,
        "size": export.stat().st_size,
        "sha256": artifact_sha,
        "external_confirmed": False,
        "external_confirmation_required": f"CONFIRM ROOT RECOVERY {artifact_sha[:16]}",
    }
    _atomic_json(state_path, state)
    return {**state, "executed": True}


def root_recovery_export_info(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_root_cleanup_plan(root)
    _stage, export, state_path = _recovery_paths(root, plan["plan_sha256"])
    state = _json(state_path)
    if state.get("status") == "WAIVED":
        return state
    if state.get("schema") != "energie_root_cleanup_recovery_state_v1" or state.get("status") != "GREEN":
        raise RuntimeError("ROOT recovery state missing/invalid")
    if export.is_symlink() or not export.is_file():
        raise RuntimeError("ROOT recovery ZIP missing/unsafe")
    with zipfile.ZipFile(export) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"ROOT recovery ZIP corrupt:{bad}")
    sha = _sha(export)
    if sha != state.get("sha256") or export.stat().st_size != int(state.get("size") or -1):
        raise RuntimeError("ROOT recovery artifact identity mismatch")
    return {**state, "artifact": export.name, "size": export.stat().st_size, "sha256": sha}


def root_recovery_export_chunk(project_root: Path | str, *, offset: int = 0, max_bytes: int = RECOVERY_CHUNK_MAX) -> dict[str, Any]:
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be non-negative integer")
    if type(max_bytes) is not int or not 1 <= max_bytes <= RECOVERY_CHUNK_MAX:
        raise ValueError(f"max_bytes must be 1..{RECOVERY_CHUNK_MAX}")
    root = Path(project_root).resolve()
    info = root_recovery_export_info(root)
    if not info.get("artifact"):
        return {**info, "offset": 0, "bytes": 0, "next_offset": 0, "eof": True, "base64": ""}
    plan = build_root_cleanup_plan(root)
    _stage, export, _state = _recovery_paths(root, plan["plan_sha256"])
    with export.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(max_bytes)
    next_offset = offset + len(data)
    return {
        **info,
        "offset": offset,
        "bytes": len(data),
        "next_offset": next_offset,
        "eof": next_offset >= export.stat().st_size,
        "chunk_sha256": hashlib.sha256(data).hexdigest(),
        "base64": base64.b64encode(data).decode("ascii"),
    }


def confirm_root_recovery(project_root: Path | str, *, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    info = root_recovery_export_info(root)
    if info.get("external_confirmed") is True:
        return {**info, "status": "GREEN", "executed": False}
    expected = str(info.get("external_confirmation_required") or "")
    if source != "mcp_remote" or " ".join(str(explicit_user_text or "").strip().split()).upper() != expected.upper():
        return {"status": "APPROVAL_REQUIRED", "executed": False, "confirmation_required": expected}
    plan = build_root_cleanup_plan(root)
    _stage, _export, state_path = _recovery_paths(root, plan["plan_sha256"])
    state = _json(state_path)
    state["external_confirmed"] = True
    state["external_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_json(state_path, state)
    return {**state, "status": "GREEN", "executed": True}


def _recovery_proof(root: Path, plan: dict[str, Any]) -> dict[str, Any]:
    if int(plan.get("recovery_required_count") or 0) == 0:
        return {"required": False, "confirmed": True, "rollback_waiver": True}
    info = root_recovery_export_info(root)
    if info.get("external_confirmed") is not True:
        raise RuntimeError("ROOT recovery external confirmation missing")
    return {
        "required": True,
        "confirmed": True,
        "plan_sha256": plan["plan_sha256"],
        "artifact": info.get("artifact"),
        "size": info.get("size"),
        "sha256": info.get("sha256"),
    }


def _watcher_call(root: Path, *, operation: str, plan: dict[str, Any] | None = None, run_id: str = "", recovery: dict[str, Any] | None = None) -> dict[str, Any]:
    request_path = Path(project_system_path(root, WATCHER_REQUEST_REL.as_posix()))
    if request_path.exists():
        raise RuntimeError("another ClearUp request is already active")
    request_id = secrets.token_hex(16)
    result_rel = WATCHER_RESULT_ROOT_REL / f"{request_id}.json"
    result_path = root / result_rel
    result_path.unlink(missing_ok=True)
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "operation": operation,
        "release_version": _release_version(root),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=WATCHER_TIMEOUT_SECONDS)).isoformat(),
        "result_path": result_rel.as_posix(),
        "explicit_user_approval": True,
    }
    if plan is not None:
        payload["plan"] = plan
        payload["plan_sha256"] = plan.get("plan_sha256")
    if recovery is not None:
        payload["recovery"] = recovery
    if run_id:
        payload["run_id"] = run_id
    _atomic_json(request_path, payload)
    try:
        deadline = time.monotonic() + WATCHER_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            response = _json(result_path)
            if response and response.get("request_id") == request_id:
                if response.get("schema") != RESULT_SCHEMA:
                    raise RuntimeError("ROOT cleanup result schema mismatch")
                if response.get("status") != "completed":
                    raise RuntimeError(f"ROOT cleanup executor {response.get('status')}:{response.get('error')}")
                result = response.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("ROOT cleanup result missing")
                return result
            time.sleep(0.2)
        raise RuntimeError("ROOT cleanup watcher timeout")
    finally:
        try:
            current = _json(request_path)
            if current.get("request_id") == request_id:
                request_path.unlink(missing_ok=True)
        except OSError:
            pass


def apply_root_cleanup(project_root: Path | str, *, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_root_cleanup_plan(root)
    if plan["review_count"]:
        return {"status": "REVIEW_REQUIRED", "executed": False, "review_count": plan["review_count"], "plan_sha256": plan["plan_sha256"]}
    expected = str(plan["confirmation_required"])
    if source != "mcp_remote" or " ".join(str(explicit_user_text or "").strip().split()).upper() != expected.upper():
        return {"status": "APPROVAL_REQUIRED", "executed": False, "confirmation_required": expected, "plan_sha256": plan["plan_sha256"]}
    return _watcher_call(root, operation="root_apply", plan=plan, recovery=_recovery_proof(root, plan))


def restore_root_cleanup(project_root: Path | str, *, run_id: str, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run_id = str(run_id or "").strip()
    expected = f"RESTORE ROOT CLEANUP {run_id}"
    if source != "mcp_remote" or " ".join(str(explicit_user_text or "").strip().split()).upper() != expected.upper():
        return {"status": "APPROVAL_REQUIRED", "executed": False, "confirmation_required": expected, "run_id": run_id}
    return _watcher_call(root, operation="root_restore", run_id=run_id)


def finalize_root_cleanup(project_root: Path | str, *, run_id: str, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run_id = str(run_id or "").strip()
    expected = f"FINALIZE ROOT CLEANUP {run_id}"
    if source != "mcp_remote" or " ".join(str(explicit_user_text or "").strip().split()).upper() != expected.upper():
        return {"status": "APPROVAL_REQUIRED", "executed": False, "confirmation_required": expected, "run_id": run_id}
    return _watcher_call(root, operation="root_finalize", run_id=run_id)
