from __future__ import annotations

"""32.5.26 scoped final Inbox cleanup orchestration.

This module is intentionally *not* a privileged filesystem executor.  It builds
an exact, hash-bound plan, publishes it through the existing 32.5.x ClearUp
sideband, and waits for the privileged watcher/executor to return the result.
All mutations therefore stay on the proven 32.5.x execution boundary.
"""

import hashlib
import json
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from system_path_contract import project_system_path

MIN_VERSION = (32, 5, 26)
SCOPED_REQUEST_SCHEMA = "energie_clearup_scoped_request_v1"
SCOPED_RESULT_SCHEMA = "energie_clearup_scoped_result_v1"
PLAN_SCHEMA = "energie_clearup_scoped_plan_v1"
WATCHER_REQUEST_REL = Path("Inbox/project_clearup_move_request.json")
WATCHER_RESULT_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Runtime/results")
WATCHER_TIMEOUT_SECONDS = 90.0

FINAL_LEGACY = (
    "Inbox/release_hold_tmp",
    "Inbox/crash_recovery_cleanup_result.json",
    "Inbox/github_publication_state.pre_59_recovery.json",
    "Inbox/ha_publication_required.json.corrective.22616",
    "Inbox/ha_publication_required.json.settled.10928",
    "Inbox/.github_publisher.lock",
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


def _watcher_call(root: Path, *, operation: str, plan: dict[str, Any] | None = None, run_id: str = "", explicit_approval: bool = False) -> dict[str, Any]:
    request_path = root / WATCHER_REQUEST_REL
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
    normalized = " ".join(str(explicit_user_text or "").strip().split()).upper()
    if source != "mcp_remote" or normalized != plan["confirmation_required"].upper():
        return {
            "status": "APPROVAL_REQUIRED",
            "executed": False,
            "plan_sha256": plan["plan_sha256"],
            "confirmation_required": plan["confirmation_required"],
            "action_count": len(plan["actions"]),
        }
    result = _watcher_call(root, operation="scoped_apply", plan=plan, explicit_approval=True)
    return {**result, "plan_sha256": plan["plan_sha256"], "confirmation_required": plan["confirmation_required"]}


def restore_final_inbox_cleanup(project_root: Path | str, *, run_id: str, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    run_id = str(run_id or "").strip()
    expected = f"RESTORE INBOX CLEANUP {run_id}"
    normalized = " ".join(str(explicit_user_text or "").strip().split()).upper()
    if not run_id or source != "mcp_remote" or normalized != expected.upper():
        return {"status": "APPROVAL_REQUIRED", "executed": False, "confirmation_required": expected, "run_id": run_id}
    return _watcher_call(root, operation="scoped_restore", run_id=run_id, explicit_approval=True)
