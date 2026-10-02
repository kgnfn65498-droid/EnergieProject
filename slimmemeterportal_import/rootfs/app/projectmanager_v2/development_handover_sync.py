from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from persistence import atomic_write_json, atomic_write_text
from system_path_contract import project_system_path

HANDOVER_REL = Path("Data/03_Systeem/Projectmanager/Handover/CURRENT_DEVELOPMENT_HANDOVER.md")
POINTER_REL = Path("Data/03_Systeem/Projectmanager/Handover/CURRENT_CHAT_SWITCH_POINTER.json")
SYNC_STATE_REL = Path("Data/03_Systeem/Projectmanager/Handover/CURRENT_HANDOVER_SYNC_STATE.json")
ACCEPTED_LIVE_DIR = Path("Data/03_Systeem/Projectmanager/ClearUp/State")
RELEASE_CONTROLLER_CURRENT = Path("Data/03_Systeem/Projectmanager/ReleaseController/current.json")
ATOMIC_SWAP_STATE = Path("Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json")
RELEASE_ARTIFACTS = Path("Data/03_Systeem/Projectmanager/ReleaseArtifacts")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _canonical_sha(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _live_release(root: Path, status: dict[str, Any] | None = None) -> str:
    path = root / "App/VERSIE.txt"
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("handover live release missing/unsafe")
    live = path.read_text(encoding="utf-8").strip()
    status_release = str((((status or {}).get("release") or {}).get("version")) or "").strip()
    if status_release and status_release != live:
        raise RuntimeError("handover live/status release mismatch")
    return live


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        parts = tuple(int(part) for part in str(value or "").strip().split("."))
    except ValueError:
        return ()
    return parts if len(parts) == 3 else ()


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _checkpoint_result(root: Path, path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    stat = path.stat()
    return {
        "status": "GREEN",
        "path": path.relative_to(root).as_posix(),
        "mtime_ns": stat.st_mtime_ns,
        "payload": payload,
        "ranking_basis": "accepted_live",
        "ranking_value": float(payload.get("checkpoint_sequence") or 0),
        "legacy_rank_fallback": False,
        "invalid_candidates": [],
    }


def reconcile_accepted_live(project_root: Path | str, status: dict[str, Any] | None) -> dict[str, Any] | None:
    """Create/read one idempotent PM-owned accepted-live checkpoint from immutable live evidence."""
    root = Path(project_root).resolve()
    live = _live_release(root, status)
    if _version_tuple(live) < (32, 5, 31):
        return None

    rc = _json_object(root / RELEASE_CONTROLLER_CURRENT)
    atomic = _json_object(root / ATOMIC_SWAP_STATE)
    ha = _json_object(Path(project_system_path(root, "Inbox/ha_runtime/current.json")))
    release_status = (status or {}).get("release") if isinstance((status or {}).get("release"), dict) else {}

    artifact_sha = str(rc.get("artifact_sha256") or "").strip().lower()
    artifact_name = str(rc.get("artifact_name") or f"EnergieProject_v{live}.zip").strip()
    rc_exact = bool(
        rc.get("status") == "COMPLETE"
        and rc.get("phase") == "COMPLETE"
        and int(rc.get("step") or 0) == int(rc.get("total") or 0)
        and int(rc.get("total") or 0) > 0
        and str(rc.get("to_version") or "") == live
        and str(rc.get("release_id") or "").strip()
        and str(rc.get("generation") or "").strip()
        and len(artifact_sha) == 64
        and all(ch in "0123456789abcdef" for ch in artifact_sha)
        and release_status.get("active_verified") is True
    )
    atomic_exact = bool(
        atomic.get("state") == "ACCEPTED"
        and str(atomic.get("to_version") or "") == live
        and str(atomic.get("artifact_sha256") or "").strip().lower() == artifact_sha
        and str(atomic.get("from_version") or "").strip() == str(rc.get("from_version") or "").strip()
    )
    ha_exact = str(ha.get("version") or "").strip() == live
    if not (rc_exact and atomic_exact and ha_exact):
        return None

    candidates = (
        root / RELEASE_ARTIFACTS / artifact_name,
        root / "Inbox/processed" / artifact_name,
    )
    artifact = next((item for item in candidates if item.is_file() and not item.is_symlink()), None)
    if artifact is None or _sha(artifact) != artifact_sha:
        return None

    checkpoint_path = root / ACCEPTED_LIVE_DIR / f"CHECKPOINT_{live}_ACCEPTED_LIVE.json"
    existing = _json_object(checkpoint_path)
    identity = {
        "release_id": str(rc.get("release_id") or ""),
        "generation": str(rc.get("generation") or ""),
        "artifact_sha256": artifact_sha,
        "from_version": str(atomic.get("from_version") or ""),
        "rollback_path": str(atomic.get("rollback_path") or ""),
        "ha_runtime_version": live,
    }
    if existing:
        exact = bool(
            existing.get("schema") == "energie_accepted_live_checkpoint_v1"
            and existing.get("status") == "ACCEPTED_LIVE"
            and str(existing.get("live_release") or "") == live
            and str(existing.get("target_release") or "") == live
            and all(str(existing.get(key) or "") == value for key, value in identity.items())
        )
        if not exact:
            raise RuntimeError("accepted-live checkpoint identity conflict")
        return _checkpoint_result(root, checkpoint_path, existing)

    version = _version_tuple(live)
    sequence = version[0] * 1000000 + version[1] * 10000 + version[2] * 100 + 99
    payload = {
        "schema": "energie_accepted_live_checkpoint_v1",
        "checkpoint_sequence": sequence,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "ACCEPTED_LIVE",
        "live_release": live,
        "target_release": live,
        **identity,
        "artifact": artifact.relative_to(root).as_posix(),
        "artifact_size": artifact.stat().st_size,
        "final_zip_exists": True,
        "release_ready": True,
        "live_cleanup_executed": False,
        "completed": [
            "ReleaseController COMPLETE exact identity",
            "atomic app swap ACCEPTED exact identity",
            "Home Assistant runtime exact/current",
            "governing release artifact SHA readback exact",
        ],
        "pending": [
            "clean new-chat/verder behavioral E2E",
            "client MCP catalog parity receipt",
        ],
        "blockers": [],
        "next_action": (
            f"Run clean new-chat/verder acceptance for {live}; verify client MCP parity; "
            "then continue the first unresolved governed roadmap item."
        ),
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(checkpoint_path, payload, mode=0o644)
    if _json_object(checkpoint_path) != payload:
        raise RuntimeError("accepted-live checkpoint readback mismatch")
    if checkpoint_path.stat().st_mode & 0o777 != 0o644:
        raise RuntimeError("accepted-live checkpoint mode mismatch")
    return _checkpoint_result(root, checkpoint_path, payload)


def _checkpoint_projection(root: Path, status: dict[str, Any] | None, checkpoint: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(checkpoint, dict) or checkpoint.get("status") != "GREEN":
        raise RuntimeError("handover highest checkpoint missing")
    rel = str(checkpoint.get("path") or "").strip()
    if not rel:
        raise RuntimeError("handover checkpoint path missing")
    path = root / rel
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("handover checkpoint missing/unsafe")
    payload = checkpoint.get("payload") if isinstance(checkpoint.get("payload"), dict) else {}
    live = _live_release(root, status)
    checkpoint_live = str(payload.get("live_release") or payload.get("live_production") or live).strip()
    if checkpoint_live and checkpoint_live != live:
        raise RuntimeError("handover checkpoint/live release mismatch")
    target = str(payload.get("target_release") or live).strip()
    checkpoint_sha = _sha(path)
    final_zip_exists = payload.get("final_zip_exists") is True
    release_ready = bool(payload.get("release_ready") is True and final_zip_exists)
    identity = {
        "checkpoint": rel,
        "checkpoint_sha256": checkpoint_sha,
        "live_release": live,
        "target_release": target,
        "development_status": str(payload.get("status") or "UNKNOWN"),
        "predecessor_artifact": str(payload.get("predecessor_artifact") or ""),
        "predecessor_sha256": str(payload.get("predecessor_sha256") or ""),
        "final_zip_exists": final_zip_exists,
        "release_ready": release_ready,
        "live_cleanup_executed": payload.get("live_cleanup_executed") is True,
        "completed": list(payload.get("completed") or []),
        "pending": list(payload.get("pending") or []),
        "next_action": str(payload.get("next_action") or ""),
    }
    return {**identity, "source_generation": _canonical_sha(identity)}


def _handover_markdown(projection: dict[str, Any], generated_at: str) -> str:
    completed = projection.get("completed") or []
    pending = projection.get("pending") or []
    lines = [
        "# CURRENT DEVELOPMENT HANDOVER — AUTO-SYNC",
        f"<!-- HANDOVER_GENERATION:{projection['source_generation']} -->",
        f"<!-- CHECKPOINT_SHA256:{projection['checkpoint_sha256']} -->",
        f"<!-- CHECKPOINT_PATH:{projection['checkpoint']} -->",
        "",
        f"Generated at: {generated_at}",
        f"Live release: **{projection['live_release']}**",
        f"Target release: **{projection['target_release']}**",
        f"Development status: **{projection['development_status']}**",
        f"Final ZIP exists: **{'yes' if projection['final_zip_exists'] else 'no'}**",
        f"Release ready: **{'yes' if projection['release_ready'] else 'no'}**",
        f"Live cleanup executed: **{'yes' if projection['live_cleanup_executed'] else 'no'}**",
        f"Checkpoint: `{projection['checkpoint']}`",
        f"Checkpoint SHA256: `{projection['checkpoint_sha256']}`",
        f"Predecessor artifact: `{projection['predecessor_artifact']}`",
        f"Predecessor SHA256: `{projection['predecessor_sha256']}`",
        "",
        "## Completed",
    ]
    lines.extend(f"- {item}" for item in completed)
    if not completed:
        lines.append("- none recorded")
    lines.extend(["", "## Pending"])
    lines.extend(f"- {item}" for item in pending)
    if not pending:
        lines.append("- none recorded")
    lines.extend([
        "",
        "## Next action",
        projection.get("next_action") or "No next action recorded; fail closed until checkpoint is complete.",
        "",
        "## Continuity rule",
        "This file and CURRENT_CHAT_SWITCH_POINTER.json are generated projections of the highest valid development checkpoint. A mismatch is HANDOVER_STALE/RED and must be reconciled before release-ready or new-chat continuation.",
        "",
    ])
    return "\n".join(lines)


def evaluate_handover_freshness(project_root: Path | str, *, checkpoint: dict[str, Any], status: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    reasons: list[str] = []
    try:
        expected = _checkpoint_projection(root, status, checkpoint)
    except Exception as exc:
        return {"status": "RED", "fail_closed": True, "reasons": [f"projection_error:{type(exc).__name__}:{exc}"]}

    pointer_path = root / POINTER_REL
    handover_path = root / HANDOVER_REL
    pointer: dict[str, Any] = {}
    try:
        raw = json.loads(pointer_path.read_text(encoding="utf-8"))
        pointer = raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError, UnicodeError):
        reasons.append("pointer_missing_or_invalid")
    try:
        handover = handover_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        handover = ""
        reasons.append("handover_missing_or_invalid")

    if pointer:
        if str(pointer.get("source_generation") or "") != expected["source_generation"]:
            reasons.append("pointer_generation_mismatch")
        if str(pointer.get("checkpoint") or "") != expected["checkpoint"]:
            reasons.append("pointer_checkpoint_mismatch")
        if str(pointer.get("checkpoint_sha256") or "") != expected["checkpoint_sha256"]:
            reasons.append("pointer_checkpoint_sha_mismatch")
        for field in ("live_release", "target_release", "development_status", "predecessor_artifact", "predecessor_sha256"):
            if str(pointer.get(field) or "") != str(expected.get(field) or ""):
                reasons.append(f"pointer_{field}_mismatch")
        for field in ("final_zip_exists", "release_ready", "live_cleanup_executed"):
            if pointer.get(field) is not expected.get(field):
                reasons.append(f"pointer_{field}_mismatch")

    if handover:
        if f"HANDOVER_GENERATION:{expected['source_generation']}" not in handover:
            reasons.append("handover_generation_mismatch")
        if f"CHECKPOINT_SHA256:{expected['checkpoint_sha256']}" not in handover:
            reasons.append("handover_checkpoint_sha_mismatch")
        if f"CHECKPOINT_PATH:{expected['checkpoint']}" not in handover:
            reasons.append("handover_checkpoint_mismatch")
        if f"Live release: **{expected['live_release']}**" not in handover:
            reasons.append("handover_live_release_mismatch")
        if f"Target release: **{expected['target_release']}**" not in handover:
            reasons.append("handover_target_release_mismatch")

    return {
        "status": "GREEN" if not reasons else "RED",
        "fail_closed": bool(reasons),
        "reasons": sorted(set(reasons)),
        "source_generation": expected["source_generation"],
        "checkpoint": expected["checkpoint"],
        "checkpoint_sha256": expected["checkpoint_sha256"],
        "live_release": expected["live_release"],
        "target_release": expected["target_release"],
        "release_ready": expected["release_ready"],
    }


def sync_current_development_handover(project_root: Path | str, status: dict[str, Any] | None, *, checkpoint: dict[str, Any]) -> dict[str, Any]:
    root = Path(project_root).resolve()
    projection = _checkpoint_projection(root, status, checkpoint)
    generated_at = datetime.now(timezone.utc).isoformat()
    pointer = {
        "schema": "energie_current_chat_switch_pointer_v2",
        **projection,
        "generated_at": generated_at,
        "handover": HANDOVER_REL.as_posix(),
        "instruction": "Read live runtime first, then this pointer, the exact checkpoint and CURRENT_DEVELOPMENT_HANDOVER. Resume next_action only when this projection is GREEN/fresh; never infer release-ready from VERSIE.txt.",
    }
    handover = _handover_markdown(projection, generated_at)
    atomic_write_json(root / POINTER_REL, pointer, mode=0o644)
    atomic_write_text(root / HANDOVER_REL, handover, mode=0o644)
    readback = evaluate_handover_freshness(root, checkpoint=checkpoint, status=status)
    sync_state = {
        "schema": "energie_current_handover_sync_state_v1",
        "status": readback["status"],
        "fail_closed": readback["fail_closed"],
        "source_generation": projection["source_generation"],
        "checkpoint": projection["checkpoint"],
        "checkpoint_sha256": projection["checkpoint_sha256"],
        "pointer_sha256": _sha(root / POINTER_REL),
        "handover_sha256": _sha(root / HANDOVER_REL),
        "synced_at": generated_at,
        "readback_reasons": readback.get("reasons") or [],
    }
    atomic_write_json(root / SYNC_STATE_REL, sync_state, mode=0o644)
    if readback["status"] != "GREEN":
        raise RuntimeError("handover sync readback failed:" + ",".join(readback.get("reasons") or []))
    return {**readback, "synced_at": generated_at, "sync_state": SYNC_STATE_REL.as_posix()}
