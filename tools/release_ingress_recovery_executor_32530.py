from __future__ import annotations

"""32.5.30 bounded autonomous Incoming/Processing recovery executor.

This runs inside the single-owner release watcher. It never guesses: every
mutation is derived from a read-only snapshot and guarded by an exact
fingerprint that is recomputed immediately before apply.
"""

import hashlib
import json
import os
import stat
import time
import zipfile
from pathlib import Path
from typing import Any

from system_path_contract import project_system_path

REQUEST_SCHEMA = "energie_release_ingress_recovery_request_v2"
RESULT_SCHEMA = "energie_release_ingress_recovery_result_v2"
REQUEST_REL = "Inbox/projectmanager_v2/RuntimeV2/release_ingress/recovery_request.json"
RESULT_REL = "Inbox/projectmanager_v2/RuntimeV2/release_ingress/recovery_result.json"
STALE_SECONDS = 600
_ALLOWED_LOCK_FILES = {"owner.json", "heartbeat"}


class RecoveryRejected(RuntimeError):
    pass


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        parts = tuple(int(x) for x in str(value).split("."))
    except ValueError:
        return ()
    return parts if len(parts) == 3 else ()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _json(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RecoveryRejected(f"unsafe result symlink:{path}")
    tmp = path.with_name("." + path.name + f".tmp-{os.getpid()}")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o666)
        except OSError:
            pass
    finally:
        tmp.unlink(missing_ok=True)


def _regular_zips(directory: Path) -> list[Path]:
    if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
        raise RecoveryRejected(f"unsafe mailbox:{directory}")
    if not directory.is_dir():
        return []
    rows: list[Path] = []
    for path in sorted(directory.glob("*.zip"), key=lambda p: p.name):
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise RecoveryRejected(f"unsafe ZIP entry:{path}")
        rows.append(path)
    return rows


