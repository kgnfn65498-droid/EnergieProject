#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Ensure sibling tools are importable both as an executable script and via importlib-based tests.
_TOOL_DIR = Path(__file__).resolve().parent
if str(_TOOL_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOL_DIR))
from system_path_contract import project_system_path

REQUEST_SCHEMA = "energie_project_clearup_move_request_v1"
RESULT_SCHEMA = "energie_project_clearup_move_result_v1"
REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")

TYPE1_DELETE_SCHEMA = "energie_clearup_type1_delete_request_v1"
TYPE1_DELETE_RESULT_SCHEMA = "energie_clearup_type1_delete_result_v1"
TYPE1_CLEARUP_ID = "ClearUp_001"
TYPE2_SCHEMA = "energie_clearup_type2_request_v1"
TYPE2_RESULT_SCHEMA = "energie_clearup_type2_result_v1"
TYPE2_ACTIVATION_SCHEMA = "energie_clearup_system_path_contract_v1"
TYPE2_ACTIVATION_ROOT = Path("Data/03_Systeem/Projectmanager/ClearUp/PathActivation")

def _type2_activation_path(root: Path, key: str) -> Path:
    if not key or not re.fullmatch(r"[a-z0-9_]{2,64}", key):
        raise RequestRejected("TYPE2 path_key ongeldig")
    return root / TYPE2_ACTIVATION_ROOT / f"{key}.json"

