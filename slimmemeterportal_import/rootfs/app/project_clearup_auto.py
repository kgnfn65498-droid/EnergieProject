from __future__ import annotations

"""One-shot, explicitly approved 32.4.25+ CLEARUP execution gate.

No cleanup is attempted until the release itself is ACCEPTED, its validation
hold is released, the persisted user-approved scope is present, and a recent
Crash Recovery set is hash-verified.  The actual move remains delegated to the
same dependency-audited hard-rename implementation used by manual previews.
"""

import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from project_clearup import ClearupExecutionTimeout, apply_clearup_plan, build_clearup_plan

APPROVAL_RELATIVE = Path("Data/03_Systeem/Projectmanager/State/32_4_25_scope_cleanup_and_history_repair_20260909.md")
MAX_CR_AGE_SECONDS = 30 * 86400
CLEARUP_MOVE_REQUEST_RELATIVE = Path("Inbox/project_clearup_move_request.json")
CLEARUP_MOVE_RESULT_RELATIVE = Path("Inbox/logs/project_clearup_move_result.json")
CLEARUP_MOVE_REQUEST_SCHEMA = "energie_project_clearup_move_request_v1"
CLEARUP_MOVE_RESULT_SCHEMA = "energie_project_clearup_move_result_v1"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"CLEARUP bridge weigert symlinkpad: {path}")
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _apply_clearup_via_watcher(
    root: Path,
    plan: dict[str, Any],
    *,
    run_id: str | None,
    deadline_monotonic: float,
    progress_callback: Callable[[dict[str, Any]], None] | None,
    started_monotonic: float,
) -> dict[str, Any]:
    request_path = root / CLEARUP_MOVE_REQUEST_RELATIVE
    result_path = root / CLEARUP_MOVE_RESULT_RELATIVE
    if request_path.is_symlink() or result_path.is_symlink():
        raise RuntimeError("CLEARUP watcher bridge weigert symlink request/result pad")
    if request_path.exists():
        existing = _read_json(request_path) or {}
        raise RuntimeError(f"CLEARUP watcher request bestaat al: {existing.get('request_id') or 'unknown'}")
    if result_path.exists():
        result_path.unlink()

    remaining = float(deadline_monotonic) - time.monotonic()
    if remaining <= 0:
        raise ClearupExecutionTimeout("qnap_apply_wait")
    effective_run_id = run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    request_id = secrets.token_hex(16)
    payload = {
        "schema": CLEARUP_MOVE_REQUEST_SCHEMA,
        "request_id": request_id,
        "operation": "apply",
        "release_version": str(plan.get("current_version") or ""),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=remaining)).isoformat(),
        "plan": plan,
        "confirmation": str(plan.get("confirmation_required") or ""),
        "run_id": effective_run_id,
    }
    _emit_progress(
        progress_callback, phase="apply", started_monotonic=started_monotonic,
        stage="watcher_request", candidate_total=int(plan.get("clearup_count") or 0),
    )
    _atomic_write_json(request_path, payload)
    try:
        while time.monotonic() < deadline_monotonic:
            response = _read_json(result_path)
            if response and response.get("request_id") == request_id:
                if str(response.get("schema") or "") != CLEARUP_MOVE_RESULT_SCHEMA:
                    raise RuntimeError("CLEARUP watcher result schema ongeldig")
                status = str(response.get("status") or "").lower()
                if status != "completed":
                    raise RuntimeError(f"CLEARUP watcher executor {status or 'unknown'}: {response.get('error')}")
                result = response.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("CLEARUP watcher result payload ontbreekt")
                if result.get("delete_performed") not in (None, False):
                    raise RuntimeError("CLEARUP watcher result rapporteert onverwachte delete")
                _emit_progress(
                    progress_callback, phase="manifest", started_monotonic=started_monotonic,
                    manifest=result.get("manifest"), moved_count=int(result.get("moved_count") or 0),
                    review_count=int(result.get("review_count") or 0), stage="watcher_completed",
                )
                return result
            _emit_progress(
                progress_callback, phase="qnap_apply_wait", started_monotonic=started_monotonic,
                request_id=request_id, run_id=effective_run_id,
            )
            time.sleep(0.25)
        raise ClearupExecutionTimeout("qnap_apply_wait")
    finally:
        try:
            current = _read_json(request_path)
            if current and current.get("request_id") == request_id:
                request_path.unlink(missing_ok=True)
        except OSError:
            pass


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _sha256(path: Path, *, deadline_monotonic: float | None = None) -> str:
    digest = hashlib.sha256()
    if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
        raise ClearupExecutionTimeout("crash_recovery_check")
    with path.open("rb") as handle:
        while True:
            if deadline_monotonic is not None and time.monotonic() >= float(deadline_monotonic):
                raise ClearupExecutionTimeout("crash_recovery_check")
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _emit_progress(
    progress_callback: Callable[[dict[str, Any]], None] | None,
    *,
    phase: str,
    started_monotonic: float,
    **details: Any,
) -> None:
    if progress_callback is None:
        return
    progress_callback({
        "phase": str(phase),
        "elapsed_seconds": round(max(0.0, time.monotonic() - float(started_monotonic)), 3),
        **details,
    })