def _zip_version(path: Path) -> tuple[bool, str]:
    try:
        with zipfile.ZipFile(path, "r") as archive:
            if archive.testzip() is not None:
                return False, ""
            try:
                value = archive.read("VERSIE.txt").decode("utf-8").strip()
            except KeyError:
                return False, ""
            return bool(_version_tuple(value)), value
    except (OSError, UnicodeError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return False, ""


def _row(path: Path, now: float) -> dict[str, Any]:
    integral, version = _zip_version(path)
    return {
        "name": path.name,
        "size": path.stat().st_size,
        "sha256": _sha256(path),
        "age_seconds": round(max(0.0, now - path.stat().st_mtime), 3),
        "integral": integral,
        "candidate_version": version,
    }


def _lock_snapshot(lock: Path, now: float) -> dict[str, Any]:
    try:
        st = lock.lstat()
    except FileNotFoundError:
        return {"state": "absent", "age_seconds": None}
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        return {"state": "unsafe", "age_seconds": 0.0}
    names = sorted(p.name for p in lock.iterdir())
    if set(names) - _ALLOWED_LOCK_FILES:
        return {"state": "unsafe", "age_seconds": 0.0, "entries": names}
    owner = lock / "owner.json"
    owner_pid = 0
    if owner.exists():
        try:
            if owner.is_symlink() or not owner.is_file():
                return {"state": "unsafe", "age_seconds": 0.0, "entries": names}
            data = json.loads(owner.read_text(encoding="utf-8"))
            owner_pid = int(data.get("pid") or 0) if isinstance(data, dict) else 0
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
            return {"state": "unsafe", "age_seconds": 0.0, "entries": names}
        if owner_pid > 1 and (Path("/proc") / str(owner_pid)).is_dir():
            return {"state": "owner_alive", "age_seconds": 0.0, "entries": names, "owner_pid": owner_pid}
    newest = st.st_mtime
    heartbeat = lock / "heartbeat"
    if heartbeat.exists():
        try:
            if heartbeat.is_symlink() or not heartbeat.is_file():
                return {"state": "unsafe", "age_seconds": 0.0, "entries": names}
            newest = max(newest, heartbeat.stat().st_mtime)
            raw = float(heartbeat.read_text(encoding="utf-8").strip())
            if 0 < raw <= now + 300:
                newest = max(newest, raw)
        except (OSError, ValueError):
            pass
    age = max(0.0, now - newest)
    return {
        "state": "stale" if age >= STALE_SECONDS else "fresh",
        "age_seconds": round(age, 3),
        "entries": names,
        "owner_pid": owner_pid or None,
    }


def _semantic_state(data: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: data.get(key) for key in keys if data.get(key) not in (None, "", [], {})}


def _fingerprint(snapshot: dict[str, Any]) -> str:
    # Elapsed age values drift every second and are evidence, not identity.
    # Keep the classified state (fresh/stale) but remove only volatile ages.
    def stable(value: Any) -> Any:
        if isinstance(value, dict):
            return {k: stable(v) for k, v in value.items() if k != "age_seconds"}
        if isinstance(value, list):
            return [stable(v) for v in value]
        return value
    canonical = json.dumps(stable(snapshot), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def inspect(project_root: Path | str, *, now: float | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    now_value = float(time.time() if now is None else now)
    live = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    if _version_tuple(live) < (32, 5, 30):
        return {"status": "BLOCKED", "reason": "capability_requires_live_32.5.30_or_newer", "live_version": live}

    incoming = [_row(p, now_value) for p in _regular_zips(root / "Inbox/incoming")]
    processing = [_row(p, now_value) for p in _regular_zips(root / "Inbox/processing")]
    current = _json(project_system_path(root, "Inbox/release_controller/current.json"))
    atomic = _json(project_system_path(root, "Inbox/atomic_app_swap_state.json"))
    publication = _json(project_system_path(root, "Inbox/github_publication_state.json"))
    ha_required = _json(project_system_path(root, "Inbox/release_controller/Publication/ha_publication_required.json"))
    lock = _lock_snapshot(root / "Inbox/.installer.lock", now_value)

    target_version = processing[0]["candidate_version"] if len(processing) == 1 else ""
    target_sha = processing[0]["sha256"] if len(processing) == 1 else ""
    partial_evidence: list[str] = []
    if target_version:
        if str(current.get("status") or "") not in {"", "COMPLETE", "ROLLED_BACK"}:
            partial_evidence.append("release_controller_active")
        if str(current.get("to_version") or "") == target_version or str(current.get("artifact_sha256") or "") == target_sha:
            if str(current.get("status") or "") not in {"COMPLETE", "ROLLED_BACK"}:
                partial_evidence.append("release_controller_owns_candidate")
        if str(atomic.get("to_version") or "") == target_version or str(atomic.get("artifact_sha256") or "") == target_sha:
            partial_evidence.append("atomic_state_mentions_candidate")
        if (
            str(publication.get("version") or "") == target_version
            or str(publication.get("processed_zip_sha256") or "") == target_sha
            or str(publication.get("release_id") or "").startswith(target_version + ":")
        ):
            partial_evidence.append("publication_state_mentions_candidate")
        if str(ha_required.get("target_version") or ha_required.get("to_version") or "") == target_version:
            partial_evidence.append("ha_delivery_mentions_candidate")
        if (root / f"App.__candidate_{target_version}").exists():
            partial_evidence.append("candidate_tree_present")
        processed = root / "Inbox/processed" / processing[0]["name"]
        if processed.is_file() and not processed.is_symlink():
            partial_evidence.append("processed_artifact_same_name_present")

    snapshot = {
        "live_version": live,
        "incoming": incoming,
        "processing": processing,
        "installer_lock": lock,
        "release_controller": _semantic_state(current, (
            "status", "phase", "release_id", "generation", "from_version", "to_version",
            "artifact_name", "artifact_sha256", "step", "total",
        )),
        "atomic_state": _semantic_state(atomic, (
            "state", "from_version", "to_version", "artifact_sha256", "rollback_path",
        )),
        "publication_state": _semantic_state(publication, (
            "published", "version", "release_id", "generation", "processed_zip",
            "processed_zip_sha256", "target_exact", "publication_contract_active",
            "publication_contract_settled",
        )),
        "ha_publication_required": _semantic_state(ha_required, (
            "target_version", "to_version", "release_id", "generation", "artifact_sha256",
        )),
        "partial_evidence": sorted(set(partial_evidence)),
    }
    fp = _fingerprint(snapshot)

    plan: dict[str, Any] = {"action": "NONE", "recoverable": False}
    reason = "release_ingress_idle"
    controller_status = str(current.get("status") or "")
    controller_active = controller_status not in {"", "COMPLETE", "ROLLED_BACK"}

    if controller_active:
        reason = "release_controller_active"
    elif len(processing) > 1:
        reason = "multiple_processing_items"
    elif len(incoming) > 1:
        hashes = {row["sha256"] for row in incoming}
        if len(hashes) == 1 and all(row["integral"] for row in incoming):
            plan = {"action": "DEDUPLICATE_INCOMING", "recoverable": True}
            reason = "identical_incoming_duplicates"
        else:
            reason = "multiple_distinct_or_invalid_incoming"
    elif processing:
        row = processing[0]
        if incoming:
            reason = "incoming_and_processing_conflict"
        elif not row["integral"]:
            reason = "processing_candidate_not_integral"
        elif not _version_tuple(row["candidate_version"]) or _version_tuple(row["candidate_version"]) <= _version_tuple(live):
            reason = "processing_candidate_not_newer_than_live"
        elif snapshot["partial_evidence"]:
            reason = "partial_release_side_effects_present"
        elif lock["state"] in {"owner_alive", "fresh", "unsafe"}:
            reason = "installer_lock_not_recoverable"
        elif float(row["age_seconds"]) < STALE_SECONDS:
            reason = "processing_grace_period"
        else:
            action = "RECOVER_STALE_LOCK_AND_REQUEUE" if lock["state"] == "stale" else "REQUEUE_ORPHAN_PROCESSING"
            plan = {"action": action, "recoverable": True, "artifact_name": row["name"], "artifact_sha256": row["sha256"]}
            reason = "orphan_processing_proven"
    elif lock["state"] == "stale":
        plan = {"action": "REMOVE_STALE_INSTALLER_LOCK", "recoverable": True}
        reason = "stale_installer_lock_proven"
    elif lock["state"] in {"owner_alive", "fresh", "unsafe"}:
        reason = "installer_lock_active_or_unsafe"
    elif incoming:
        row = incoming[0]
        if row["integral"]:
            reason = "single_incoming_ready"
        elif float(row["age_seconds"]) >= STALE_SECONDS:
            plan = {"action": "QUARANTINE_STALE_CORRUPT", "recoverable": True, "artifact_name": row["name"], "artifact_sha256": row["sha256"]}
            reason = "stale_corrupt_incoming"
        else:
            reason = "incoming_candidate_still_stabilizing"

    status = "RECOVERABLE" if plan["recoverable"] else ("READY" if reason == "single_incoming_ready" else "IDLE" if reason == "release_ingress_idle" else "BLOCKED")
    return {
        "schema": "energie_release_ingress_recovery_inspection_v2",
        "status": status,
        "reason": reason,
        "fingerprint": fp,
        "snapshot": snapshot,
        "plan": plan,
        "executed": False,
    }


def _remove_stale_lock(lock: Path) -> None:
    snap = _lock_snapshot(lock, time.time())
    if snap.get("state") != "stale":
        raise RecoveryRejected("installer lock is no longer stale")
    names = {p.name for p in lock.iterdir()}
    if names - _ALLOWED_LOCK_FILES:
        raise RecoveryRejected("installer lock entries changed")
    for name in sorted(names):
        path = lock / name
        st = path.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise RecoveryRejected("unsafe installer lock entry")
        path.unlink()
    lock.rmdir()


def _unique_failed(root: Path, source: Path, suffix: str) -> Path:
    failed = root / "Inbox/failed"
    if failed.exists() and (failed.is_symlink() or not failed.is_dir()):
        raise RecoveryRejected("failed mailbox unsafe")
    failed.mkdir(parents=True, exist_ok=True)
    candidate = failed / f"{source.stem}.{suffix}.zip"
    index = 1
    while candidate.exists():
        candidate = failed / f"{source.stem}.{suffix}.{index}.zip"
        index += 1
    return candidate


def apply(project_root: Path | str, *, expected_fingerprint: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    current = inspect(root)
    if current.get("fingerprint") != expected_fingerprint:
        raise RecoveryRejected("ingress recovery fingerprint changed")
    plan = current.get("plan") if isinstance(current.get("plan"), dict) else {}
    if current.get("status") != "RECOVERABLE" or plan.get("recoverable") is not True:
        return {**current, "executed": False}

    action = str(plan.get("action") or "")
    lock = root / "Inbox/.installer.lock"
    incoming = root / "Inbox/incoming"
    processing = root / "Inbox/processing"
    changed: list[str] = []

    if action == "REMOVE_STALE_INSTALLER_LOCK":
        _remove_stale_lock(lock)
        changed.append("Inbox/.installer.lock")
    elif action in {"REQUEUE_ORPHAN_PROCESSING", "RECOVER_STALE_LOCK_AND_REQUEUE"}:
        name = str(plan.get("artifact_name") or "")
        source = processing / name
        target = incoming / name
        if action == "RECOVER_STALE_LOCK_AND_REQUEUE":
            _remove_stale_lock(lock)
            changed.append("Inbox/.installer.lock")
        if source.is_symlink() or not source.is_file() or target.exists():
            raise RecoveryRejected("processing requeue source/target changed")
        if _sha256(source) != str(plan.get("artifact_sha256") or ""):
            raise RecoveryRejected("processing artifact SHA changed")
        os.replace(source, target)
        if not target.is_file() or target.is_symlink() or _sha256(target) != str(plan.get("artifact_sha256") or ""):
            raise RuntimeError("processing requeue readback failed")
        changed.append(f"Inbox/processing/{name}->Inbox/incoming/{name}")
    elif action == "DEDUPLICATE_INCOMING":
        rows = current["snapshot"]["incoming"]
        canonical_name = sorted(row["name"] for row in rows)[0]
        for row in rows:
            if row["name"] == canonical_name:
                continue
            source = incoming / row["name"]
            if source.is_symlink() or not source.is_file() or _sha256(source) != row["sha256"]:
                raise RecoveryRejected("incoming duplicate changed")
            target = _unique_failed(root, source, f"duplicate-{row['sha256'][:12]}")
            os.replace(source, target)
            changed.append(f"Inbox/incoming/{source.name}->{target.relative_to(root).as_posix()}")
    elif action == "QUARANTINE_STALE_CORRUPT":
        name = str(plan.get("artifact_name") or "")
        source = incoming / name
        if source.is_symlink() or not source.is_file() or _sha256(source) != str(plan.get("artifact_sha256") or ""):
            raise RecoveryRejected("corrupt incoming candidate changed")
        target = _unique_failed(root, source, f"corrupt-{str(plan.get('artifact_sha256') or '')[:12]}")
        os.replace(source, target)
        changed.append(f"Inbox/incoming/{source.name}->{target.relative_to(root).as_posix()}")
    else:
        raise RecoveryRejected(f"unsupported recovery action:{action}")

    after = inspect(root)
    return {
        "schema": "energie_release_ingress_recovery_apply_v2",
        "status": "GREEN",
        "action": action,
        "executed": True,
        "changed": changed,
        "before_fingerprint": expected_fingerprint,
        "after": after,
    }


def execute(root: Path, request: dict[str, Any]) -> dict[str, Any]:
    if request.get("schema") != REQUEST_SCHEMA:
        raise RecoveryRejected("request schema mismatch")
    request_id = str(request.get("request_id") or "")
    if len(request_id) != 32 or any(ch not in "0123456789abcdef" for ch in request_id):
        raise RecoveryRejected("request id invalid")
    operation = str(request.get("operation") or "")
    if operation == "inspect":
        result = inspect(root)
    elif operation == "recover":
        expected = str(request.get("expected_fingerprint") or "")
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise RecoveryRejected("expected fingerprint invalid")
        result = apply(root, expected_fingerprint=expected)
    else:
        raise RecoveryRejected("operation invalid")
    return {"request_id": request_id, "result": result}


def process_pending_request(project_root: Path | str) -> dict[str, Any] | None:
    root = Path(project_root).resolve()
    request_path = Path(project_system_path(root, REQUEST_REL))
    result_path = Path(project_system_path(root, RESULT_REL))
    if request_path.is_symlink():
        raise RecoveryRejected("request path symlink refused")
    if not request_path.is_file():
        return None
    request = _json(request_path)
    request_id = str(request.get("request_id") or "")
    existing = _json(result_path)
    if existing.get("schema") == RESULT_SCHEMA and existing.get("request_id") == request_id and existing.get("status") in {"completed", "rejected", "error"}:
        return existing
    try:
        payload = execute(root, request)
        out = {
            "schema": RESULT_SCHEMA,
            "request_id": request_id,
            "status": "completed",
            "result": payload["result"],
            "finished_at_epoch": time.time(),
        }
    except RecoveryRejected as exc:
        out = {
            "schema": RESULT_SCHEMA,
            "request_id": request_id,
            "status": "rejected",
            "error": f"{type(exc).__name__}:{exc}",
            "finished_at_epoch": time.time(),
        }
    except Exception as exc:
        out = {
            "schema": RESULT_SCHEMA,
            "request_id": request_id,
            "status": "error",
            "error": f"{type(exc).__name__}:{exc}",
            "finished_at_epoch": time.time(),
        }
    _atomic_json(result_path, out)
    return out
