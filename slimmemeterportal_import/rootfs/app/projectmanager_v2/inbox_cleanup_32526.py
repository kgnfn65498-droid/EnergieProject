from __future__ import annotations

"""32.5.26 scoped final Inbox cleanup orchestration.

This module is intentionally *not* a privileged filesystem executor.  It builds
an exact, hash-bound plan, publishes it through the existing 32.5.x ClearUp
sideband, and waits for the privileged watcher/executor to return the result.
All mutations therefore stay on the proven 32.5.x execution boundary.
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

from system_path_contract import project_system_path

MIN_VERSION = (32, 5, 26)
SCOPED_REQUEST_SCHEMA = "energie_clearup_scoped_request_v1"
SCOPED_RESULT_SCHEMA = "energie_clearup_scoped_result_v1"
PLAN_SCHEMA = "energie_clearup_scoped_plan_v1"
WATCHER_REQUEST_REL = Path("Inbox/projectmanager_v2/RuntimeV2/clearup/project_clearup_move_request.json")
WATCHER_RESULT_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Runtime/results")
WATCHER_TIMEOUT_SECONDS = 90.0
RECOVERY_CHUNK_MAX = 32768

FINAL_LEGACY = (
    "Inbox/release_hold_tmp",
    "Inbox/crash_recovery_cleanup_result.json",
    "Inbox/github_publication_state.pre_59_recovery.json",
    "Inbox/ha_publication_required.json.corrective.22616",
    "Inbox/ha_publication_required.json.settled.10928",
    "Inbox/.github_publisher.lock",
    "Inbox/watcher_recreate_request.json",
    "Inbox/project_clearup_move_request.json",
    "Inbox/.publisher-rw-probe",
)
FAILED_BUCKETS = ("corrupt", "rejected", "rolled_back", "withdrawn", "duplicates")
CONSUMED = {"APPLIED", "IGNORED_ALREADY_RESOLVED", "REJECTED", "RESOLVED", "CONSUMED"}
CANONICAL_REQUIRED = (
    "Data/03_Systeem/Projectmanager/ApprovalIngress",
    "Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup",
    "Data/03_Systeem/Projectmanager/Runtime/Locks",
    "Data/03_Systeem/Projectmanager/RuntimeV2",
)


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in str(value).split(".")[:3])
    except ValueError:
        return ()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"unsafe JSON result path: {path}")
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _recovery_paths(root: Path, version: str) -> tuple[Path, Path, Path]:
    safe_version = str(version).replace("/", "_").replace("\\", "_")
    stage = root / "Data/03_Systeem/Projectmanager/ClearUp/Recovery" / f"FinalInbox_v{safe_version}"
    export = root / "Data/03_Systeem/Projectmanager/ClearUp/Exports" / f"FinalInboxCleanup_v{safe_version}_recovery.zip"
    state = root / "Data/03_Systeem/Projectmanager/ClearUp/State" / f"FINAL_INBOX_RECOVERY_v{safe_version}.json"
    return stage, export, state


def _copy_exact(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.exists():
        raise RuntimeError(f"recovery source missing/unsafe:{source}")
    if source.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target, symlinks=False)


def _remove_internal_tree(path: Path) -> None:
    """Remove only private recovery staging; never used for live Inbox cleanup."""
    if not path.exists():
        return
    if path.is_symlink() or not path.is_dir():
        raise RuntimeError("internal recovery staging path unsafe")
    for item in sorted(path.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if item.is_symlink():
            raise RuntimeError("internal recovery staging symlink refused")
        if item.is_dir():
            item.rmdir()
        else:
            item.unlink()
    path.rmdir()


def _verify_final_recovery_zip(path: Path, expected_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("final Inbox recovery ZIP missing/unsafe")
    try:
        with zipfile.ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f"final Inbox recovery ZIP corrupt:{bad}")
            manifest = json.loads(archive.read("RECOVERY_MANIFEST.json"))
            if not isinstance(manifest, dict) or manifest.get("schema") != "energie_final_inbox_recovery_v1":
                raise RuntimeError("final Inbox recovery manifest invalid")
            if manifest.get("deletion_performed") is not False:
                raise RuntimeError("final Inbox recovery manifest is not pre-mutation")
            if expected_manifest is not None and manifest != expected_manifest:
                raise RuntimeError("final Inbox recovery manifest mismatch")
            names = set(archive.namelist())
            for item in manifest.get("items") or []:
                rows = item.get("source_rows") if isinstance(item, dict) else None
                if not isinstance(rows, list):
                    raise RuntimeError("final Inbox recovery source_rows missing")
                for row in rows:
                    if not isinstance(row, dict) or row.get("type") != "file":
                        continue
                    member = "original/" + str(row.get("path") or "")
                    if member not in names:
                        raise RuntimeError(f"final Inbox recovery payload missing:{member}")
                    data = archive.read(member)
                    if len(data) != int(row.get("size") if row.get("size") is not None else -1):
                        raise RuntimeError(f"final Inbox recovery payload size mismatch:{member}")
                    if hashlib.sha256(data).hexdigest() != str(row.get("sha256") or ""):
                        raise RuntimeError(f"final Inbox recovery payload hash mismatch:{member}")
            return manifest
    except (OSError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        raise RuntimeError("final Inbox recovery ZIP verification failed") from exc


def _release_version(root: Path) -> str:
    path = root / "App/VERSIE.txt"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("active_release_missing_or_unsafe")
    version = path.read_text(encoding="utf-8").strip()
    if _version_tuple(version) < MIN_VERSION:
        raise RuntimeError("final Inbox cleanup requires active 32.5.26+")
    return version


def _release_controller(root: Path) -> dict[str, Any]:
    candidates = (
        root / "Data/03_Systeem/Projectmanager/ReleaseController/current.json",
        Path(project_system_path(root, "Inbox/release_controller/current.json")),
    )
    for path in candidates:
        value = _json(path)
        if value:
            return value
    return {}


def _release_idle(root: Path, version: str) -> None:
    state = _release_controller(root)
    if str(state.get("status") or "").upper() != "COMPLETE" or str(state.get("phase") or "").upper() != "COMPLETE":
        raise RuntimeError("release_controller_not_complete")
    to_version = str(state.get("to_version") or version)
    if to_version not in {"", version}:
        raise RuntimeError("release_controller_version_mismatch")
    processing = root / "Inbox/processing"
    if processing.exists() and (processing.is_symlink() or not processing.is_dir()):
        raise RuntimeError("processing_path_unsafe")
    if processing.is_dir() and any(p.is_file() and p.suffix == ".zip" for p in processing.iterdir()):
        raise RuntimeError("active_processing_release")


def _tree_rows(path: Path, root: Path) -> list[dict[str, Any]]:
    if path.is_symlink():
        raise RuntimeError(f"symlink refused: {path}")
    if not path.exists():
        return []
    seq = [path] if path.is_file() else [path, *sorted(path.rglob("*"), key=lambda p: p.as_posix())]
    rows: list[dict[str, Any]] = []
    for item in seq:
        if item.is_symlink():
            raise RuntimeError(f"symlink refused: {item}")
        rel = item.relative_to(root).as_posix()
        if item.is_file():
            rows.append({"path": rel, "type": "file", "size": item.stat().st_size, "sha256": _sha(item)})
        elif item.is_dir():
            rows.append({"path": rel, "type": "directory"})
    return rows


def _tree_digest(rows: list[dict[str, Any]]) -> str:
    return _json_sha(rows)


def _legacy_approval_ids(root: Path) -> list[str]:
    base = root / "Inbox/projectmanager_v2/ApprovalIngress"
    if not base.exists():
        return []
    if base.is_symlink() or not base.is_dir():
        raise RuntimeError("legacy_approval_root_unsafe")
    return sorted(p.stem for p in base.glob("*.json") if p.is_file() and not p.is_symlink())


def _unconsumed_legacy_approvals(root: Path) -> list[str]:
    receipts = _json(root / "Data/03_Systeem/Projectmanager/RuntimeV2/decisions/approval_ingress_receipts.json").get("items") or {}
    out: list[str] = []
    for ident in _legacy_approval_ids(root):
        row = receipts.get(ident) if isinstance(receipts, dict) else None
        if not isinstance(row, dict) or str(row.get("status") or "").upper() not in CONSUMED:
            out.append(ident)
    return out


def _binding_contract(root: Path) -> list[str]:
    """Return exact legacy-writer/read-path blockers still present in 32.5.26 code."""
    checks = (
        (
            "App/slimmemeterportal_import/rootfs/app/projectmanager_v2/projectmanager_web.py",
            ("Inbox/projectmanager_v2/ApprovalIngress",),
        ),
        (
            "App/slimmemeterportal_import/rootfs/app/projectmanager_v2/embedded_config.py",
            ("Inbox/projectmanager_v2/ApprovalIngress",),
        ),
        (
            "App/slimmemeterportal_import/rootfs/app/operating_mode_crash_recovery.py",
            ('project_root / "Inbox/crash_recovery_cleanup_result.json"',),
        ),
        (
            "App/tools/nas_github_publisher.sh",
            ('LOCK="$ROOT/Inbox/.github_publisher.lock"',),
        ),
    )
    blockers: list[str] = []
    for relative, forbidden in checks:
        path = root / relative
        if path.is_symlink() or not path.is_file():
            blockers.append(f"contract_file_missing:{relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            blockers.append(f"contract_file_unreadable:{relative}")
            continue
        for token in forbidden:
            if token in text:
                blockers.append(f"legacy_reference:{relative}:{token}")
    return blockers


def _failed_nested(root: Path) -> list[str]:
    base = root / "Inbox/failed"
    if not base.exists():
        return []
    if base.is_symlink() or not base.is_dir():
        raise RuntimeError("failed_root_unsafe")
    return sorted(p.name for p in base.iterdir() if p.is_dir() and not p.is_symlink())


def _flat_target(base: Path, source: Path) -> Path:
    candidate = base / source.name
    if not candidate.exists():
        return candidate
    if candidate.is_symlink() or not candidate.is_file():
        raise RuntimeError(f"failed_flat_target_unsafe:{candidate.name}")
    source_sha = _sha(source)
    digest = source_sha[:12]
    if _sha(candidate) == source_sha:
        candidate = base / f"{source.stem}.duplicate.{digest}{source.suffix}"
    else:
        candidate = base / f"{source.stem}.moved.{digest}{source.suffix}"
    counter = 1
    original = candidate
    while candidate.exists():
        candidate = original.with_name(f"{original.stem}.{counter}{original.suffix}")
        counter += 1
    return candidate


def _snapshot_release_dirs(root: Path) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for rel in ("Inbox/incoming", "Inbox/processing", "Inbox/processed"):
        base = root / rel
        rows: list[dict[str, Any]] = []
        if base.exists():
            if base.is_symlink() or not base.is_dir():
                raise RuntimeError(f"release_mailbox_unsafe:{rel}")
            for path in sorted(base.rglob("*"), key=lambda p: p.as_posix()):
                if path.is_symlink():
                    raise RuntimeError(f"release_mailbox_symlink:{path}")
                if path.is_file():
                    rows.append({"path": path.relative_to(base).as_posix(), "size": path.stat().st_size, "sha256": _sha(path)})
        result[rel] = rows
    return result


def inventory_final_inbox_cleanup(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    version = _release_version(root)
    _release_idle(root, version)
    processing = root / "Inbox/processing"
    unconsumed = _unconsumed_legacy_approvals(root)
    nested = _failed_nested(root)
    missing = [rel for rel in CANONICAL_REQUIRED if not (root / rel).exists() or (root / rel).is_symlink()]
    contract_blockers = _binding_contract(root)
    blockers: list[str] = []
    if processing.is_symlink() or not processing.is_dir():
        blockers.append("processing_mailbox_missing_or_unsafe")
    elif any(processing.iterdir()):
        blockers.append("processing_mailbox_not_empty")
    if (root / "Inbox/ha_publication_required.json").exists():
        blockers.append("active_ha_publication_contract")
    if unconsumed:
        blockers.append("unconsumed_legacy_approvals")
    if missing:
        blockers.append("canonical_destination_missing")
    if contract_blockers:
        blockers.append("legacy_code_binding_present")
    return {
        "schema": "energie_final_inbox_cleanup_inventory_v2",
        "status": "READY" if not blockers else "BLOCKED",
        "release_version": version,
        "blockers": blockers,
        "failed_nested_directories": nested,
        "unconsumed_legacy_approvals": unconsumed,
        "missing_canonical_destinations": missing,
        "contract_blockers": contract_blockers,
        "legacy_candidates": [rel for rel in FINAL_LEGACY if (root / rel).exists()],
        "processing_directory_present_and_empty": processing.is_dir() and not processing.is_symlink() and not any(processing.iterdir()),
        "projectmanager_v2_present": (root / "Inbox/projectmanager_v2").exists(),
        "projectmanager_v2_last": True,
        "privileged_executor": "App/tools/project_clearup_move_executor.py",
        "transport": "32.5.x request-scoped sideband",
        "delete_capability": False,
    }


def build_cleanup_plan(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    inventory = inventory_final_inbox_cleanup(root)
    if inventory["status"] != "READY":
        raise RuntimeError("final Inbox cleanup is not READY: " + ",".join(inventory.get("blockers") or []))
    version = inventory["release_version"]
    actions: list[dict[str, Any]] = []

    failed = root / "Inbox/failed"
    if failed.exists():
        if failed.is_symlink() or not failed.is_dir():
            raise RuntimeError("failed_root_unsafe")
        for bucket in FAILED_BUCKETS:
            directory = failed / bucket
            if not directory.exists():
                continue
            if directory.is_symlink() or not directory.is_dir():
                raise RuntimeError(f"failed_bucket_unsafe:{bucket}")
            for source in sorted(directory.iterdir(), key=lambda p: p.name):
                if source.is_symlink() or not source.is_file():
                    raise RuntimeError(f"failed_bucket_contains_nonfile:{bucket}/{source.name}")
                target = _flat_target(failed, source)
                actions.append({
                    "kind": "flatten_failed_file",
                    "source": source.relative_to(root).as_posix(),
                    "target": target.relative_to(root).as_posix(),
                    "size": source.stat().st_size,
                    "sha256": _sha(source),
                })
            actions.append({"kind": "remove_empty_dir", "source": directory.relative_to(root).as_posix(), "role": "failed_bucket"})

    for rel in FINAL_LEGACY:
        source = root / rel
        if not source.exists():
            continue
        rows = _tree_rows(source, root)
        actions.append({"kind": "quarantine", "source": rel, "tree_sha256": _tree_digest(rows), "rows": rows})

    processing = root / "Inbox/processing"
    if processing.is_symlink() or not processing.is_dir():
        raise RuntimeError("processing_mailbox_missing_or_unsafe")
    if any(processing.iterdir()):
        raise RuntimeError("processing_not_empty")

    pm_legacy = root / "Inbox/projectmanager_v2"
    if pm_legacy.exists():
        rows = _tree_rows(pm_legacy, root)
        actions.append({
            "kind": "quarantine",
            "source": "Inbox/projectmanager_v2",
            "tree_sha256": _tree_digest(rows),
            "rows": rows,
            "must_be_last": True,
        })

    identity = {
        "schema": PLAN_SCHEMA,
        "release_version": version,
        "classification": "TYPE3_REVIEW_RESOLVED_AND_FINAL_INBOX",
        "actions": actions,
        "mailbox_snapshot": _snapshot_release_dirs(root),
        "projectmanager_v2_last": True,
        "delete_capability": False,
    }
    plan_sha256 = _json_sha(identity)
    return {**identity, "plan_sha256": plan_sha256, "confirmation_required": f"APPLY INBOX CLEANUP {plan_sha256[:16]}"}


def prepare_final_inbox_recovery(project_root: Path | str, *, source: str = "") -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_cleanup_plan(root)
    version = str(plan["release_version"])
    stage, export, state_path = _recovery_paths(root, version)
    temp_stage = stage.with_name(stage.name + f".tmp-{secrets.token_hex(6)}")
    temp_export = export.with_name(export.name + f".tmp-{secrets.token_hex(6)}")
    items: list[dict[str, Any]] = []
    try:
        temp_stage.mkdir(parents=True, exist_ok=False)
        seen: set[str] = set()
        for action in plan.get("actions") or []:
            kind = str(action.get("kind") or "")
            source_rel = str(action.get("source") or "")
            if kind not in {"flatten_failed_file", "quarantine"} or not source_rel or source_rel in seen:
                continue
            seen.add(source_rel)
            source_path = root / source_rel
            before_rows = _tree_rows(source_path, root)
            if not before_rows:
                raise RuntimeError(f"recovery source missing:{source_rel}")
            staged = temp_stage / "original" / source_rel
            _copy_exact(source_path, staged)
            after_rows = _tree_rows(source_path, root)
            staged_rows = _tree_rows(staged, temp_stage / "original")
            if after_rows != before_rows:
                raise RuntimeError(f"recovery source changed during snapshot:{source_rel}")
            if staged_rows != before_rows:
                raise RuntimeError(f"recovery staged payload mismatch:{source_rel}")
            items.append({"source": source_rel, "kind": kind, "source_rows": before_rows})

        manifest = {
            "schema": "energie_final_inbox_recovery_v1",
            "classification": "TYPE3_FINAL_INBOX",
            "release_version": version,
            "plan_sha256": plan["plan_sha256"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "items": items,
            "deletion_performed": False,
        }
        _atomic_json(temp_stage / "RECOVERY_MANIFEST.json", manifest)
        export.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(temp_export, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(temp_stage.rglob("*"), key=lambda p: p.as_posix()):
                if path.is_symlink():
                    raise RuntimeError("recovery staging symlink refused")
                arc = path.relative_to(temp_stage).as_posix()
                if path.is_dir():
                    archive.writestr(arc.rstrip("/") + "/", b"")
                else:
                    archive.write(path, arc)
        _verify_final_recovery_zip(temp_export, manifest)
        for item in items:
            if _tree_rows(root / item["source"], root) != item["source_rows"]:
                raise RuntimeError(f"recovery source changed after snapshot:{item['source']}")

        if stage.exists():
            if stage.is_symlink() or not stage.is_dir():
                raise RuntimeError("recovery stage path unsafe")
            _remove_internal_tree(stage)
        os.replace(temp_stage, stage)
        os.replace(temp_export, export)
        artifact_sha = _sha(export)
        confirmation = f"CONFIRM INBOX RECOVERY {artifact_sha[:16]}"
        state = {
            "schema": "energie_final_inbox_recovery_state_v1",
            "status": "GREEN",
            "release_version": version,
            "plan_sha256": plan["plan_sha256"],
            "artifact": export.name,
            "size": export.stat().st_size,
            "sha256": artifact_sha,
            "item_count": len(items),
            "external_confirmed": False,
            "external_confirmation_required": confirmation,
            "prepared_at": datetime.now(timezone.utc).isoformat(),
            "deletion_performed": False,
            "source": str(source or ""),
        }
        _atomic_json(state_path, state)
        return {**state, "deletion_performed": False}
    finally:
        if temp_stage.exists() and not temp_stage.is_symlink():
            try:
                _remove_internal_tree(temp_stage)
            except OSError:
                pass
        temp_export.unlink(missing_ok=True)


def final_inbox_recovery_export_info(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    version = _release_version(root)
    _stage, export, state_path = _recovery_paths(root, version)
    state = _json(state_path)
    if state.get("schema") != "energie_final_inbox_recovery_state_v1" or state.get("status") != "GREEN":
        raise RuntimeError("final Inbox recovery state missing/invalid")
    manifest = _verify_final_recovery_zip(export)
    sha = _sha(export)
    if str(state.get("artifact") or "") != export.name or int(state.get("size") or -1) != export.stat().st_size or str(state.get("sha256") or "") != sha:
        raise RuntimeError("final Inbox recovery artifact identity mismatch")
    if str(manifest.get("plan_sha256") or "") != str(state.get("plan_sha256") or ""):
        raise RuntimeError("final Inbox recovery plan identity mismatch")
    return {
        "status": "GREEN",
        "release_version": version,
        "artifact": export.name,
        "size": export.stat().st_size,
        "sha256": sha,
        "plan_sha256": manifest["plan_sha256"],
        "item_count": len(manifest.get("items") or []),
        "external_confirmed": state.get("external_confirmed") is True,
        "external_confirmation_required": state.get("external_confirmation_required"),
        "deletion_performed": False,
    }


def final_inbox_recovery_export_chunk(project_root: Path | str, *, offset: int = 0, max_bytes: int = RECOVERY_CHUNK_MAX) -> dict[str, Any]:
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")
    if type(max_bytes) is not int or max_bytes < 1 or max_bytes > RECOVERY_CHUNK_MAX:
        raise ValueError(f"max_bytes must be 1..{RECOVERY_CHUNK_MAX}")
    root = Path(project_root).resolve()
    info = final_inbox_recovery_export_info(root)
    _stage, export, _state = _recovery_paths(root, info["release_version"])
    total = export.stat().st_size
    if offset > total:
        raise ValueError("offset beyond EOF")
    with export.open("rb") as handle:
        handle.seek(offset)
        data = handle.read(max_bytes)
    nxt = offset + len(data)
    return {
        **info,
        "offset": offset,
        "bytes": len(data),
        "next_offset": nxt,
        "eof": nxt >= total,
        "chunk_sha256": hashlib.sha256(data).hexdigest(),
        "base64": base64.b64encode(data).decode("ascii"),
    }


def validate_final_inbox_recovery_for_apply(project_root: Path | str, plan: dict[str, Any], supplied: dict[str, Any] | None = None, *, require_external_confirmation: bool = True) -> dict[str, Any]:
    root = Path(project_root).resolve()
    version = str(plan.get("release_version") or _release_version(root))
    _stage, export, state_path = _recovery_paths(root, version)
    state = _json(state_path)
    if state.get("schema") != "energie_final_inbox_recovery_state_v1" or state.get("status") != "GREEN":
        raise RuntimeError("recovery missing")
    if str(state.get("plan_sha256") or "") != str(plan.get("plan_sha256") or ""):
        raise RuntimeError("recovery stale plan")
    manifest = _verify_final_recovery_zip(export)
    artifact_sha = _sha(export)
    if str(state.get("sha256") or "") != artifact_sha or int(state.get("size") or -1) != export.stat().st_size:
        raise RuntimeError("recovery artifact identity mismatch")
    if str(manifest.get("plan_sha256") or "") != str(plan.get("plan_sha256") or ""):
        raise RuntimeError("recovery manifest plan mismatch")
    if supplied is not None:
        if str(supplied.get("plan_sha256") or "") != str(plan.get("plan_sha256") or "") or str(supplied.get("sha256") or "") != artifact_sha:
            raise RuntimeError("recovery request identity mismatch")
    if require_external_confirmation:
        if state.get("external_confirmed") is not True or str(state.get("external_confirmed_sha256") or "") != artifact_sha:
            raise RuntimeError("recovery external confirmation missing")
    for item in manifest.get("items") or []:
        source_rel = str(item.get("source") or "")
        rows = item.get("source_rows")
        if not source_rel or not isinstance(rows, list) or _tree_rows(root / source_rel, root) != rows:
            raise RuntimeError(f"recovery source mismatch:{source_rel}")
    return {"sha256": artifact_sha, "size": export.stat().st_size, "plan_sha256": plan["plan_sha256"], "artifact": export.name}


def confirm_final_inbox_recovery(project_root: Path | str, *, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_cleanup_plan(root)
    version = str(plan["release_version"])
    _stage, _export, state_path = _recovery_paths(root, version)
    state = _json(state_path)
    expected = str(state.get("external_confirmation_required") or "")
    normalized = " ".join(str(explicit_user_text or "").strip().split()).upper()
    if source != "mcp_remote" or not expected or normalized != expected.upper():
        return {"status": "APPROVAL_REQUIRED", "executed": False, "confirmation_required": expected}
    proof = validate_final_inbox_recovery_for_apply(root, plan, require_external_confirmation=False)
    updated = dict(state)
    updated["external_confirmed"] = True
    updated["external_confirmed_sha256"] = proof["sha256"]
    updated["external_confirmed_at"] = datetime.now(timezone.utc).isoformat()
    _atomic_json(state_path, updated)
    return {"status": "GREEN", "executed": True, **proof, "external_confirmed": True}


def _watcher_call(root: Path, *, operation: str, plan: dict[str, Any] | None = None, run_id: str = "", explicit_approval: bool = False, recovery: dict[str, Any] | None = None) -> dict[str, Any]:
    request_path = project_system_path(root, WATCHER_REQUEST_REL.as_posix())
    if request_path.is_symlink():
        raise RuntimeError("scoped cleanup request path symlink refused")
    if request_path.exists():
        raise RuntimeError("another ClearUp request is already active")
    request_id = secrets.token_hex(16)
    result_rel = WATCHER_RESULT_ROOT_REL / f"{request_id}.json"
    result_path = root / result_rel
    result_path.unlink(missing_ok=True)
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "schema": SCOPED_REQUEST_SCHEMA,
        "request_id": request_id,
        "operation": operation,
        "release_version": _release_version(root),
        "created_at": now.isoformat(),
        "expires_at": (now + timedelta(seconds=WATCHER_TIMEOUT_SECONDS)).isoformat(),
        "result_path": result_rel.as_posix(),
        "explicit_user_approval": bool(explicit_approval),
    }
    if plan is not None:
        payload["plan"] = plan
        payload["plan_sha256"] = plan.get("plan_sha256")
    if recovery is not None:
        payload["recovery"] = dict(recovery)
    if run_id:
        payload["run_id"] = run_id
    _atomic_json(request_path, payload)
    try:
        deadline = time.monotonic() + WATCHER_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            response = _json(result_path)
            if response and response.get("request_id") == request_id:
                if response.get("schema") != SCOPED_RESULT_SCHEMA:
                    raise RuntimeError("scoped cleanup result schema mismatch")
                status = str(response.get("status") or "")
                if status != "completed":
                    raise RuntimeError(f"scoped cleanup executor {status}: {response.get('error')}")
                result = response.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("scoped cleanup result missing")
                return result
            time.sleep(0.2)
        raise RuntimeError("scoped cleanup watcher timeout")
    finally:
        try:
            current = _json(request_path)
            if current.get("request_id") == request_id:
                request_path.unlink(missing_ok=True)
        except OSError:
            pass


def apply_final_inbox_cleanup(project_root: Path | str, *, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    plan = build_cleanup_plan(root)
    recovery = None
    if _version_tuple(plan.get("release_version", "")) >= (32, 5, 28):
        try:
            recovery = validate_final_inbox_recovery_for_apply(root, plan, require_external_confirmation=True)
        except RuntimeError as exc:
            reason = str(exc)
            status = "RECOVERY_CONFIRMATION_REQUIRED" if "confirmation" in reason or "missing" in reason else "RECOVERY_STALE"
            return {
                "status": status,
                "executed": False,
                "plan_sha256": plan["plan_sha256"],
                "recovery_error": reason,
            }
    normalized = " ".join(str(explicit_user_text or "").strip().split()).upper()
    if source != "mcp_remote" or normalized != plan["confirmation_required"].upper():
        return {
            "status": "APPROVAL_REQUIRED",
            "executed": False,
            "plan_sha256": plan["plan_sha256"],
            "confirmation_required": plan["confirmation_required"],
            "action_count": len(plan["actions"]),
        }
    result = _watcher_call(root, operation="scoped_apply", plan=plan, explicit_approval=True, recovery=recovery)
    return {**result, "plan_sha256": plan["plan_sha256"], "confirmation_required": plan["confirmation_required"]}


def restore_final_inbox_cleanup(project_root: Path | str, *, run_id: str, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run_id = str(run_id or "").strip()
    expected = f"RESTORE INBOX CLEANUP {run_id}"
    normalized = " ".join(str(explicit_user_text or "").strip().split()).upper()
    if not run_id or source != "mcp_remote" or normalized != expected.upper():
        return {"status": "APPROVAL_REQUIRED", "executed": False, "confirmation_required": expected, "run_id": run_id}
    return _watcher_call(root, operation="scoped_restore", run_id=run_id, explicit_approval=True)