def _approval_ok(root: Path) -> bool:
    path = root / APPROVAL_RELATIVE
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "Status: DEVELOPMENT SCOPE APPROVED BY USER" in text and "CLEARUP" in text


def _release_accepted(root: Path, app_version: str) -> tuple[bool, dict[str, Any]]:
    atomic = _read_json(root / "Inbox/atomic_app_swap_state.json") or {}
    ok = str(atomic.get("state") or "").upper() == "ACCEPTED" and str(atomic.get("to_version") or "") == str(app_version)
    return ok, atomic


def _hold_released(root: Path) -> tuple[bool, dict[str, Any]]:
    hold = _read_json(root / "Inbox/operating_mode/release_validation_hold.json") or {}
    ok = hold.get("active") is False and str(hold.get("validation_status") or "").lower() == "ok"
    return ok, hold


def _parse_expected_sha(text: str) -> str | None:
    match = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    return match.group(1).lower() if match else None


def _practical_recovery_acceptance(root: Path) -> dict[str, Any]:
    state_root = root / "Data/03_Systeem/Projectmanager/State"
    try:
        candidates = sorted(state_root.glob("crash_recovery_closure_*.json"), reverse=True)
    except OSError:
        candidates = []
    for path in candidates:
        data = _read_json(path)
        if not data:
            continue
        scope = {str(item).strip() for item in (data.get("scope") or [])}
        evidence = data.get("evidence") if isinstance(data.get("evidence"), dict) else {}
        project = evidence.get("EnergieProject") if isinstance(evidence.get("EnergieProject"), dict) else {}
        containers = evidence.get("NAS_Containers") if isinstance(evidence.get("NAS_Containers"), dict) else {}
        home_assistant = evidence.get("Home_Assistant") if isinstance(evidence.get("Home_Assistant"), dict) else {}
        ok = bool(
            str(data.get("status") or "").upper() == "GREEN_PRACTICAL_ACCEPTANCE_COMPLETE"
            and {"EnergieProject", "NAS/Containers", "Home Assistant"}.issubset(scope)
            and str(project.get("zip_integrity") or "").lower() == "ok"
            and int(project.get("hash_failures") or 0) == 0
            and str(containers.get("restore_extract") or "").lower() == "ok"
            and containers.get("production_containers_changed") is False
            and str(home_assistant.get("backup_manager_state_after_run") or "").lower() == "idle"
        )
        if ok:
            return {"ok": True, "path": str(path), "status": data.get("status")}
    return {"ok": False, "path": None, "status": None}


