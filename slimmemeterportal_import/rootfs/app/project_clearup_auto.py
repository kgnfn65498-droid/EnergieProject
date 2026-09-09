from __future__ import annotations

"""One-shot, explicitly approved 32.4.25+ CLEARUP execution gate.

No cleanup is attempted until the release itself is ACCEPTED, its validation
hold is released, the persisted user-approved scope is present, and a recent
Crash Recovery set is hash-verified.  The actual move remains delegated to the
same dependency-audited hard-rename implementation used by manual previews.
"""

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from project_clearup import apply_clearup_plan, build_clearup_plan

APPROVAL_RELATIVE = Path("Data/03_Systeem/Projectmanager/State/32_4_25_scope_cleanup_and_history_repair_20260909.md")
MAX_CR_AGE_SECONDS = 30 * 86400


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def _crash_recovery_gate(root: Path, *, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
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
        actual_sha = _sha256(latest)
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


def clearup_auto_gate(project_root: Path, *, app_version: str, now: datetime | None = None) -> dict[str, Any]:
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

    # Hashing a large Crash Recovery ZIP is intentionally deferred until the
    # release itself is settled; otherwise a startup poll would repeatedly read
    # hundreds of MB while acceptance is still in progress.
    if approval and accepted and hold_ok:
        cr = _crash_recovery_gate(root, now=now)
        if not cr.get("ok"):
            blockers.append("crash_recovery_not_verified")
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
        "crash_recovery": cr,
    }


def run_approved_clearup_once(
    project_root: Path,
    *,
    app_version: str,
    run_id: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    gate = clearup_auto_gate(root, app_version=app_version, now=now)
    if not gate["ready"]:
        return {"status": "blocked", "gate": gate, "delete_performed": False}

    # If this exact release already completed a quarantine run, do not create a
    # second one automatically. Manual restore/retry remains possible.
    clearup_root = root / "CLEARUP"
    if clearup_root.is_dir():
        for manifest_path in sorted(clearup_root.glob("*/manifest.json")):
            manifest = _read_json(manifest_path) or {}
            if manifest.get("current_version") == str(app_version) and manifest.get("hard_move") is True:
                return {
                    "status": "already_completed",
                    "run_id": manifest.get("run_id"),
                    "manifest": str(manifest_path.relative_to(root)),
                    "delete_performed": False,
                    "gate": gate,
                }

    plan = build_clearup_plan(root, current_version=str(app_version), keep_rollbacks=3)
    if int(plan.get("clearup_count") or 0) == 0:
        return {
            "status": "no_action",
            "review_count": int(plan.get("review_count") or 0),
            "plan_id": plan.get("plan_id"),
            "delete_performed": False,
            "gate": gate,
        }
    result = apply_clearup_plan(
        root,
        plan,
        confirmation=str(plan["confirmation_required"]),
        run_id=run_id,
    )
    return {**result, "gate": gate, "plan_id": plan.get("plan_id")}
