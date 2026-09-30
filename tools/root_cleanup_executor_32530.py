from __future__ import annotations

"""Privileged executor for the 32.5.30 canonical ROOT cleanup contract."""

import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from system_path_contract import project_system_path

REQUEST_SCHEMA = "energie_root_cleanup_request_v1"
RESULT_SCHEMA = "energie_root_cleanup_result_v1"
PLAN_SCHEMA = "energie_root_cleanup_plan_v1"
REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")
STATE_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/State")
QUARANTINE_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Quarantine")
EXPORT_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Exports")


class RootCleanupRejected(ValueError):
    pass


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RootCleanupRejected(f"unsafe JSON path:{path}")
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tree_sha(path: Path) -> str:
    path = Path(path)
    digest = hashlib.sha256()
    if path.is_symlink():
        digest.update(b"SYMLINK\0")
        digest.update(os.readlink(path).encode("utf-8", errors="surrogateescape"))
        return digest.hexdigest()
    if path.is_file():
        digest.update(b"FILE\0")
        digest.update(_sha(path).encode("ascii"))
        return digest.hexdigest()
    if not path.is_dir():
        raise RootCleanupRejected(f"path missing:{path}")
    digest.update(b"DIR\0")
    for item in sorted(path.rglob("*"), key=lambda p: p.relative_to(path).as_posix()):
        rel = item.relative_to(path).as_posix().encode("utf-8", errors="surrogateescape")
        if item.is_symlink():
            digest.update(b"L\0" + rel + b"\0")
            digest.update(os.readlink(item).encode("utf-8", errors="surrogateescape"))
        elif item.is_dir():
            digest.update(b"D\0" + rel + b"\0")
        elif item.is_file():
            digest.update(b"F\0" + rel + b"\0")
            digest.update(_sha(item).encode("ascii"))
    return digest.hexdigest()