def _crash_recovery_gate(root: Path, *, now: datetime | None = None, deadline_monotonic: float | None = None, progress_callback: Callable[[dict[str, Any]], None] | None = None, started_monotonic: float | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    started = time.monotonic() if started_monotonic is None else float(started_monotonic)
    _emit_progress(progress_callback, phase="crash_recovery_check", started_monotonic=started, stage="start")
    cr = root / "Backups/CrashRecovery"
    try:
        zips = [path for path in cr.glob("*.zip") if path.is_file()]
    except OSError:
        zips = []
    if not zips:
        return {"ok": False, "reason": "backup_missing"}
    latest = max(zips, key=lambda path: path.stat().st_mtime)
    stem = latest.with_suffix("")
    sha_path = Path(str(stem) + ".sha256")
    manifest_path = Path(str(stem) + ".manifest.json")
    restore_path = Path(str(stem) + ".restore.txt")
    if not all(path.is_file() for path in (sha_path, manifest_path, restore_path)):
        return {"ok": False, "reason": "backup_sidecars_incomplete", "backup": str(latest)}
    try:
        age = max(0.0, now.timestamp() - latest.stat().st_mtime)
        expected_sha = _parse_expected_sha(sha_path.read_text(encoding="utf-8"))
        actual_sha = _sha256(latest, deadline_monotonic=deadline_monotonic)
        manifest = _read_json(manifest_path)
        restore_text = restore_path.read_text(encoding="utf-8", errors="replace").upper()
    except OSError as exc:
        return {"ok": False, "reason": "backup_verification_io_error", "error": str(exc), "backup": str(latest)}
    explicit_restore_validation = any(word in restore_text for word in ("VALID", "VERIFIED", "GESLAAGD"))
    practical = _practical_recovery_acceptance(root)
    restore_chain_proven = explicit_restore_validation or practical["ok"]
    ok = bool(
        age <= MAX_CR_AGE_SECONDS
        and expected_sha
        and expected_sha == actual_sha
        and isinstance(manifest, dict)
        and (manifest.get("file_count") is None or int(manifest.get("file_count") or 0) > 0)
        and restore_path.stat().st_size > 0
        and restore_chain_proven
    )
    return {
        "ok": ok,
        "reason": "verified" if ok else "backup_verification_failed",
        "backup": str(latest),
        "age_seconds": round(age, 1),
        "sha256": actual_sha,
        "explicit_restore_validation": explicit_restore_validation,
        "practical_acceptance": practical["ok"],
        "practical_acceptance_path": practical["path"],
    }



def _clearup_destination_gate(root: Path) -> dict[str, Any]:
    """Prove the pre-created quarantine root is safe and writable before heavy scans."""
    clearup_root = root / "CLEARUP"
    if clearup_root.is_symlink():
        return {"ok": False, "reason": "clearup_root_symlink", "path": str(clearup_root)}
    if not clearup_root.exists():
        return {"ok": False, "reason": "clearup_root_missing", "path": str(clearup_root)}
    if not clearup_root.is_dir():
        return {"ok": False, "reason": "clearup_root_not_directory", "path": str(clearup_root)}
    try:
        if clearup_root.stat().st_dev != root.stat().st_dev:
            return {"ok": False, "reason": "clearup_root_cross_filesystem", "path": str(clearup_root)}
        probe = clearup_root / f".clearup-runtime-probe.{os.getpid()}"
        with probe.open("x", encoding="utf-8") as handle:
            handle.write("clearup-runtime-write-probe\n")
            handle.flush()
            os.fsync(handle.fileno())
        probe.unlink()
    except OSError as exc:
        try:
            probe.unlink(missing_ok=True)
        except (OSError, UnboundLocalError):
            pass
        return {"ok": False, "reason": "clearup_root_not_writable", "path": str(clearup_root), "error": f"{type(exc).__name__}: {exc}"}
    return {"ok": True, "reason": "verified", "path": str(clearup_root)}

def clearup_auto_gate(
    project_root: Path, *, app_version: str, now: datetime | None = None,
    deadline_monotonic: float | None = None,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
    started_monotonic: float | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    accepted, atomic = _release_accepted(root, app_version)
    hold_ok, hold = _hold_released(root)
    approval = _approval_ok(root)
    blockers: list[str] = []
    if not approval:
        blockers.append("user_approval")
    if not accepted:
        blockers.append("release_not_accepted")
    if not hold_ok:
        blockers.append("release_hold_not_released")

    # The quarantine destination is a release prerequisite.  Prove it before
    # hashing Crash Recovery or any CLEARUP candidate so a permission problem
    # fails quickly and never after minutes of expensive NAS reads.
    if approval and accepted and hold_ok:
        clearup_destination = _clearup_destination_gate(root)
        if not clearup_destination.get("ok"):
            blockers.append("clearup_root_not_ready")
    else:
        clearup_destination = {"ok": False, "reason": "deferred_until_release_acceptance", "path": str(root / "CLEARUP")}

    # Hashing a large Crash Recovery ZIP is intentionally deferred until the
    # release itself is settled and the quarantine destination is proven.
    if approval and accepted and hold_ok and clearup_destination.get("ok"):
        cr = _crash_recovery_gate(
            root, now=now, deadline_monotonic=deadline_monotonic,
            progress_callback=progress_callback, started_monotonic=started_monotonic,
        )
        if not cr.get("ok"):
            blockers.append("crash_recovery_not_verified")
    elif approval and accepted and hold_ok:
        cr = {"ok": False, "reason": "deferred_until_clearup_root_ready"}
    else:
        cr = {"ok": False, "reason": "deferred_until_release_acceptance"}
        if not accepted or not approval or not hold_ok:
            # Keep the blocker visible without performing the expensive proof.
            blockers.append("crash_recovery_not_verified")
    return {
        "ready": not blockers,
        "blockers": blockers,
        "app_version": str(app_version),
        "user_approval": approval,
        "atomic": atomic,
        "release_hold": hold,
        "clearup_destination": clearup_destination,
        "crash_recovery": cr,
    }


def run_approved_clearup_once(
    project_root: Path,
    *,
    app_version: str,
    run_id: str | None = None,
    now: datetime | None = None,
    timeout_seconds: float = 25 * 60,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    started_monotonic = time.monotonic()
    timeout = max(0.0, float(timeout_seconds))
    deadline_monotonic = started_monotonic + timeout
    _emit_progress(progress_callback, phase="gate", started_monotonic=started_monotonic, stage="start")
    if timeout <= 0:
        raise ClearupExecutionTimeout("gate")
    gate = clearup_auto_gate(
        root, app_version=app_version, now=now, deadline_monotonic=deadline_monotonic,
        progress_callback=progress_callback, started_monotonic=started_monotonic,
    )
    if not gate["ready"]:
        return {"status": "blocked", "gate": gate, "delete_performed": False}

    clearup_root = root / "CLEARUP"
    if clearup_root.is_dir():
        for manifest_path in sorted(clearup_root.glob("*/manifest.json")):
            if time.monotonic() >= deadline_monotonic:
                raise ClearupExecutionTimeout("candidate_inventory")
            manifest = _read_json(manifest_path) or {}
            if manifest.get("current_version") == str(app_version) and manifest.get("hard_move") is True:
                return {
                    "status": "already_completed",
                    "run_id": manifest.get("run_id"),
                    "manifest": str(manifest_path.relative_to(root)),
                    "delete_performed": False,
                    "gate": gate,
                }

    plan = build_clearup_plan(
        root, current_version=str(app_version), keep_rollbacks=3,
        deadline_monotonic=deadline_monotonic, progress_callback=progress_callback,
        started_monotonic=started_monotonic,
    )
    if int(plan.get("clearup_count") or 0) == 0:
        return {
            "status": "no_action",
            "review_count": int(plan.get("review_count") or 0),
            "plan_id": plan.get("plan_id"),
            "delete_performed": False,
            "gate": gate,
        }
    stale_plan_id = plan.get("plan_id")
    try:
        result = _apply_clearup_via_watcher(
            root,
            plan,
            run_id=run_id,
            deadline_monotonic=deadline_monotonic,
            progress_callback=progress_callback,
            started_monotonic=started_monotonic,
        )
        return {**result, "gate": gate, "plan_id": stale_plan_id}
    except RuntimeError as exc:
        if str(exc) != "CLEARUP-plan is gewijzigd; nieuwe dependency-audit vereist.":
            raise

    _emit_progress(
        progress_callback,
        phase="fresh_dependency_audit",
        started_monotonic=started_monotonic,
        stale_plan_id=stale_plan_id,
    )
    if time.monotonic() >= deadline_monotonic:
        raise ClearupExecutionTimeout("fresh_dependency_audit")
    fresh_plan = build_clearup_plan(
        root, current_version=str(app_version), keep_rollbacks=3,
        deadline_monotonic=deadline_monotonic, progress_callback=progress_callback,
        started_monotonic=started_monotonic,
    )
    fresh_plan_id = fresh_plan.get("plan_id")
    if not fresh_plan_id or fresh_plan_id == stale_plan_id:
        raise RuntimeError("CLEARUP verse dependency-audit leverde geen nieuw plan-id op")
    if int(fresh_plan.get("clearup_count") or 0) == 0:
        return {
            "status": "no_action",
            "review_count": int(fresh_plan.get("review_count") or 0),
            "plan_id": fresh_plan_id,
            "stale_plan_id": stale_plan_id,
            "replanned_after_stale": True,
            "delete_performed": False,
            "gate": gate,
        }
    result = _apply_clearup_via_watcher(
        root,
        fresh_plan,
        run_id=run_id,
        deadline_monotonic=deadline_monotonic,
        progress_callback=progress_callback,
        started_monotonic=started_monotonic,
    )
    return {
        **result,
        "gate": gate,
        "plan_id": fresh_plan_id,
        "stale_plan_id": stale_plan_id,
        "replanned_after_stale": True,
    }