def _set_type2_activation(root: Path, *, key: str, source: str, destination: str, active: bool, clearup_id: str, plan_sha256: str) -> None:
    path=_type2_activation_path(root,key)
    payload={
        "schema":TYPE2_ACTIVATION_SCHEMA,"key":key,"source":source,"destination":destination,
        "active":bool(active),"clearup_id":clearup_id,"plan_sha256":plan_sha256,
        "updated_at":datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write_json(path,payload)


TYPE1_ROOTS = (
    "Inbox/.bridge_patch_stage_20260914T171141Z",
    "Inbox/live_bridge_backup_20260914T171141Z",
    "Inbox/live_bridge_backup_queue_schema_20260914T172223Z",
    "Inbox/.release-transition.operation.lock.backup_20260914T1812Z",
)


class RequestRejected(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequestRejected(f"request JSON ongeldig: {exc}") from exc
    if not isinstance(value, dict):
        raise RequestRejected("request moet een JSON-object zijn")
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"resultaatpad mag geen symlink zijn: {path}")
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _parse_utc(value: Any, field: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RequestRejected(f"{field} ontbreekt")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RequestRejected(f"{field} ongeldig") from exc
    if parsed.tzinfo is None:
        raise RequestRejected(f"{field} moet timezone-aware zijn")
    return parsed.astimezone(timezone.utc)


def _load_state_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequestRejected(f"{label} ontbreekt of is ongeldig: {exc}") from exc
    if not isinstance(value, dict):
        raise RequestRejected(f"{label} moet een JSON-object zijn")
    return value


def _validate_common(root: Path, request: dict[str, Any]) -> tuple[str, str, str, float]:
    if str(request.get("schema") or "") != REQUEST_SCHEMA:
        raise RequestRejected("CLEARUP watcher request schema ongeldig")
    request_id = str(request.get("request_id") or "").strip().lower()
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise RequestRejected("CLEARUP watcher request_id ongeldig")
    operation = str(request.get("operation") or "").strip().lower()
    if operation not in {"apply", "restore"}:
        raise RequestRejected("CLEARUP watcher operation ongeldig")
    release_version = str(request.get("release_version") or "").strip()
    try:
        current_version = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RequestRejected(f"actieve releaseversie onleesbaar: {exc}") from exc
    if not release_version or current_version != release_version:
        raise RequestRejected(
            f"release mismatch: request={release_version or '<leeg>'} current={current_version or '<leeg>'}"
        )

    atomic = _load_state_json(project_system_path(root, 'Inbox/atomic_app_swap_state.json'), "atomic release state")
    hold = _load_state_json(project_system_path(root, 'Inbox/operating_mode/release_validation_hold.json'), "release validation hold")
    pre_acceptance = request.get("pre_acceptance") is True
    if pre_acceptance:
        if operation != "apply":
            raise RequestRejected("pre_acceptance is alleen toegestaan voor CLEARUP apply")
        if str(atomic.get("state") or "").upper() != "LIVE_ACCEPTANCE" or str(atomic.get("to_version") or "") != release_version:
            raise RequestRejected("pre-acceptance CLEARUP vereist LIVE_ACCEPTANCE voor exact deze release")
        hold_status = str(hold.get("validation_status") or "").lower()
        if not (
            hold.get("active") is True
            and str(hold.get("release_version") or "") == release_version
            and hold_status in {"required", "blocked"}
        ):
            raise RequestRejected("pre-acceptance CLEARUP release-hold hoort niet exact bij deze release")
        from_version = str(atomic.get("from_version") or "").strip()
        if not from_version or from_version == release_version:
            raise RequestRejected("pre-acceptance CLEARUP mist geldige source rollback-versie")
        rollback = root / f"App.__rollback_{from_version}"
        if rollback.is_symlink() or not rollback.is_dir():
            raise RequestRejected("pre-acceptance CLEARUP vereist de exacte rollbackdirectory")
        rollback_version = rollback / "VERSIE.txt"
        if not rollback_version.is_file() or rollback_version.read_text(encoding="utf-8").strip() != from_version:
            raise RequestRejected("pre-acceptance CLEARUP rollbackversie is ongeldig")
        if (root / "Inbox/.installer.lock").exists():
            raise RequestRejected("pre-acceptance CLEARUP weigert actieve installer lock")
        if (root / "Inbox/.atomic_app_swap.lock").exists():
            raise RequestRejected("pre-acceptance CLEARUP weigert actieve atomic swap lock")
        processing = root / "Inbox/processing"
        if processing.is_dir() and any(processing.glob("*.zip")):
            raise RequestRejected("pre-acceptance CLEARUP weigert actieve processing release")
    else:
        if str(atomic.get("state") or "").upper() != "ACCEPTED" or str(atomic.get("to_version") or "") != release_version:
            raise RequestRejected("release is niet ACCEPTED voor deze requestversie")
        if hold.get("active") is not False or str(hold.get("validation_status") or "").lower() != "ok":
            raise RequestRejected("release validation hold is niet vrijgegeven")

    clearup_root = root / "CLEARUP"
    if clearup_root.is_symlink() or not clearup_root.is_dir():
        raise RequestRejected("CLEARUP-root ontbreekt, is geen directory of is een symlink")
    try:
        if clearup_root.stat().st_dev != root.stat().st_dev:
            raise RequestRejected("CLEARUP-root staat niet op hetzelfde filesystem")
    except OSError as exc:
        raise RequestRejected(f"CLEARUP-root kan niet worden gevalideerd: {exc}") from exc

    expires_at = _parse_utc(request.get("expires_at"), "expires_at")
    remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        raise RequestRejected("CLEARUP watcher request is verlopen")
    return request_id, operation, release_version, remaining, pre_acceptance


def _load_project_clearup(root: Path):
    module_root = root / "App/slimmemeterportal_import/rootfs/app"
    if not module_root.is_dir():
        raise RequestRejected("actieve App module-root ontbreekt")
    sys.path.insert(0, str(module_root))
    try:
        import project_clearup  # type: ignore
    finally:
        try:
            sys.path.remove(str(module_root))
        except ValueError:
            pass
    return project_clearup


def _load_clearup_chat_service(root: Path):
    module_root = root / "App/slimmemeterportal_import/rootfs/app/projectmanager_v2"
    if not module_root.is_dir():
        raise RequestRejected("projectmanager module-root ontbreekt")
    sys.path.insert(0, str(module_root))
    try:
        import clearup_chat_service  # type: ignore
    finally:
        try:
            sys.path.remove(str(module_root))
        except ValueError:
            pass
    return clearup_chat_service



def _tree_rows(path: Path, base: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists() or path.is_symlink():
        raise RequestRejected(f"tree missing/unsafe: {path}")
    seq = [path] if path.is_file() else [path, *sorted(path.rglob("*"))]
    for q in seq:
        if q.is_symlink():
            raise RequestRejected(f"symlink refused: {q}")
        rel = q.relative_to(base).as_posix()
        if q.is_file():
            h = hashlib.sha256()
            with q.open("rb") as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(block)
            rows.append({"path": rel, "type": "file", "size": q.stat().st_size, "sha256": h.hexdigest()})
        elif q.is_dir():
            rows.append({"path": rel, "type": "directory"})
    return rows


def _copy_exact(source: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise RequestRejected(f"destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_dir():
        shutil.copytree(source, destination, copy_function=shutil.copy2)
    else:
        shutil.copy2(source, destination)


def _remove_path(path: Path) -> None:
    if not os.path.lexists(path):
        return
    if path.is_symlink():
        raise RuntimeError(f"refuse to remove symlink: {path}")
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _type2_validate_request(root: Path, request: dict[str, Any]):
    if str(request.get("schema") or "") != TYPE2_SCHEMA:
        raise RequestRejected("TYPE2 schema ongeldig")
    request_id = str(request.get("request_id") or "").strip().lower()
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise RequestRejected("TYPE2 request_id ongeldig")
    operation = str(request.get("operation") or "")
    if operation not in {"type2_prepare", "type2_migrate", "type2_finalize", "type2_restore"}:
        raise RequestRejected("TYPE2 operation ongeldig")
    clearup_id = str(request.get("clearup_id") or "")
    release_version = str(request.get("release_version") or "").strip()
    try:
        active = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RequestRejected(f"TYPE2 actieve release onleesbaar: {exc}") from exc
    if active != release_version:
        raise RequestRejected("TYPE2 actieve release mismatch")
    expires_at = _parse_utc(request.get("expires_at"), "expires_at")
    if expires_at <= datetime.now(timezone.utc):
        raise RequestRejected("TYPE2 request verlopen")
    controller = _load_state_json(project_system_path(root, 'Inbox/release_controller/current.json'), "release controller")
    if str(controller.get("status") or "").upper() != "COMPLETE" or str(controller.get("phase") or "").upper() != "COMPLETE":
        raise RequestRejected("TYPE2 vereist COMPLETE release controller")
    processing = root / "Inbox/processing"
    if processing.is_dir() and any(p.is_file() and p.name.startswith("EnergieProject_v") and p.suffix == ".zip" for p in processing.iterdir()):
        raise RequestRejected("TYPE2 weigert actieve processing release")
    service = _load_clearup_type2_service(root)
    plan = service._load_plan(root, clearup_id)
    if str(request.get("plan_sha256") or "") != str(plan.get("plan_sha256") or ""):
        raise RequestRejected("TYPE2 plan fingerprint mismatch")
    if operation != "type2_prepare" and request.get("explicit_user_approval") is not True:
        raise RequestRejected("TYPE2 expliciete gebruikersgoedkeuring ontbreekt")
    before = request.get("mailbox_snapshot_before")
    if not isinstance(before, dict) or before != service._snapshot_release_dirs(root):
        raise RequestRejected("TYPE2 incoming/processing changed before execution")
    if operation != "type2_prepare":
        service._contract_checks(root, plan)
    return request_id, operation, clearup_id, plan, service


def _type2_manifest(root: Path, clearup_id: str, plan: dict[str, Any], service) -> dict[str, Any]:
    stage = root / service.STAGING_ROOT_REL / clearup_id
    manifest_path = stage / "TYPE2_MANIFEST.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RequestRejected("TYPE2 recovery manifest ontbreekt")
    data = _read_json(manifest_path)
    if data.get("plan_sha256") != plan.get("plan_sha256") or data.get("clearup_id") != clearup_id:
        raise RequestRejected("TYPE2 recovery manifest mismatch")
    return data


def _verify_type2_source_against_manifest(root: Path, manifest: dict[str, Any]) -> None:
    for item in manifest.get("items") or []:
        source = root / str(item.get("source") or "")
        expected = item.get("source_rows")
        if not isinstance(expected, list) or _tree_rows(source, root) != expected:
            raise RequestRejected(f"TYPE2 source/recovery mismatch: {item.get('source')}")


def execute_type2(root: Path, request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    root = root.resolve()
    request_id, operation, clearup_id, plan, service = _type2_validate_request(root, request)
    stage = root / service.STAGING_ROOT_REL / clearup_id
    export = root / service.EXPORT_ROOT_REL / f"{clearup_id}_Type2_recovery.zip"
    state = root / service.STATE_ROOT_REL / f"{clearup_id}.json"

    if operation == "type2_prepare":
        if stage.exists() or stage.is_symlink():
            if stage.is_symlink():
                raise RequestRejected("TYPE2 staging symlink refused")
            shutil.rmtree(stage)
        stage.mkdir(parents=True, exist_ok=False)
        items = []
        try:
            for item in plan["items"]:
                source_rel = item["source"]; dest_rel = item["destination"]
                source = root / source_rel; destination = root / dest_rel
                if not source.exists():
                    if item.get("optional") is True:
                        continue
                    raise RequestRejected(f"TYPE2 source missing/unsafe: {source_rel}")
                if source.is_symlink():
                    raise RequestRejected(f"TYPE2 source missing/unsafe: {source_rel}")
                if destination.exists() or destination.is_symlink():
                    raise RequestRejected(f"TYPE2 destination must be absent at prepare: {dest_rel}")
                source_rows = _tree_rows(source, root)
                staged = stage / "original" / source_rel
                _copy_exact(source, staged)
                staged_rows = _tree_rows(staged, stage / "original")
                if staged_rows != source_rows:
                    raise RuntimeError(f"TYPE2 staged recovery mismatch: {source_rel}")
                items.append({"source": source_rel, "destination": dest_rel, "source_rows": source_rows, "reason": item.get("reason", ""), "path_key": item.get("path_key", "")})
            manifest = {
                "schema": "energie_clearup_type2_recovery_v1", "classification": "TYPE2",
                "clearup_id": clearup_id, "plan_sha256": plan["plan_sha256"],
                "created_at": datetime.now(timezone.utc).isoformat(), "items": items,
                "deletion_performed": False,
            }
            _atomic_write_json(stage / "TYPE2_MANIFEST.json", manifest)
            export.parent.mkdir(parents=True, exist_ok=True)
            tmp = export.with_name(f".{export.name}.tmp-{os.getpid()}")
            try:
                with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
                    for p in sorted(stage.rglob("*")):
                        if p.is_symlink():
                            raise RequestRejected("TYPE2 staging symlink refused")
                        arc = p.relative_to(stage).as_posix()
                        if p.is_dir():
                            z.writestr(arc.rstrip("/") + "/", b"")
                        else:
                            z.write(p, arc)
                os.replace(tmp, export)
            finally:
                tmp.unlink(missing_ok=True)
            with zipfile.ZipFile(export) as z:
                bad = z.testzip()
                if bad:
                    raise RuntimeError(f"TYPE2 recovery ZIP corrupt: {bad}")
                zipped_manifest = json.loads(z.read("TYPE2_MANIFEST.json"))
                if zipped_manifest != manifest:
                    raise RuntimeError("TYPE2 recovery ZIP manifest mismatch")
            result = {
                "status": "GREEN", "clearup_id": clearup_id, "phase": "PREPARED",
                "artifact": export.name, "artifact_size": export.stat().st_size,
                "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
                "item_count": len(items), "deletion_performed": False,
            }
            _atomic_write_json(state, {**result, "plan_sha256": plan["plan_sha256"]})
            return request_id, result
        except Exception:
            if stage.exists() and not stage.is_symlink():
                shutil.rmtree(stage, ignore_errors=True)
            raise

    manifest = _type2_manifest(root, clearup_id, plan, service)

    if operation == "type2_migrate":
        created = []
        cutover_rows = {}
        try:
            for item in manifest["items"]:
                source = root / item["source"]; destination = root / item["destination"]
                if not source.exists() or source.is_symlink():
                    raise RequestRejected(f"TYPE2 live source missing/unsafe: {item['source']}")
                # Recovery is historical rollback evidence.  Active runtime
                # state may legitimately have changed since prepare; copy the
                # current source atomically at cutover and prove that copy.
                current_rows = _tree_rows(source, root)
                cutover_rows[item["source"]] = current_rows
                _copy_exact(source, destination)
                created.append(destination)
                expected_dest = []
                for row in current_rows:
                    suffix = Path(row["path"]).relative_to(item["source"]).as_posix() if row["path"] != item["source"] else "."
                    dest_path = item["destination"] if suffix == "." else f"{item['destination']}/{suffix}"
                    expected_dest.append({**row, "path": dest_path})
                if _tree_rows(destination, root) != expected_dest:
                    raise RuntimeError(f"TYPE2 destination verification failed: {item['destination']}")
        except Exception:
            for destination in reversed(created):
                try: _remove_path(destination)
                except Exception: pass
            raise
        activated_at_epoch=time.time()
        for item in manifest["items"]:
            key=str(item.get("path_key") or "").strip()
            if key:
                _set_type2_activation(root,key=key,source=item["source"],destination=item["destination"],active=True,clearup_id=clearup_id,plan_sha256=plan["plan_sha256"])
        after = service._snapshot_release_dirs(root)
        if after != request["mailbox_snapshot_before"]:
            raise RuntimeError("TYPE2 release mailboxes changed during migration")
        result = {
            "status": "GREEN", "clearup_id": clearup_id, "phase": "MIGRATED_PENDING_VALIDATION",
            "migrated": [{"source": x["source"], "destination": x["destination"]} for x in manifest["items"]],
            "source_preserved": True, "deletion_performed": False,
        }
        _atomic_write_json(state, {**result, "plan_sha256": plan["plan_sha256"],
                                   "activated_at_epoch": activated_at_epoch,
                                   "cutover_rows": cutover_rows,
                                   "migration_fingerprint": hashlib.sha256(json.dumps(result,sort_keys=True).encode()).hexdigest()})
        return request_id, result

    if operation == "type2_finalize":
        current = _read_json(state)
        if current.get("phase") != "MIGRATED_PENDING_VALIDATION" or current.get("plan_sha256") != plan["plan_sha256"]:
            raise RequestRejected("TYPE2 finalize requires matching migrated state")
        validation = root / service.VALIDATION_ROOT_REL / f"{clearup_id}.json"
        proof = _read_json(validation)
        if str(proof.get("status") or "").upper() != "GREEN" or proof.get("plan_sha256") != plan["plan_sha256"]:
            raise RequestRejected("TYPE2 finalize validation proof mismatch")
        proof_checks={str(x.get("source") or ""):x for x in (proof.get("checks") or []) if isinstance(x,dict)}
        for item in manifest["items"]:
            check=proof_checks.get(item["source"])
            if not isinstance(check,dict):
                raise RequestRejected(f"TYPE2 validation source proof missing: {item['source']}")
            source_now=_tree_rows(root/item["source"],root)
            source_hash=hashlib.sha256(json.dumps(source_now,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")).hexdigest()
            # The old location must remain quiescent after validation.  The
            # destination is intentionally allowed to keep changing because it
            # is now the active writer location.
            if source_hash != str(check.get("source_rows_sha256") or ""):
                raise RequestRejected(f"TYPE2 old source changed after validation: {item['source']}")
        for item in manifest["items"]:
            destination = root / item["destination"]
            if not destination.exists() or destination.is_symlink():
                raise RequestRejected(f"TYPE2 destination missing/unsafe: {item['destination']}")
            key=str(item.get("path_key") or "").strip()
            if key:
                marker=_read_json(_type2_activation_path(root,key))
                if marker.get("active") is not True or marker.get("destination") != item["destination"] or marker.get("plan_sha256") != plan["plan_sha256"]:
                    raise RequestRejected(f"TYPE2 path activation not proven: {key}")
        clearup_root = root / "CLEARUP"
        clearup_root.mkdir(parents=True, exist_ok=True)
        if clearup_root.is_symlink() or clearup_root.stat().st_dev != root.stat().st_dev:
            raise RequestRejected("TYPE2 CLEARUP root unsafe")
        run_root = clearup_root / f"{clearup_id}-finalize-{request_id}"
        original = run_root / "original"
        original.mkdir(parents=True, exist_ok=False)
        moved = []
        try:
            for item in manifest["items"]:
                source = root / item["source"]; dest = original / item["source"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                source.rename(dest); moved.append((source, dest))
                if os.path.lexists(source) or not os.path.lexists(dest):
                    raise RuntimeError(f"TYPE2 finalize hard-move failed: {item['source']}")
        except Exception:
            for source, dest in reversed(moved):
                try:
                    if not os.path.lexists(source) and os.path.lexists(dest):
                        source.parent.mkdir(parents=True, exist_ok=True); dest.rename(source)
                except OSError: pass
            raise
        try:
            shutil.rmtree(run_root)
        except Exception as exc:
            raise RuntimeError(f"TYPE2 finalize delete failed; quarantine preserved: {run_root}: {exc}") from exc
        if any(os.path.lexists(root / item["source"]) for item in manifest["items"]):
            raise RuntimeError("TYPE2 finalize source readback failed")
        after = service._snapshot_release_dirs(root)
        if after != request["mailbox_snapshot_before"]:
            raise RuntimeError("TYPE2 release mailboxes changed during finalize")
        result = {
            "status": "GREEN", "clearup_id": clearup_id, "phase": "COMPLETE",
            "removed_sources": [x["source"] for x in manifest["items"]],
            "destinations_retained": [x["destination"] for x in manifest["items"]],
            "delete_performed": True,
        }
        _atomic_write_json(state, {**result, "plan_sha256": plan["plan_sha256"]})
        return request_id, result

    # type2_restore: non-destructively recreate original source from recovery staging; destination is retained.
    restored = []
    for item in manifest["items"]:
        source = root / item["source"]
        staged = stage / "original" / item["source"]
        if source.exists():
            if _tree_rows(source, root) != item["source_rows"]:
                raise RequestRejected(f"TYPE2 existing source differs; restore refused: {item['source']}")
            continue
        _copy_exact(staged, source)
        if _tree_rows(source, root) != item["source_rows"]:
            raise RuntimeError(f"TYPE2 restore verification failed: {item['source']}")
        restored.append(item["source"])
    for item in manifest["items"]:
        key=str(item.get("path_key") or "").strip()
        if key:
            _set_type2_activation(root,key=key,source=item["source"],destination=item["destination"],active=False,clearup_id=clearup_id,plan_sha256=plan["plan_sha256"])
    after = service._snapshot_release_dirs(root)
    if after != request["mailbox_snapshot_before"]:
        raise RuntimeError("TYPE2 release mailboxes changed during restore")
    result = {"status": "GREEN", "clearup_id": clearup_id, "phase": "RESTORED", "restored_sources": restored, "destinations_untouched": True, "delete_performed": False}
    _atomic_write_json(state, {**result, "plan_sha256": plan["plan_sha256"]})
    return request_id, result


def _load_clearup_type2_service(root: Path):
    module_root = root / "App/slimmemeterportal_import/rootfs/app/projectmanager_v2"
    if not module_root.is_dir():
        raise RequestRejected("projectmanager module-root ontbreekt")
    sys.path.insert(0, str(module_root))
    try:
        import clearup_type2_service  # type: ignore
    finally:
        try: sys.path.remove(str(module_root))
        except ValueError: pass
    return clearup_type2_service

def execute_type1_delete(root: Path, request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    root = root.resolve()
    if str(request.get("schema") or "") != TYPE1_DELETE_SCHEMA:
        raise RequestRejected("TYPE1 delete schema ongeldig")
    request_id = str(request.get("request_id") or "").strip().lower()
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise RequestRejected("TYPE1 delete request_id ongeldig")
    if str(request.get("operation") or "") != "clearup_001_delete":
        raise RequestRejected("TYPE1 delete operation ongeldig")
    if str(request.get("clearup_id") or "") != TYPE1_CLEARUP_ID:
        raise RequestRejected("TYPE1 clearup_id ongeldig")
    if tuple(request.get("roots") or ()) != TYPE1_ROOTS:
        raise RequestRejected("TYPE1 roots wijken af van allowlist")
    release_version = str(request.get("release_version") or "").strip()
    try:
        release_tuple=tuple(int(part) for part in release_version.split('.'))
    except ValueError as exc:
        raise RequestRejected("TYPE1 releaseversie ongeldig") from exc
    if release_tuple < (32,5,7):
        raise RequestRejected("TYPE1 delete vereist release 32.5.7+")
    try:
        current_version = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RequestRejected(f"actieve release onleesbaar: {exc}") from exc
    if current_version != release_version:
        raise RequestRejected("TYPE1 actieve release mismatch")
    expires_at = _parse_utc(request.get("expires_at"), "expires_at")
    if expires_at <= datetime.now(timezone.utc):
        raise RequestRejected("TYPE1 delete request verlopen")
    controller = _load_state_json(project_system_path(root, 'Inbox/release_controller/current.json'), "release controller")
    if str(controller.get("status") or "").upper() != "COMPLETE" or str(controller.get("phase") or "").upper() != "COMPLETE":
        raise RequestRejected("TYPE1 delete vereist COMPLETE release controller")
    processing = root / "Inbox/processing"
    if processing.is_dir() and any(p.is_file() and p.name.startswith("EnergieProject_v") and p.suffix == ".zip" for p in processing.iterdir()):
        raise RequestRejected("TYPE1 delete weigert actieve processing release")

    service = _load_clearup_chat_service(root)
    service._dependency_guard(root)
    live_rows = service._collect(root)
    staged_rows = service._staging_rows(root)
    expected_rows = request.get("expected_rows")
    if not isinstance(expected_rows, list) or expected_rows != live_rows or staged_rows != live_rows:
        raise RequestRejected("TYPE1 recovery/live hashrevalidatie mismatch")

    clearup_root = root / "CLEARUP"
    clearup_root.mkdir(parents=True, exist_ok=True)
    if clearup_root.is_symlink() or not clearup_root.is_dir():
        raise RequestRejected("TYPE1 CLEARUP-root ongeldig")
    if clearup_root.stat().st_dev != root.stat().st_dev:
        raise RequestRejected("TYPE1 CLEARUP-root cross-filesystem")
    run_root = clearup_root / f"ClearUp_001-delete-{request_id}"
    original_root = run_root / "original"
    if run_root.exists() or run_root.is_symlink():
        raise RequestRejected("TYPE1 delete run bestaat al")
    original_root.mkdir(parents=True)
    moved = []
    try:
        for rel in TYPE1_ROOTS:
            source = root / rel
            if not source.exists() or source.is_symlink():
                raise RuntimeError(f"TYPE1 bron ontbreekt/unsafe: {rel}")
            if source.stat().st_dev != root.stat().st_dev:
                raise RuntimeError(f"TYPE1 cross-filesystem bron: {rel}")
            dest = original_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() or dest.is_symlink():
                raise RuntimeError(f"TYPE1 quarantainebestemming bestaat: {rel}")
            source.rename(dest)
            moved.append((source, dest))
            if os.path.lexists(source) or not os.path.lexists(dest):
                raise RuntimeError(f"TYPE1 hard-move readback mislukt: {rel}")
    except Exception:
        for source, dest in reversed(moved):
            try:
                if not os.path.lexists(source) and os.path.lexists(dest):
                    source.parent.mkdir(parents=True, exist_ok=True)
                    dest.rename(source)
            except OSError:
                pass
        raise

    # All four roots are now outside Inbox in one reversible transaction.
    # Permanent deletion happens only after the complete hard-move succeeded.
    try:
        shutil.rmtree(run_root)
    except Exception as exc:
        raise RuntimeError(f"TYPE1 permanent delete failed; quarantine preserved at {run_root}: {exc}") from exc
    if run_root.exists() or run_root.is_symlink():
        raise RuntimeError("TYPE1 delete readback failed: quarantine still exists")
    remaining = [rel for rel in TYPE1_ROOTS if os.path.lexists(root / rel)]
    if remaining:
        raise RuntimeError(f"TYPE1 delete readback failed: {remaining}")
    return request_id, {
        "status": "GREEN",
        "clearup_id": TYPE1_CLEARUP_ID,
        "removed": list(TYPE1_ROOTS),
        "removed_count": len(TYPE1_ROOTS),
        "delete_performed": True,
        "recovery_reverified": True,
        "live_tree_reverified": True,
        "privileged_watcher_executor": True,
    }


def execute_request(root: Path, request_path: Path) -> tuple[str, dict[str, Any]]:
    root = root.resolve()
    if request_path.is_symlink() or not request_path.is_file():
        raise RequestRejected("requestpad ontbreekt, is geen regulier bestand of is een symlink")
    request = _read_json(request_path)
    request_id, operation, release_version, remaining, pre_acceptance = _validate_common(root, request)
    clearup = _load_project_clearup(root)

    if operation == "apply":
        plan = request.get("plan")
        if not isinstance(plan, dict):
            raise RequestRejected("CLEARUP apply-plan ontbreekt")
        if str(plan.get("current_version") or "") != release_version:
            raise RequestRejected("CLEARUP plan hoort niet bij de actieve release")
        if plan.get("delete_capability") is not False:
            raise RequestRejected("CLEARUP plan delete_capability moet exact false zijn")
        if pre_acceptance:
            atomic_now = _load_state_json(project_system_path(root, 'Inbox/atomic_app_swap_state.json'), "atomic release state")
            protected_rollback = f"App.__rollback_{str(atomic_now.get('from_version') or '').strip()}"
            items = plan.get("items")
            if not isinstance(items, list):
                raise RequestRejected("pre-acceptance CLEARUP plan items ontbreken/ongeldig")
            for item in items:
                if not isinstance(item, dict):
                    raise RequestRejected("pre-acceptance CLEARUP plan item ongeldig")
                if str(item.get("source_path") or "").rstrip("/") == protected_rollback:
                    raise RequestRejected("pre-acceptance CLEARUP mag actieve rollback niet verplaatsen")
            expected_fingerprint = str(plan.get("prerequisite_fingerprint") or "").strip().lower()
            if len(expected_fingerprint) != 64 or any(ch not in "0123456789abcdef" for ch in expected_fingerprint):
                raise RequestRejected("pre-acceptance CLEARUP mist geldige recovery prerequisite_fingerprint")
            module_root = root / "App/slimmemeterportal_import/rootfs/app"
            sys.path.insert(0, str(module_root))
            try:
                import project_clearup_auto  # type: ignore
                current = project_clearup_auto._current_release_cr_gate(root, app_version=release_version)
            finally:
                try:
                    sys.path.remove(str(module_root))
                except ValueError:
                    pass
            if current.get("ok") is not True or str(current.get("fingerprint") or "").lower() != expected_fingerprint:
                raise RequestRejected("pre-acceptance CLEARUP recovery fingerprint is niet meer actueel")
        confirmation = str(request.get("confirmation") or "")
        if confirmation != str(plan.get("confirmation_required") or ""):
            raise RequestRejected("CLEARUP plan confirmation mismatch")
        run_id = str(request.get("run_id") or "").strip()
        if not RUN_ID_RE.fullmatch(run_id):
            raise RequestRejected("CLEARUP run_id ongeldig")
        result = clearup.apply_clearup_plan(
            root,
            plan,
            confirmation=confirmation,
            run_id=run_id,
            deadline_monotonic=time.monotonic() + remaining,
        )
    else:
        run_id = str(request.get("restore_run_id") or "").strip()
        if not RUN_ID_RE.fullmatch(run_id):
            raise RequestRejected("CLEARUP restore_run_id ongeldig")
        confirmation = str(request.get("confirmation") or "")
        if confirmation != f"RESTORE CLEARUP {run_id}":
            raise RequestRejected("CLEARUP restore confirmation mismatch")
        result = clearup.restore_clearup_run(root, run_id, confirmation=confirmation)

    if not isinstance(result, dict):
        raise RuntimeError("CLEARUP executor resultaat is geen object")
    if result.get("delete_performed") not in (None, False):
        raise RuntimeError("CLEARUP executor rapporteert onverwachte delete")
    return request_id, result


def process(root: Path, request_path: Path, result_path: Path) -> tuple[int, dict[str, Any]]:
    request_id = ""
    try:
        raw = _read_json(request_path)
        request_id = str(raw.get("request_id") or "").strip().lower()
        if str(raw.get("schema") or "") == TYPE1_DELETE_SCHEMA:
            request_id, result = execute_type1_delete(root, raw)
            payload = {
                "schema": TYPE1_DELETE_RESULT_SCHEMA,
                "request_id": request_id,
                "status": "completed",
                "result": result,
                "delete_performed": True,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        elif str(raw.get("schema") or "") == TYPE2_SCHEMA:
            request_id, result = execute_type2(root, raw)
            payload = {
                "schema": TYPE2_RESULT_SCHEMA,
                "request_id": request_id,
                "status": "completed",
                "result": result,
                "delete_performed": bool(result.get("delete_performed") is True),
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        else:
            request_id, result = execute_request(root, request_path)
            payload = {
                "schema": RESULT_SCHEMA,
                "request_id": request_id,
                "status": "completed",
                "result": result,
                "delete_performed": False,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
        code = 0
    except RequestRejected as exc:
        payload = {
            "schema": (TYPE1_DELETE_RESULT_SCHEMA if str(locals().get("raw", {}).get("schema") or "") == TYPE1_DELETE_SCHEMA else TYPE2_RESULT_SCHEMA if str(locals().get("raw", {}).get("schema") or "") == TYPE2_SCHEMA else RESULT_SCHEMA),
            "request_id": request_id,
            "status": "rejected",
            "error": f"{type(exc).__name__}: {exc}",
            "delete_performed": False,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        code = 2
    except Exception as exc:
        payload = {
            "schema": (TYPE1_DELETE_RESULT_SCHEMA if str(locals().get("raw", {}).get("schema") or "") == TYPE1_DELETE_SCHEMA else TYPE2_RESULT_SCHEMA if str(locals().get("raw", {}).get("schema") or "") == TYPE2_SCHEMA else RESULT_SCHEMA),
            "request_id": request_id,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "delete_performed": False,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        code = 1
    _atomic_write_json(result_path, payload)
    return code, payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a release-bound EnergieProject CLEARUP move request")
    parser.add_argument("--root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    code, payload = process(Path(args.root), Path(args.request), Path(args.result))
    print(json.dumps(payload, ensure_ascii=False), file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