def _load_service(root: Path):
    app_root = root / "App/slimmemeterportal_import/rootfs/app"
    pm_root = app_root / "projectmanager_v2"
    if not app_root.is_dir() or not pm_root.is_dir():
        raise RootCleanupRejected("ROOT cleanup active App modules missing")
    for path in (str(app_root), str(pm_root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    try:
        import root_cleanup_32530  # type: ignore
    except Exception as exc:
        raise RootCleanupRejected(f"ROOT cleanup service import failed:{type(exc).__name__}:{exc}") from exc
    return root_cleanup_32530


def _parse_utc(value: Any) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RootCleanupRejected("expires_at invalid") from exc
    if parsed.tzinfo is None:
        raise RootCleanupRejected("expires_at must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _state_path(root: Path, run_id: str) -> Path:
    if not RUN_ID_RE.fullmatch(str(run_id or "")):
        raise RootCleanupRejected("invalid ROOT cleanup run_id")
    return root / STATE_ROOT_REL / f"ROOT_CLEANUP_RUN_{run_id}.json"


def _validate_recovery(root: Path, plan: dict[str, Any], supplied: Any) -> dict[str, Any]:
    required = int(plan.get("recovery_required_count") or 0)
    if required == 0:
        if not isinstance(supplied, dict) or supplied.get("confirmed") is not True:
            raise RootCleanupRejected("ROOT rollback recovery waiver proof missing")
        return dict(supplied)
    if not isinstance(supplied, dict) or supplied.get("confirmed") is not True:
        raise RootCleanupRejected("ROOT recovery proof missing")
    plan_sha = str(plan.get("plan_sha256") or "")
    if str(supplied.get("plan_sha256") or "") != plan_sha:
        raise RootCleanupRejected("ROOT recovery plan mismatch")
    artifact = str(supplied.get("artifact") or "")
    sha = str(supplied.get("sha256") or "")
    size = int(supplied.get("size") or -1)
    expected_name = f"RootCleanup_{plan_sha[:24]}_recovery.zip"
    if artifact != expected_name:
        raise RootCleanupRejected("ROOT recovery artifact name mismatch")
    path = root / EXPORT_ROOT_REL / expected_name
    if path.is_symlink() or not path.is_file():
        raise RootCleanupRejected("ROOT recovery artifact missing/unsafe")
    if path.stat().st_size != size or _sha(path) != sha:
        raise RootCleanupRejected("ROOT recovery artifact identity mismatch")
    return dict(supplied)


def _validate(root: Path, request: dict[str, Any]):
    service = _load_service(root)
    if str(request.get("schema") or "") != REQUEST_SCHEMA:
        raise RootCleanupRejected("ROOT cleanup request schema invalid")
    request_id = str(request.get("request_id") or "").strip().lower()
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise RootCleanupRejected("ROOT cleanup request_id invalid")
    operation = str(request.get("operation") or "").strip()
    if operation not in {"root_apply", "root_restore", "root_finalize"}:
        raise RootCleanupRejected("ROOT cleanup operation invalid")
    version = service._release_version(root)
    if str(request.get("release_version") or "") != version:
        raise RootCleanupRejected("ROOT cleanup release version mismatch")
    service._release_idle(root, version)
    if request.get("explicit_user_approval") is not True:
        raise RootCleanupRejected("ROOT cleanup explicit approval missing")
    if _parse_utc(request.get("expires_at")) <= datetime.now(timezone.utc):
        raise RootCleanupRejected("ROOT cleanup request expired")

    if operation == "root_apply":
        supplied = request.get("plan")
        if not isinstance(supplied, dict) or supplied.get("schema") != PLAN_SCHEMA:
            raise RootCleanupRejected("ROOT cleanup plan missing/invalid")
        current = service.build_root_cleanup_plan(root)
        if current.get("status") != "READY" or int(current.get("review_count") or 0) != 0:
            raise RootCleanupRejected("ROOT cleanup current plan not READY")
        if supplied != current or str(request.get("plan_sha256") or "") != str(current.get("plan_sha256") or ""):
            raise RootCleanupRejected("ROOT cleanup plan changed")
        recovery = _validate_recovery(root, current, request.get("recovery"))
        return request_id, operation, current, recovery, service

    run_id = str(request.get("run_id") or "").strip()
    state = _json(_state_path(root, run_id))
    if state.get("schema") != "energie_root_cleanup_run_v1" or state.get("run_id") != run_id:
        raise RootCleanupRejected("ROOT cleanup run state missing/invalid")
    if state.get("release_version") != version:
        raise RootCleanupRejected("ROOT cleanup run belongs to another release")
    return request_id, operation, state, None, service


def _same_filesystem(root: Path, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.parent.stat().st_dev != root.stat().st_dev:
        raise RootCleanupRejected(f"cross-filesystem target refused:{path}")


def _atomic_path(root: Path) -> Path:
    return Path(project_system_path(root, "Inbox/atomic_app_swap_state.json"))


def _apply(root: Path, request_id: str, plan: dict[str, Any], recovery: dict[str, Any], service) -> dict[str, Any]:
    run_id = f"RootCleanup_{request_id}"
    quarantine = root / QUARANTINE_ROOT_REL / run_id
    original = quarantine / "original"
    if quarantine.exists() or quarantine.is_symlink():
        raise RootCleanupRejected("ROOT cleanup quarantine run already exists")
    original.mkdir(parents=True, exist_ok=False)
    _same_filesystem(root, quarantine)

    journal: list[dict[str, Any]] = []
    atomic_path = _atomic_path(root)
    atomic_before = _json(atomic_path)
    atomic_after = dict(atomic_before)
    atomic_changed = False
    try:
        for action in plan.get("actions") or []:
            kind = str(action.get("kind") or "")
            source_rel = str(action.get("source") or "")
            source = root / source_rel
            expected_hash = str(action.get("tree_sha256") or "")
            if source.is_symlink() or not source.exists():
                raise RootCleanupRejected(f"ROOT cleanup source missing/unsafe:{source_rel}")
            if _tree_sha(source) != expected_hash:
                raise RootCleanupRejected(f"ROOT cleanup source changed:{source_rel}")

            if kind in {"migrate_rollback", "migrate_legacy_clearup"}:
                target_rel = str(action.get("target") or "")
                target = root / target_rel
                if target.exists() or target.is_symlink():
                    raise RootCleanupRejected(f"ROOT cleanup target exists:{target_rel}")
                _same_filesystem(root, target)
                before = source.lstat()
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, target)
                after = target.lstat()
                if os.path.lexists(source) or not os.path.lexists(target):
                    raise RuntimeError(f"ROOT cleanup migration readback failed:{source_rel}")
                if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
                    raise RuntimeError(f"ROOT cleanup migration identity mismatch:{source_rel}")
                journal.append({**action, "target": target_rel})
                if kind == "migrate_rollback" and str(atomic_before.get("rollback_path") or "").strip() == source_rel:
                    atomic_after["rollback_path"] = target_rel
                    atomic_changed = True
            elif kind == "quarantine":
                target = original / source_rel
                if target.exists() or target.is_symlink():
                    raise RootCleanupRejected(f"ROOT quarantine target exists:{source_rel}")
                _same_filesystem(root, target)
                before = source.lstat()
                target.parent.mkdir(parents=True, exist_ok=True)
                os.replace(source, target)
                after = target.lstat()
                if os.path.lexists(source) or not os.path.lexists(target):
                    raise RuntimeError(f"ROOT quarantine readback failed:{source_rel}")
                if (before.st_dev, before.st_ino, before.st_size) != (after.st_dev, after.st_ino, after.st_size):
                    raise RuntimeError(f"ROOT quarantine identity mismatch:{source_rel}")
                journal.append({**action, "target": target.relative_to(root).as_posix()})
            else:
                raise RootCleanupRejected(f"unsupported ROOT cleanup action:{kind}")

        if atomic_changed:
            _atomic_json(atomic_path, atomic_after)
            readback = _json(atomic_path)
            if str(readback.get("rollback_path") or "") != str(atomic_after.get("rollback_path") or ""):
                raise RuntimeError("atomic rollback_path migration readback failed")

        post = service.build_root_cleanup_plan(root)
        if post.get("status") != "READY" or int(post.get("action_count") or 0) != 0 or int(post.get("review_count") or 0) != 0:
            raise RuntimeError("ROOT cleanup post-apply inventory is not clean")

        state = {
            "schema": "energie_root_cleanup_run_v1",
            "status": "APPLIED",
            "run_id": run_id,
            "request_id": request_id,
            "release_version": plan["release_version"],
            "plan_sha256": plan["plan_sha256"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "moves": journal,
            "quarantine_root": quarantine.relative_to(root).as_posix(),
            "atomic_rollback_path_changed": atomic_changed,
            "atomic_rollback_path_before": atomic_before.get("rollback_path"),
            "atomic_rollback_path_after": atomic_after.get("rollback_path") if atomic_changed else atomic_before.get("rollback_path"),
            "recovery": recovery,
            "delete_performed": False,
            "post_apply_inventory": {
                "status": post.get("status"),
                "action_count": post.get("action_count"),
                "review_count": post.get("review_count"),
                "retained_rollback_versions": post.get("retained_rollback_versions"),
            },
        }
        _atomic_json(_state_path(root, run_id), state)
        _atomic_json(quarantine / "manifest.json", state)
        return {
            "status": "GREEN",
            "run_id": run_id,
            "moved_count": len(journal),
            "delete_performed": False,
            "atomic_rollback_path_changed": atomic_changed,
            "root_clean": True,
        }
    except Exception:
        if atomic_changed:
            try:
                _atomic_json(atomic_path, atomic_before)
            except Exception:
                pass
        for entry in reversed(journal):
            try:
                source = root / str(entry.get("source") or "")
                target = root / str(entry.get("target") or "")
                if not os.path.lexists(source) and os.path.lexists(target):
                    source.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(target, source)
            except OSError:
                pass
        if quarantine.exists() and not quarantine.is_symlink():
            shutil.rmtree(quarantine, ignore_errors=True)
        raise


def _restore(root: Path, state: dict[str, Any], service) -> dict[str, Any]:
    if state.get("status") != "APPLIED" or state.get("delete_performed") is not False:
        raise RootCleanupRejected("ROOT restore requires reversible APPLIED state")
    moves = list(state.get("moves") or [])
    for entry in reversed(moves):
        source = root / str(entry.get("source") or "")
        target = root / str(entry.get("target") or "")
        if source.exists() or source.is_symlink():
            raise RootCleanupRejected(f"ROOT restore source conflict:{entry.get('source')}")
        if target.is_symlink() or not target.exists():
            raise RootCleanupRejected(f"ROOT restore target missing/unsafe:{entry.get('target')}")
        if _tree_sha(target) != str(entry.get("tree_sha256") or ""):
            raise RootCleanupRejected(f"ROOT restore hash mismatch:{entry.get('source')}")

    restored: list[dict[str, Any]] = []
    try:
        for entry in reversed(moves):
            source = root / str(entry["source"])
            target = root / str(entry["target"])
            source.parent.mkdir(parents=True, exist_ok=True)
            os.replace(target, source)
            restored.append(entry)
        if state.get("atomic_rollback_path_changed") is True:
            atomic = _json(_atomic_path(root))
            atomic["rollback_path"] = state.get("atomic_rollback_path_before")
            _atomic_json(_atomic_path(root), atomic)
        quarantine = root / str(state.get("quarantine_root") or "")
        if quarantine.exists() and not quarantine.is_symlink():
            shutil.rmtree(quarantine)
        updated = dict(state)
        updated["status"] = "RESTORED"
        updated["restored_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(_state_path(root, state["run_id"]), updated)
        return {"status": "GREEN", "run_id": state["run_id"], "restored_count": len(restored), "delete_performed": False}
    except Exception:
        for entry in restored:
            try:
                source = root / str(entry["source"])
                target = root / str(entry["target"])
                if source.exists() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, target)
            except OSError:
                pass
        raise


def _finalize(root: Path, state: dict[str, Any], service) -> dict[str, Any]:
    if state.get("status") != "APPLIED" or state.get("delete_performed") is not False:
        raise RootCleanupRejected("ROOT finalize requires APPLIED state")
    recovery = state.get("recovery") if isinstance(state.get("recovery"), dict) else {}
    if recovery.get("required") is True:
        if recovery.get("confirmed") is not True:
            raise RootCleanupRejected("ROOT finalize recovery not externally confirmed")
        plan_sha = str(state.get("plan_sha256") or "")
        artifact = root / EXPORT_ROOT_REL / f"RootCleanup_{plan_sha[:24]}_recovery.zip"
        if artifact.is_symlink() or not artifact.is_file():
            raise RootCleanupRejected("ROOT finalize recovery artifact missing")
        if artifact.stat().st_size != int(recovery.get("size") or -1) or _sha(artifact) != str(recovery.get("sha256") or ""):
            raise RootCleanupRejected("ROOT finalize recovery artifact identity mismatch")

    quarantine = root / str(state.get("quarantine_root") or "")
    quarantine_moves = [entry for entry in state.get("moves") or [] if entry.get("kind") == "quarantine"]
    for entry in quarantine_moves:
        target = root / str(entry.get("target") or "")
        if target.is_symlink() or not target.exists():
            raise RootCleanupRejected(f"ROOT finalize quarantine item missing:{entry.get('source')}")
        if _tree_sha(target) != str(entry.get("tree_sha256") or ""):
            raise RootCleanupRejected(f"ROOT finalize quarantine hash mismatch:{entry.get('source')}")

    if quarantine.exists():
        if quarantine.is_symlink() or not quarantine.is_dir():
            raise RootCleanupRejected("ROOT finalize quarantine root unsafe")
        shutil.rmtree(quarantine)
    if quarantine.exists():
        raise RuntimeError("ROOT finalize delete readback failed")

    post = service.build_root_cleanup_plan(root)
    if post.get("status") != "READY" or int(post.get("action_count") or 0) != 0 or int(post.get("review_count") or 0) != 0:
        raise RootCleanupRejected("ROOT finalize post-delete inventory not clean")

    updated = dict(state)
    updated["status"] = "COMPLETE"
    updated["delete_performed"] = True
    updated["finalized_at"] = datetime.now(timezone.utc).isoformat()
    updated["deleted_quarantine_items"] = len(quarantine_moves)
    _atomic_json(_state_path(root, state["run_id"]), updated)
    return {
        "status": "GREEN",
        "run_id": state["run_id"],
        "deleted_count": len(quarantine_moves),
        "delete_performed": True,
        "root_clean": True,
    }


def execute(root: Path | str, request: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    root = Path(root).resolve()
    request_id, operation, payload, recovery, service = _validate(root, request)
    if operation == "root_apply":
        return request_id, _apply(root, request_id, payload, recovery, service)
    if operation == "root_restore":
        return request_id, _restore(root, payload, service)
    return request_id, _finalize(root, payload, service)
