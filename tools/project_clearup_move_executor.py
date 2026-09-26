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
    if operation not in {"type2_prepare", "type2_refresh_recovery", "type2_migrate", "type2_validation_commit", "type2_external_recovery_confirm", "type2_finalize", "type2_restore"}:
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
    if operation in {"type2_migrate", "type2_external_recovery_confirm", "type2_finalize", "type2_restore"} and request.get("explicit_user_approval") is not True:
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


def _verify_type2_zip_payload(path: Path, manifest: dict[str, Any]) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("TYPE2 recovery ZIP missing/unsafe")
    with zipfile.ZipFile(path) as z:
        bad = z.testzip()
        if bad:
            raise RuntimeError(f"TYPE2 recovery ZIP corrupt: {bad}")
        zipped_manifest = json.loads(z.read("TYPE2_MANIFEST.json"))
        if zipped_manifest != manifest:
            raise RuntimeError("TYPE2 recovery ZIP manifest mismatch")
        names = set(z.namelist())
        for item in manifest.get("items") or []:
            rows = item.get("source_rows") if isinstance(item, dict) else None
            if not isinstance(rows, list):
                raise RuntimeError("TYPE2 recovery manifest source_rows missing")
            for row in rows:
                if not isinstance(row, dict) or row.get("type") != "file":
                    continue
                member = "original/" + str(row.get("path") or "")
                if member not in names:
                    raise RuntimeError(f"TYPE2 recovery ZIP payload missing: {member}")
                data = z.read(member)
                if len(data) != int(row.get("size") if row.get("size") is not None else -1):
                    raise RuntimeError(f"TYPE2 recovery ZIP payload size mismatch: {member}")
                if hashlib.sha256(data).hexdigest() != str(row.get("sha256") or ""):
                    raise RuntimeError(f"TYPE2 recovery ZIP payload hash mismatch: {member}")


def _build_type2_recovery_snapshot(root: Path, *, stage: Path, export: Path, clearup_id: str, plan: dict[str, Any], expected_rows: dict[str, list[dict[str, Any]]] | None = None, manifest_extra: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if stage.exists() or stage.is_symlink():
        raise RequestRejected("TYPE2 recovery build staging already exists/unsafe")
    stage.mkdir(parents=True, exist_ok=False)
    items = []
    try:
        for item in plan["items"]:
            source_rel = item["source"]
            source = root / source_rel
            if not source.exists():
                if item.get("optional") is True:
                    continue
                raise RequestRejected(f"TYPE2 source missing/unsafe: {source_rel}")
            if source.is_symlink():
                raise RequestRejected(f"TYPE2 source missing/unsafe: {source_rel}")
            before_rows = _tree_rows(source, root)
            if expected_rows is not None and before_rows != expected_rows.get(source_rel):
                raise RequestRejected(f"TYPE2 preserved source differs from migrated cutover: {source_rel}")
            staged = stage / "original" / source_rel
            _copy_exact(source, staged)
            after_rows = _tree_rows(source, root)
            staged_rows = _tree_rows(staged, stage / "original")
            if after_rows != before_rows:
                raise RequestRejected(f"TYPE2 source changed during recovery snapshot: {source_rel}")
            if staged_rows != before_rows:
                raise RuntimeError(f"TYPE2 staged recovery mismatch: {source_rel}")
            items.append({
                "source": source_rel, "destination": item["destination"], "source_rows": before_rows,
                "reason": item.get("reason", ""), "path_key": item.get("path_key", ""),
            })
        manifest = {
            "schema": "energie_clearup_type2_recovery_v1", "classification": "TYPE2",
            "clearup_id": clearup_id, "plan_sha256": plan["plan_sha256"],
            "created_at": datetime.now(timezone.utc).isoformat(), "items": items,
            "deletion_performed": False,
        }
        if manifest_extra:
            reserved = {"schema", "classification", "clearup_id", "plan_sha256", "created_at", "items", "deletion_performed"}
            if reserved.intersection(manifest_extra):
                raise RequestRejected("TYPE2 recovery manifest_extra may not override reserved fields")
            manifest.update(manifest_extra)
        _atomic_write_json(stage / "TYPE2_MANIFEST.json", manifest)
        export.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(export, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(stage.rglob("*")):
                if p.is_symlink():
                    raise RequestRejected("TYPE2 staging symlink refused")
                arc = p.relative_to(stage).as_posix()
                if p.is_dir():
                    z.writestr(arc.rstrip("/") + "/", b"")
                else:
                    z.write(p, arc)
        _verify_type2_zip_payload(export, manifest)
        return manifest, {
            "artifact": export.name, "artifact_size": export.stat().st_size,
            "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
            "item_count": len(items), "deletion_performed": False,
        }
    except Exception:
        if stage.exists() and not stage.is_symlink():
            shutil.rmtree(stage, ignore_errors=True)
        export.unlink(missing_ok=True)
        raise



def _read_exact_file_candidate(path: Path, *, expected_size: int, expected_sha256: str) -> bytes | None:
    """Return bytes only when one regular file exactly matches the cutover identity."""
    if path.is_symlink() or not path.is_file():
        return None
    try:
        if path.stat().st_size != expected_size:
            return None
        h = hashlib.sha256()
        chunks = []
        with path.open("rb") as handle:
            while True:
                block = handle.read(1024 * 1024)
                if not block:
                    break
                h.update(block)
                chunks.append(block)
        if h.hexdigest() != expected_sha256:
            return None
        return b"".join(chunks)
    except OSError:
        return None


def _read_exact_zip_candidate(z: zipfile.ZipFile | None, member: str, *, expected_size: int, expected_sha256: str) -> bytes | None:
    """Return archived bytes only when the existing recovery ZIP contains an exact cutover payload."""
    if z is None:
        return None
    try:
        info = z.getinfo(member)
        if info.file_size != expected_size:
            return None
        data = z.read(member)
    except (KeyError, OSError, RuntimeError, zipfile.BadZipFile):
        return None
    if len(data) != expected_size or hashlib.sha256(data).hexdigest() != expected_sha256:
        return None
    return data


def _destination_path_for_row(root: Path, *, source_rel: str, destination_rel: str, row_path: str) -> Path:
    source_path = Path(source_rel)
    row = Path(row_path)
    suffix = row.relative_to(source_path)
    return root / destination_rel / suffix


def _build_type2_recovery_from_cutover(
    root: Path,
    *,
    stage: Path,
    export: Path,
    existing_export: Path,
    clearup_id: str,
    plan: dict[str, Any],
    cutover_rows: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Reconstruct an exact historical cutover snapshot without mutating live source/destination.

    Byte precedence is deliberately conservative:
    1. the existing recovery ZIP, but only for members already matching cutover size+SHA;
    2. the preserved source, only when the current file still matches cutover size+SHA;
    3. the migrated destination, only when its current file still matches cutover size+SHA;
    4. synthesize b'' only for the cryptographically proven empty-file identity.

    Any other missing historical payload fails closed.
    """
    if stage.exists() or stage.is_symlink():
        raise RequestRejected("TYPE2 recovery rebuild staging already exists/unsafe")
    if export.exists() or export.is_symlink():
        raise RequestRejected("TYPE2 recovery rebuild export already exists/unsafe")

    old_zip = None
    if existing_export.is_file() and not existing_export.is_symlink():
        try:
            old_zip = zipfile.ZipFile(existing_export, "r")
        except zipfile.BadZipFile:
            old_zip = None

    stage.mkdir(parents=True, exist_ok=False)
    items: list[dict[str, Any]] = []
    provenance: dict[str, str] = {}
    empty_sha = hashlib.sha256(b"").hexdigest()
    try:
        for item in plan["items"]:
            source_rel = item["source"]
            destination_rel = item["destination"]
            rows = cutover_rows.get(source_rel)
            if not isinstance(rows, list) or not rows:
                raise RequestRejected(f"TYPE2 recovery refresh missing cutover rows: {source_rel}")

            staged_root = stage / "original"
            for row in rows:
                if not isinstance(row, dict):
                    raise RequestRejected(f"TYPE2 cutover row invalid: {source_rel}")
                row_path = str(row.get("path") or "")
                row_type = str(row.get("type") or "")
                if not row_path or not (row_path == source_rel or row_path.startswith(source_rel.rstrip("/") + "/")):
                    raise RequestRejected(f"TYPE2 cutover row path outside source: {row_path}")
                staged_path = staged_root / row_path
                if row_type == "directory":
                    staged_path.mkdir(parents=True, exist_ok=True)
                    continue
                if row_type != "file":
                    raise RequestRejected(f"TYPE2 cutover row type invalid: {row_path}")

                expected_size = int(row.get("size") if row.get("size") is not None else -1)
                expected_sha = str(row.get("sha256") or "")
                if expected_size < 0 or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
                    raise RequestRejected(f"TYPE2 cutover file identity invalid: {row_path}")

                member = "original/" + row_path
                data = _read_exact_zip_candidate(
                    old_zip, member, expected_size=expected_size, expected_sha256=expected_sha
                )
                source_kind = "existing_recovery_zip"
                if data is None:
                    data = _read_exact_file_candidate(
                        root / row_path, expected_size=expected_size, expected_sha256=expected_sha
                    )
                    source_kind = "preserved_source"
                if data is None:
                    destination_path = _destination_path_for_row(
                        root, source_rel=source_rel, destination_rel=destination_rel, row_path=row_path
                    )
                    data = _read_exact_file_candidate(
                        destination_path, expected_size=expected_size, expected_sha256=expected_sha
                    )
                    source_kind = "migrated_destination"
                if data is None and expected_size == 0 and expected_sha == empty_sha:
                    data = b""
                    source_kind = "proven_empty_identity"
                if data is None:
                    raise RequestRejected(f"TYPE2 cutover payload unavailable: {row_path}")

                staged_path.parent.mkdir(parents=True, exist_ok=True)
                staged_path.write_bytes(data)
                provenance[row_path] = source_kind

            staged_rows = _tree_rows(stage / "original" / source_rel, stage / "original")
            if staged_rows != rows:
                raise RuntimeError(f"TYPE2 reconstructed cutover mismatch: {source_rel}")
            items.append({
                "source": source_rel,
                "destination": destination_rel,
                "source_rows": rows,
                "reason": item.get("reason", ""),
                "path_key": item.get("path_key", ""),
            })

        manifest = {
            "schema": "energie_clearup_type2_recovery_v1",
            "classification": "TYPE2",
            "clearup_id": clearup_id,
            "plan_sha256": plan["plan_sha256"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "items": items,
            "deletion_performed": False,
            "reconstructed_from_cutover_evidence": True,
        }
        _atomic_write_json(stage / "TYPE2_MANIFEST.json", manifest)
        export.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(export, "w", zipfile.ZIP_DEFLATED) as z:
            for q in sorted(stage.rglob("*")):
                if q.is_symlink():
                    raise RequestRejected("TYPE2 staging symlink refused")
                arc = q.relative_to(stage).as_posix()
                if q.is_dir():
                    z.writestr(arc.rstrip("/") + "/", b"")
                else:
                    z.write(q, arc)
        _verify_type2_zip_payload(export, manifest)
        counts = {}
        for source_kind in provenance.values():
            counts[source_kind] = counts.get(source_kind, 0) + 1
        return manifest, {
            "artifact": export.name,
            "artifact_size": export.stat().st_size,
            "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
            "item_count": len(items),
            "deletion_performed": False,
            "reconstruction_sources": counts,
        }
    except Exception:
        if stage.exists() and not stage.is_symlink():
            shutil.rmtree(stage, ignore_errors=True)
        export.unlink(missing_ok=True)
        raise
    finally:
        if old_zip is not None:
            old_zip.close()


def _rows_fingerprint(rows: list[dict[str, Any]]) -> str:
    raw = json.dumps(rows, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _build_type2_recovery_from_quiescent_preserved_source(
    root: Path,
    *,
    stage: Path,
    export: Path,
    clearup_id: str,
    plan: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Last-resort non-destructive recovery for already migrated legacy batches.

    Historical 32.5.15 migrations can lose an exact cutover payload when both the
    preserved source and active destination drift after activation.  In that case
    the safe object to protect before deletion is the *current preserved source*.
    This fallback is allowed only with a matching GREEN validation envelope and
    only after the privileged watcher proves every old source tree quiescent over
    a double snapshot.  The normal post-refresh validation/finalize path still has
    to run afterwards, so this never weakens the destructive gate.
    """
    if validation.get("schema") != "energie_clearup_type2_validation_v2" or validation.get("status") != "GREEN":
        raise RequestRejected("TYPE2 preserved-source recovery requires GREEN validation envelope")
    if validation.get("plan_sha256") != plan.get("plan_sha256") or list(validation.get("failures") or []):
        raise RequestRejected("TYPE2 preserved-source recovery validation mismatch")

    quiet = max(0.05, float(validation.get("old_source_quiescence_seconds") or 2.0))
    expected_rows: dict[str, list[dict[str, Any]]] = {}
    source_fingerprints: dict[str, str] = {}
    for item in plan["items"]:
        source_rel = item["source"]
        source = root / source_rel
        if not source.exists() or source.is_symlink():
            raise RequestRejected(f"TYPE2 preserved source missing/unsafe: {source_rel}")
        before = _tree_rows(source, root)
        time.sleep(quiet)
        after = _tree_rows(source, root)
        if before != after:
            raise RequestRejected(f"TYPE2 old source still mutating during recovery fallback: {source_rel}")
        expected_rows[source_rel] = after
        source_fingerprints[source_rel] = _rows_fingerprint(after)

    manifest, artifact = _build_type2_recovery_snapshot(
        root,
        stage=stage,
        export=export,
        clearup_id=clearup_id,
        plan=plan,
        expected_rows=expected_rows,
        manifest_extra={
            "recovery_basis": "quiescent_preserved_source",
            "legacy_cutover_reconstruction_unavailable": True,
            "source_rows_sha256": source_fingerprints,
        },
    )
    artifact = dict(artifact)
    artifact["recovery_basis"] = "quiescent_preserved_source"
    artifact["reconstruction_sources"] = {"quiescent_preserved_source": sum(1 for item in manifest.get("items") or [] for row in item.get("source_rows") or [] if row.get("type") == "file")}
    return manifest, artifact


def _invalidate_external_confirmation_if_artifact_changes(
    root: Path, service, *, clearup_id: str, new_export: Path, reason: str
) -> None:
    gate_path = root / service.EXTERNAL_GATE_REL
    if gate_path.is_symlink() or not gate_path.is_file():
        return
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise RequestRejected("TYPE2 external recovery gate unreadable/unsafe")
    if not isinstance(gate, dict):
        raise RequestRejected("TYPE2 external recovery gate invalid")
    if gate.get("status") != "EXTERNAL_COPY_CONFIRMED" or gate.get("delete_allowed") is not True:
        return
    if new_export.is_symlink() or not new_export.is_file():
        raise RequestRejected("TYPE2 replacement recovery artifact missing/unsafe")
    confirmed = {
        str(row.get("clearup_id") or ""): row
        for row in (gate.get("confirmed_exports") or []) if isinstance(row, dict)
    }
    prior = confirmed.get(clearup_id)
    new_sha = hashlib.sha256(new_export.read_bytes()).hexdigest()
    new_size = new_export.stat().st_size
    if isinstance(prior, dict) and prior.get("sha256") == new_sha and prior.get("size") == new_size:
        return
    previous = {
        "confirmed_at": gate.get("confirmed_at"),
        "confirmed_exports": gate.get("confirmed_exports"),
        "confirmation_request_id": gate.get("confirmation_request_id"),
    }
    updated = dict(gate)
    updated.update({
        "status": "BLOCK_DELETE_UNTIL_EXTERNAL_COPY_CONFIRMED",
        "delete_allowed": False,
        "invalidated_at": datetime.now(timezone.utc).isoformat(),
        "invalidated_by_clearup_id": clearup_id,
        "invalidated_reason": reason,
        "previous_confirmation": previous,
    })
    _atomic_write_json(gate_path, updated)


def execute_type2(root: Path, request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    root = root.resolve()
    request_id, operation, clearup_id, plan, service = _type2_validate_request(root, request)
    stage = root / service.STAGING_ROOT_REL / clearup_id
    export = root / service.EXPORT_ROOT_REL / f"{clearup_id}_Type2_recovery.zip"
    state = root / service.STATE_ROOT_REL / f"{clearup_id}.json"

    if operation == "type2_prepare":
        for item in plan["items"]:
            destination = root / item["destination"]
            if destination.exists() or destination.is_symlink():
                raise RequestRejected(f"TYPE2 destination must be absent at prepare: {item['destination']}")
        if stage.exists() or stage.is_symlink():
            if stage.is_symlink():
                raise RequestRejected("TYPE2 staging symlink refused")
            shutil.rmtree(stage)
        tmp_export = export.with_name(f".{export.name}.tmp-{os.getpid()}-{request_id}")
        manifest, artifact = _build_type2_recovery_snapshot(
            root, stage=stage, export=tmp_export, clearup_id=clearup_id, plan=plan,
        )
        _invalidate_external_confirmation_if_artifact_changes(
            root, service, clearup_id=clearup_id, new_export=tmp_export, reason="type2_prepare_rebuilt_recovery"
        )
        os.replace(tmp_export, export)
        _verify_type2_zip_payload(export, manifest)
        result = {"status": "GREEN", "clearup_id": clearup_id, "phase": "PREPARED", **artifact}
        result["artifact"] = export.name
        result["artifact_size"] = export.stat().st_size
        result["artifact_sha256"] = hashlib.sha256(export.read_bytes()).hexdigest()
        _atomic_write_json(state, {**result, "plan_sha256": plan["plan_sha256"]})
        return request_id, result

    if operation == "type2_refresh_recovery":
        state_data = _load_state_json(state, "TYPE2 state")

        # PREPARED exports are allowed to be refreshed non-destructively.  This
        # is required for volatile Inbox artefacts (for example operation locks)
        # that may legitimately change after the original prepare.  The source
        # remains authoritative until migration, so rebuild directly from it and
        # atomically replace only staging/export evidence.
        if state_data.get("phase") == "PREPARED":
            if (
                state_data.get("status") != "GREEN"
                or state_data.get("plan_sha256") != plan["plan_sha256"]
                or state_data.get("deletion_performed") is not False
            ):
                raise RequestRejected("TYPE2 prepared recovery refresh requires matching GREEN pre-migrate state")
            for item in plan["items"]:
                destination = root / item["destination"]
                if destination.exists() or destination.is_symlink():
                    raise RequestRejected(f"TYPE2 prepared refresh requires absent destination: {item['destination']}")

            temp_stage = stage.with_name(f".{clearup_id}.prepared-refresh-{request_id}")
            temp_export = export.with_name(f".{export.name}.prepared-refresh-{request_id}")
            old_stage = stage.with_name(f".{clearup_id}.pre-prepared-refresh-{request_id}")
            old_export = export.with_name(f".{export.name}.pre-prepared-refresh-{request_id}")
            for path in (temp_stage, temp_export, old_stage, old_export):
                if path.exists() or path.is_symlink():
                    raise RequestRejected(f"TYPE2 prepared refresh temporary path exists/unsafe: {path.name}")

            manifest, artifact = _build_type2_recovery_snapshot(
                root, stage=temp_stage, export=temp_export, clearup_id=clearup_id, plan=plan,
            )
            _invalidate_external_confirmation_if_artifact_changes(
                root, service, clearup_id=clearup_id, new_export=temp_export, reason="prepared_recovery_refreshed"
            )
            stage_backed_up = export_backed_up = stage_installed = export_installed = False
            try:
                if stage.exists():
                    if stage.is_symlink():
                        raise RequestRejected("TYPE2 staging symlink refused")
                    stage.rename(old_stage); stage_backed_up = True
                if export.exists():
                    if export.is_symlink():
                        raise RequestRejected("TYPE2 export symlink refused")
                    export.rename(old_export); export_backed_up = True
                temp_stage.rename(stage); stage_installed = True
                temp_export.rename(export); export_installed = True
                _verify_type2_zip_payload(export, manifest)
                after = service._snapshot_release_dirs(root)
                if after != request["mailbox_snapshot_before"]:
                    raise RuntimeError("TYPE2 release mailboxes changed during prepared recovery refresh")
                if old_stage.exists():
                    shutil.rmtree(old_stage)
                old_export.unlink(missing_ok=True)
            except Exception:
                if export_installed:
                    export.unlink(missing_ok=True)
                if stage_installed and stage.exists() and not stage.is_symlink():
                    shutil.rmtree(stage, ignore_errors=True)
                if export_backed_up and old_export.exists():
                    old_export.rename(export)
                if stage_backed_up and old_stage.exists():
                    old_stage.rename(stage)
                raise
            finally:
                if temp_stage.exists() and not temp_stage.is_symlink():
                    shutil.rmtree(temp_stage, ignore_errors=True)
                temp_export.unlink(missing_ok=True)

            state_after = dict(state_data)
            state_after.update({
                "artifact": export.name,
                "artifact_size": export.stat().st_size,
                "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
                "item_count": artifact["item_count"],
                "deletion_performed": False,
                "recovery_refresh": {
                    "status": "GREEN",
                    "mode": "prepared_resnapshot",
                    "at": datetime.now(timezone.utc).isoformat(),
                    "artifact": export.name,
                    "artifact_size": export.stat().st_size,
                    "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
                    "deletion_performed": False,
                },
            })
            _atomic_write_json(state, state_after)
            return request_id, {
                "status": "GREEN",
                "clearup_id": clearup_id,
                "phase": "PREPARED",
                "prepared_recovery_refresh": True,
                "artifact": export.name,
                "artifact_size": export.stat().st_size,
                "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
                "item_count": artifact["item_count"],
                "deletion_performed": False,
                "source_preserved": True,
                "destination_untouched": True,
            }

        validation_path = root / service.VALIDATION_ROOT_REL / f"{clearup_id}.json"
        validation = _load_state_json(validation_path, "TYPE2 validation")
        if (
            state_data.get("phase") != "MIGRATED_PENDING_VALIDATION"
            or state_data.get("status") != "GREEN"
            or state_data.get("plan_sha256") != plan["plan_sha256"]
            or state_data.get("source_preserved") is not True
            or state_data.get("deletion_performed") is not False
        ):
            raise RequestRejected("TYPE2 recovery refresh requires preserved migrated pre-delete state")
        if (
            validation.get("schema") != "energie_clearup_type2_validation_v2"
            or validation.get("status") != "GREEN"
            or validation.get("plan_sha256") != plan["plan_sha256"]
            or list(validation.get("failures") or [])
        ):
            raise RequestRejected("TYPE2 recovery refresh requires GREEN matching validation")
        cutover_rows = state_data.get("cutover_rows")
        if not isinstance(cutover_rows, dict) or not cutover_rows:
            raise RequestRejected("TYPE2 recovery refresh missing cutover evidence")
        try:
            active_release_tuple = tuple(int(part) for part in (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip().split("."))
        except (OSError, ValueError):
            active_release_tuple = ()
        for item in plan["items"]:
            source_rel = item["source"]
            destination = root / item["destination"]
            if not destination.exists() or destination.is_symlink():
                raise RequestRejected(f"TYPE2 migrated destination missing/unsafe: {item['destination']}")
            expected = cutover_rows.get(source_rel)
            if not isinstance(expected, list) or not expected:
                raise RequestRejected(f"TYPE2 recovery refresh missing cutover rows: {source_rel}")
            # 32.5.15 required the preserved source to remain byte-identical after cutover.
            # Keep that historical contract for old-release fixtures, while 32.5.16+ reconstructs
            # the immutable cutover snapshot from exact hash evidence when the old runtime drifts.
            if active_release_tuple and active_release_tuple < (32, 5, 16):
                if _tree_rows(root / source_rel, root) != expected:
                    raise RequestRejected(f"TYPE2 preserved source differs from migrated cutover: {source_rel}")
            key = str(item.get("path_key") or "").strip()
            if key:
                marker = _read_json(_type2_activation_path(root, key))
                if not (
                    marker.get("active") is True
                    and marker.get("clearup_id") == clearup_id
                    and marker.get("plan_sha256") == plan["plan_sha256"]
                    and marker.get("source") == source_rel
                    and marker.get("destination") == item["destination"]
                ):
                    raise RequestRejected(f"TYPE2 active path contract mismatch: {key}")

        temp_stage = stage.with_name(f".{clearup_id}.refresh-{request_id}")
        temp_export = export.with_name(f".{export.name}.refresh-{request_id}")
        old_stage = stage.with_name(f".{clearup_id}.pre-refresh-{request_id}")
        old_export = export.with_name(f".{export.name}.pre-refresh-{request_id}")
        for path in (temp_stage, temp_export, old_stage, old_export):
            if path.exists() or path.is_symlink():
                raise RequestRejected(f"TYPE2 recovery refresh temporary path exists/unsafe: {path.name}")
        try:
            manifest, artifact = _build_type2_recovery_from_cutover(
                root, stage=temp_stage, export=temp_export, existing_export=export,
                clearup_id=clearup_id, plan=plan, cutover_rows=cutover_rows,
            )
            recovery_basis = "cutover_evidence"
        except RequestRejected as exc:
            if not str(exc).startswith("TYPE2 cutover payload unavailable:"):
                raise
            # Legacy 32.5.15 already-migrated batches can no longer guarantee
            # every historical cutover byte. Preserve exactly what will be
            # deleted instead, but only after privileged quiescence proof.
            manifest, artifact = _build_type2_recovery_from_quiescent_preserved_source(
                root, stage=temp_stage, export=temp_export, clearup_id=clearup_id,
                plan=plan, validation=validation,
            )
            recovery_basis = "quiescent_preserved_source"
        _invalidate_external_confirmation_if_artifact_changes(
            root, service, clearup_id=clearup_id, new_export=temp_export, reason="migrated_recovery_refreshed"
        )
        stage_backed_up = export_backed_up = stage_installed = export_installed = False
        try:
            if stage.exists():
                if stage.is_symlink():
                    raise RequestRejected("TYPE2 staging symlink refused")
                stage.rename(old_stage); stage_backed_up = True
            if export.exists():
                if export.is_symlink():
                    raise RequestRejected("TYPE2 export symlink refused")
                export.rename(old_export); export_backed_up = True
            temp_stage.rename(stage); stage_installed = True
            temp_export.rename(export); export_installed = True
            _verify_type2_zip_payload(export, manifest)
            after = service._snapshot_release_dirs(root)
            if after != request["mailbox_snapshot_before"]:
                raise RuntimeError("TYPE2 release mailboxes changed during recovery refresh")
            if old_stage.exists():
                shutil.rmtree(old_stage)
            old_export.unlink(missing_ok=True)
        except Exception:
            if export_installed:
                export.unlink(missing_ok=True)
            if stage_installed and stage.exists() and not stage.is_symlink():
                shutil.rmtree(stage, ignore_errors=True)
            if export_backed_up and old_export.exists():
                old_export.rename(export)
            if stage_backed_up and old_stage.exists():
                old_stage.rename(stage)
            raise
        finally:
            if temp_stage.exists() and not temp_stage.is_symlink():
                shutil.rmtree(temp_stage, ignore_errors=True)
            temp_export.unlink(missing_ok=True)

        state_after = dict(state_data)
        state_after["recovery_refresh"] = {
            "status": "GREEN", "at": datetime.now(timezone.utc).isoformat(),
            "artifact": export.name, "artifact_size": export.stat().st_size,
            "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
            "deletion_performed": False,
            "reconstruction_sources": dict(artifact.get("reconstruction_sources") or {}),
            "recovery_basis": recovery_basis,
        }
        _atomic_write_json(state, state_after)
        return request_id, {
            "status": "GREEN", "clearup_id": clearup_id, "phase": "MIGRATED_PENDING_VALIDATION",
            "post_migrate_recovery_refresh": True, "artifact": export.name,
            "artifact_size": export.stat().st_size, "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
            "item_count": artifact["item_count"], "deletion_performed": False,
            "source_preserved": True, "destination_untouched": True,
            "reconstruction_sources": dict(artifact.get("reconstruction_sources") or {}),
            "recovery_basis": recovery_basis,
        }

    if operation == "type2_external_recovery_confirm":
        verified = service._verified_required_exports(root)
        required_exports = [f"{required_id}_Type2_recovery.zip" for required_id in service.TYPE2_REQUIRED_IDS]
        gate_path = root / service.EXTERNAL_GATE_REL
        existing = {}
        if gate_path.is_file() and not gate_path.is_symlink():
            try:
                loaded = json.loads(gate_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = loaded
            except (OSError, json.JSONDecodeError):
                raise RequestRejected("TYPE2 external recovery gate unreadable")
        gate = {
            **existing,
            "schema": "energie_clearup_type2_external_recovery_gate_v2",
            "status": "EXTERNAL_COPY_CONFIRMED",
            "delete_allowed": True,
            "required_exports": required_exports,
            "confirmed_exports": verified,
            "confirmed_at": datetime.now(timezone.utc).isoformat(),
            "confirmation_request_id": request_id,
            "confirmation_release_version": request.get("release_version"),
            "user_requirement": "No Type2 delete/finalize until external recovery ZIPs are received and explicitly confirmed.",
        }
        _atomic_write_json(gate_path, gate)
        readback = json.loads(gate_path.read_text(encoding="utf-8"))
        if readback != gate:
            raise RuntimeError("TYPE2 external recovery confirmation readback mismatch")
        after = service._snapshot_release_dirs(root)
        if after != request["mailbox_snapshot_before"]:
            raise RuntimeError("TYPE2 release mailboxes changed during external recovery confirmation")
        return request_id, {
            "status": "GREEN", "phase": "EXTERNAL_RECOVERY_CONFIRMED",
            "confirmed": True, "delete_allowed": True, "verified_count": len(verified),
            "confirmed_at": gate["confirmed_at"],
        }

    manifest = _type2_manifest(root, clearup_id, plan, service)

    if operation == "type2_migrate":
        # Migration is one transaction: create and verify destinations, freeze an
        # exact cutover recovery artifact, activate the new paths, then persist
        # migrated state.  If any pre-commit step fails, destinations, recovery
        # evidence and activation markers are rolled back to their prior state.
        created: list[Path] = []
        cutover_rows: dict[str, list[dict[str, Any]]] = {}
        activation_previous: dict[Path, bytes | None] = {}
        temp_stage = stage.with_name(f".{clearup_id}.migrate-cutover-{request_id}")
        temp_export = export.with_name(f".{export.name}.migrate-cutover-{request_id}")
        old_stage = stage.with_name(f".{clearup_id}.pre-migrate-{request_id}")
        old_export = export.with_name(f".{export.name}.pre-migrate-{request_id}")
        for path in (temp_stage, temp_export, old_stage, old_export):
            if path.exists() or path.is_symlink():
                raise RequestRejected(f"TYPE2 migrate temporary path exists/unsafe: {path.name}")

        stage_backed_up = export_backed_up = stage_installed = export_installed = False
        state_committed = False
        try:
            for item in manifest["items"]:
                source = root / item["source"]
                destination = root / item["destination"]
                if not source.exists() or source.is_symlink():
                    raise RequestRejected(f"TYPE2 live source missing/unsafe: {item['source']}")
                # Capture the exact source identity immediately before copy.
                # The destination must match that identity byte-for-byte before
                # it can ever become active.
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

            # Freeze the immutable cutover snapshot while every new destination
            # is still an exact copy and before any path activation can make it
            # writable.  This removes the historical race that broke 002 and
            # also prevents the same class of failure for 003..012.
            cutover_manifest, cutover_artifact = _build_type2_recovery_from_cutover(
                root,
                stage=temp_stage,
                export=temp_export,
                existing_export=export,
                clearup_id=clearup_id,
                plan=plan,
                cutover_rows=cutover_rows,
            )
            _invalidate_external_confirmation_if_artifact_changes(
                root, service, clearup_id=clearup_id, new_export=temp_export, reason="cutover_recovery_frozen"
            )

            if stage.exists():
                if stage.is_symlink():
                    raise RequestRejected("TYPE2 staging symlink refused")
                stage.rename(old_stage)
                stage_backed_up = True
            if export.exists():
                if export.is_symlink():
                    raise RequestRejected("TYPE2 export symlink refused")
                export.rename(old_export)
                export_backed_up = True
            temp_stage.rename(stage)
            stage_installed = True
            temp_export.rename(export)
            export_installed = True
            _verify_type2_zip_payload(export, cutover_manifest)

            activated_at_epoch = time.time()
            for item in cutover_manifest["items"]:
                key = str(item.get("path_key") or "").strip()
                if not key:
                    continue
                marker_path = _type2_activation_path(root, key)
                if marker_path.is_symlink():
                    raise RequestRejected(f"TYPE2 activation marker symlink refused: {key}")
                activation_previous[marker_path] = marker_path.read_bytes() if marker_path.is_file() else None
                _set_type2_activation(
                    root, key=key, source=item["source"], destination=item["destination"],
                    active=True, clearup_id=clearup_id, plan_sha256=plan["plan_sha256"],
                )

            after = service._snapshot_release_dirs(root)
            if after != request["mailbox_snapshot_before"]:
                raise RuntimeError("TYPE2 release mailboxes changed during migration")

            result = {
                "status": "GREEN",
                "clearup_id": clearup_id,
                "phase": "MIGRATED_PENDING_VALIDATION",
                "migrated": [{"source": x["source"], "destination": x["destination"]} for x in cutover_manifest["items"]],
                "source_preserved": True,
                "deletion_performed": False,
                "cutover_recovery_refreshed": True,
                "artifact": export.name,
                "artifact_size": export.stat().st_size,
                "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
            }
            _atomic_write_json(
                state,
                {
                    **result,
                    "plan_sha256": plan["plan_sha256"],
                    "activated_at_epoch": activated_at_epoch,
                    "cutover_rows": cutover_rows,
                    "recovery_refresh": {
                        "status": "GREEN",
                        "mode": "cutover_freeze_before_activation",
                        "at": datetime.now(timezone.utc).isoformat(),
                        "artifact": export.name,
                        "artifact_size": export.stat().st_size,
                        "artifact_sha256": hashlib.sha256(export.read_bytes()).hexdigest(),
                        "deletion_performed": False,
                        "reconstruction_sources": dict(cutover_artifact.get("reconstruction_sources") or {}),
                    },
                    "migration_fingerprint": hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest(),
                },
            )
            state_committed = True

            # Backups are transaction scaffolding only.  Once state is durable,
            # cleanup failure must not invalidate an otherwise committed migrate.
            if old_stage.exists() and not old_stage.is_symlink():
                shutil.rmtree(old_stage, ignore_errors=True)
            old_export.unlink(missing_ok=True)
            return request_id, result
        except Exception:
            if not state_committed:
                for marker_path, previous in reversed(list(activation_previous.items())):
                    try:
                        if previous is None:
                            marker_path.unlink(missing_ok=True)
                        else:
                            marker_payload = json.loads(previous.decode("utf-8"))
                            if not isinstance(marker_payload, dict):
                                raise ValueError("activation backup not object")
                            _atomic_write_json(marker_path, marker_payload)
                    except Exception:
                        pass
                if export_installed:
                    export.unlink(missing_ok=True)
                if stage_installed and stage.exists() and not stage.is_symlink():
                    shutil.rmtree(stage, ignore_errors=True)
                if export_backed_up and old_export.exists():
                    old_export.rename(export)
                if stage_backed_up and old_stage.exists():
                    old_stage.rename(stage)
                for destination in reversed(created):
                    try:
                        _remove_path(destination)
                    except Exception:
                        pass
            raise
        finally:
            if temp_stage.exists() and not temp_stage.is_symlink():
                shutil.rmtree(temp_stage, ignore_errors=True)
            temp_export.unlink(missing_ok=True)

    if operation == "type2_validation_commit":
        proof = request.get("validation_proof")
        if not isinstance(proof, dict):
            raise RequestRejected("TYPE2 validation proof ontbreekt")
        if proof.get("schema") != "energie_clearup_type2_validation_v2":
            raise RequestRejected("TYPE2 validation proof schema ongeldig")
        if proof.get("clearup_id") != clearup_id or proof.get("plan_sha256") != plan["plan_sha256"]:
            raise RequestRejected("TYPE2 validation proof identity mismatch")
        validation_status = str(proof.get("status") or "").upper()
        if validation_status not in {"GREEN", "RED"}:
            raise RequestRejected("TYPE2 validation proof status ongeldig")
        failures = proof.get("failures")
        checks = proof.get("checks")
        if not isinstance(failures, list) or not isinstance(checks, list):
            raise RequestRejected("TYPE2 validation proof inhoud ongeldig")
        if validation_status == "GREEN" and failures:
            raise RequestRejected("TYPE2 GREEN validation proof bevat failures")
        by_source = {str(x.get("source") or ""): x for x in checks if isinstance(x, dict)}
        privileged_source_hashes: dict[str, str] = {}
        quiet = max(0.05, float(proof.get("old_source_quiescence_seconds") or 2.0))
        for item in plan["items"]:
            check = by_source.get(item["source"])
            if not isinstance(check, dict):
                raise RequestRejected(f"TYPE2 validation source proof ontbreekt: {item['source']}")
            source = root / item["source"]
            destination = root / item["destination"]
            if not source.exists() or source.is_symlink():
                raise RequestRejected(f"TYPE2 validation source missing/unsafe: {item['source']}")
            if not destination.exists() or destination.is_symlink():
                raise RequestRejected(f"TYPE2 validation destination missing/unsafe: {item['destination']}")
            # The privileged executor is authoritative for source quiescence.
            # Cross-process snapshots can legitimately differ at the boundary
            # even after the old writer has stopped (for example transient
            # filesystem artefacts). Require two privileged snapshots to be
            # byte-identical across the quiet window instead of comparing one
            # PM snapshot against a later watcher snapshot.
            source_rows_before = _tree_rows(source, root)
            time.sleep(quiet)
            source_rows_after = _tree_rows(source, root)
            if source_rows_before != source_rows_after:
                raise RequestRejected(f"TYPE2 old source still mutating during validation commit: {item['source']}")
            source_hash = hashlib.sha256(
                json.dumps(source_rows_after, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
            ).hexdigest()
            privileged_source_hashes[item["source"]] = source_hash
            key = str(item.get("path_key") or "").strip()
            if key:
                marker = _read_json(_type2_activation_path(root, key))
                if marker.get("active") is not True or marker.get("destination") != item["destination"] or marker.get("plan_sha256") != plan["plan_sha256"]:
                    raise RequestRejected(f"TYPE2 path activation not proven during validation commit: {key}")
        committed_proof = json.loads(json.dumps(proof))
        committed_checks = committed_proof.get("checks") or []
        for check in committed_checks:
            if not isinstance(check, dict):
                continue
            source_rel = str(check.get("source") or "")
            if source_rel in privileged_source_hashes:
                check["pm_observed_source_rows_sha256"] = str(check.get("source_rows_sha256") or "")
                check["source_rows_sha256"] = privileged_source_hashes[source_rel]
                check["source_quiescence_authority"] = "privileged_watcher_double_snapshot"
        committed_proof["source_quiescence_authority"] = "privileged_watcher_double_snapshot"
        validation = root / service.VALIDATION_ROOT_REL / f"{clearup_id}.json"
        _atomic_write_json(validation, committed_proof)
        readback = _read_json(validation)
        if readback != committed_proof:
            raise RuntimeError("TYPE2 validation proof write/readback mismatch")
        after = service._snapshot_release_dirs(root)
        if after != request["mailbox_snapshot_before"]:
            raise RuntimeError("TYPE2 release mailboxes changed during validation commit")
        return request_id, {
            "status": "GREEN",
            "clearup_id": clearup_id,
            "phase": "VALIDATION_COMMITTED",
            "validation_status": validation_status,
            "deletion_performed": False,
        }

    if operation == "type2_finalize":
        service._assert_external_recovery_confirmed(root)
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
