from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import secrets
import threading
from typing import Any

from operating_modes import (
    Mode,
    ModeState,
    begin_temporary_mode,
    end_temporary_mode,
    load_mode_state,
    save_mode_state,
)

_SESSION_RELATIVE = Path("Inbox/operating_mode/crash_recovery_session.json")
_ALLOWED_OUTCOMES = frozenset({"pass", "failed_safe", "unsafe"})
_ALLOWED_OPERATION_CLASSES = frozenset({"backup_verify", "mutating_maintenance"})
_AUTOMATIC_MUTATION_SUSPENSIONS = ("schedule", "full_workflow", "automatic_month_close")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def crash_recovery_session_path(project_root: Path | str) -> Path:
    return Path(project_root) / _SESSION_RELATIVE


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}.{secrets.token_hex(3)}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _load_session(project_root: Path | str) -> dict[str, Any] | None:
    path = crash_recovery_session_path(project_root)
    if not path.is_file():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or int(raw.get("schema_version") or 0) != 1:
        raise RuntimeError("invalid crash recovery mode session")
    return raw


def begin_crash_recovery_mode_session(
    project_root: Path | str,
    operation_class: str = "backup_verify",
) -> dict[str, Any]:
    root = Path(project_root)
    operation = str(operation_class).strip()
    if operation not in _ALLOWED_OPERATION_CLASSES:
        raise ValueError(f"unsupported crash recovery operation class: {operation}")

    state = load_mode_state(root)
    existing = _load_session(root)
    if (
        existing
        and existing.get("phase") in {"starting", "running", "waiting_cleanup", "unsafe_hold"}
        and state.active_transition_id == str(existing.get("transition_id") or "")
        and state.effective_mode is Mode.MAINTENANCE
    ):
        raise RuntimeError("crash recovery mode session already active")

    if state.active_transition_id:
        raise RuntimeError(
            f"conflicting temporary transition active: {state.active_transition_id}"
        )

    transition_id = f"crash-recovery-{secrets.token_hex(8)}"
    started_at = _now_iso()
    session = {
        "schema_version": 1,
        "session_id": transition_id,
        "transition_id": transition_id,
        "original_base_mode": state.base_mode.value,
        "original_effective_mode": state.effective_mode.value,
        "original_development_session_active": bool(state.development_session_active),
        "operation_class": operation,
        "phase": "starting",
        "outcome": "",
        "reason": "",
        "cleanup_request_id": "",
        "started_at": started_at,
        "completed_at": "",
    }
    _atomic_write_json(crash_recovery_session_path(root), session)

    updated = begin_temporary_mode(
        state,
        Mode.MAINTENANCE,
        "crash_recovery",
        transition_id,
        suspended_features=_AUTOMATIC_MUTATION_SUSPENSIONS,
    )
    save_mode_state(root, updated)
    if (
        updated.effective_mode is not Mode.MAINTENANCE
        or updated.active_transition_id != transition_id
    ):
        session.update(
            phase="failed_to_start",
            outcome="failed_safe",
            reason="temporary MAINTENANCE transition was refused",
            completed_at=_now_iso(),
        )
        _atomic_write_json(crash_recovery_session_path(root), session)
        raise RuntimeError("temporary MAINTENANCE transition was refused")

    session["phase"] = "running"
    _atomic_write_json(crash_recovery_session_path(root), session)
    return dict(session)


def mark_crash_recovery_cleanup_pending(
    project_root: Path | str,
    request_id: str,
) -> dict[str, Any]:
    root = Path(project_root)
    resolved_request = str(request_id).strip()
    if not resolved_request:
        raise ValueError("cleanup request id is required")

    session = _load_session(root)
    if not session or session.get("phase") != "running":
        raise RuntimeError("no running crash recovery cleanup session")
    if str(session.get("operation_class") or "") != "mutating_maintenance":
        raise RuntimeError("cleanup pending is only valid for mutating maintenance")

    state = load_mode_state(root)
    transition_id = str(session.get("transition_id") or "")
    if state.effective_mode is not Mode.MAINTENANCE or state.active_transition_id != transition_id:
        raise RuntimeError("cleanup session is not held in MAINTENANCE")

    session.update(
        phase="waiting_cleanup",
        cleanup_request_id=resolved_request,
        reason="watcher cleanup pending",
        completed_at="",
    )
    _atomic_write_json(crash_recovery_session_path(root), session)
    return dict(session)


def finish_crash_recovery_mode_session(
    project_root: Path | str,
    *,
    outcome: str,
    reason: str = "",
) -> ModeState:
    root = Path(project_root)
    resolved_outcome = str(outcome).strip()
    if resolved_outcome not in _ALLOWED_OUTCOMES:
        raise ValueError(f"unsupported crash recovery outcome: {resolved_outcome}")

    session = _load_session(root)
    if not session:
        raise RuntimeError("no crash recovery mode session exists")

    state = load_mode_state(root)
    transition_id = str(session.get("transition_id") or "")
    if not transition_id:
        raise RuntimeError("crash recovery mode session has no transition id")

    if resolved_outcome == "unsafe":
        if state.effective_mode is not Mode.MAINTENANCE or state.active_transition_id != transition_id:
            raise RuntimeError("unsafe crash recovery state is not held in MAINTENANCE")
        session.update(
            phase="unsafe_hold",
            outcome="unsafe",
            reason=str(reason),
            completed_at="",
        )
        _atomic_write_json(crash_recovery_session_path(root), session)
        return state

    if state.active_transition_id == transition_id:
        updated = end_temporary_mode(state, transition_id)
        save_mode_state(root, updated)
    elif not state.active_transition_id and state.effective_mode is state.base_mode:
        updated = state
    else:
        raise RuntimeError("crash recovery temporary transition no longer matches mode state")

    original_base = Mode(str(session.get("original_base_mode") or ""))
    if updated.base_mode is not original_base or updated.effective_mode is not original_base:
        raise RuntimeError("crash recovery did not restore the original base mode")
    expected_dev = bool(session.get("original_development_session_active"))
    if updated.development_session_active is not expected_dev:
        raise RuntimeError("crash recovery changed development session state")

    session.update(
        phase="completed",
        outcome=resolved_outcome,
        reason=str(reason),
        completed_at=_now_iso(),
    )
    _atomic_write_json(crash_recovery_session_path(root), session)
    return updated


def recover_crash_recovery_mode_session(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root)
    session = _load_session(root)
    if not session or session.get("phase") == "completed":
        return {"status": "none", "preserve_temporary": False, "outcome": ""}

    operation_class = str(session.get("operation_class") or "backup_verify")
    phase = str(session.get("phase") or "")
    if phase == "waiting_cleanup":
        return {"status": "waiting_cleanup", "preserve_temporary": True, "outcome": "pending"}
    if phase == "unsafe_hold" or operation_class == "mutating_maintenance":
        if phase != "unsafe_hold":
            finish_crash_recovery_mode_session(
                root,
                outcome="unsafe",
                reason="mutating maintenance interrupted by restart",
            )
        return {"status": "unsafe_hold", "preserve_temporary": True, "outcome": "unsafe"}

    finish_crash_recovery_mode_session(
        root,
        outcome="failed_safe",
        reason="backup verification interrupted by restart",
    )
    return {"status": "recovered", "preserve_temporary": False, "outcome": "failed_safe"}


def _result_outcome(function_name: str, result: Any) -> tuple[str, str]:
    if not isinstance(result, dict):
        return "failed_safe", "Crash Recovery returned no structured result"
    if result.get("source_project_modified") is True:
        return "unsafe", str(result.get("error") or "source project modified during Crash Recovery")

    status = str(result.get("status") or "").strip().lower()
    success_statuses = {
        "run_complete_crash_recovery": {"verified"},
        "run_complete_restore_staging": {"staged"},
        "run_complete_crash_recovery_export": {"ready_for_download"},
    }
    if status in success_statuses.get(function_name, set()):
        return "pass", ""
    return "failed_safe", str(result.get("error") or f"Crash Recovery status={status or 'unknown'}")


def _cleanup_result_path(app_module: Any, project_root: Path) -> Path:
    configured = getattr(app_module, "CRASH_RECOVERY_CLEANUP_RESULT_PATH", None)
    if configured is not None:
        return Path(configured)
    return project_root / "Inbox/crash_recovery_cleanup_result.json"


def _matching_cleanup_result(app_module: Any, project_root: Path, request_id: str) -> dict[str, Any] | None:
    path = _cleanup_result_path(app_module, project_root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or str(raw.get("request_id") or "") != request_id:
        return None
    return raw


def reconcile_pending_crash_recovery_cleanup(
    app_module: Any,
    project_root: Path | str,
) -> dict[str, Any]:
    root = Path(project_root)
    session = _load_session(root)
    if not session or session.get("phase") != "waiting_cleanup":
        return {"status": "none", "outcome": ""}

    request_id = str(session.get("cleanup_request_id") or "").strip()
    if not request_id:
        finish_crash_recovery_mode_session(
            root,
            outcome="unsafe",
            reason="pending cleanup session has no request id",
        )
        return {"status": "unsafe_hold", "outcome": "unsafe"}

    result = _matching_cleanup_result(app_module, root, request_id)
    if result is None:
        return {"status": "pending", "outcome": "pending", "request_id": request_id}

    if str(result.get("status") or "").strip().lower() == "ok":
        finish_crash_recovery_mode_session(
            root,
            outcome="pass",
            reason="watcher cleanup completed",
        )
        return {"status": "completed", "outcome": "pass", "request_id": request_id}

    reason = str(result.get("error") or "watcher cleanup was not fully successful")
    finish_crash_recovery_mode_session(root, outcome="unsafe", reason=reason)
    return {"status": "unsafe_hold", "outcome": "unsafe", "request_id": request_id, "reason": reason}


def crash_recovery_mode_worker(
    stop_event: Any,
    app_module: Any,
    project_root: Path | str,
    interval_seconds: float = 5.0,
) -> None:
    root = Path(project_root)
    while not stop_event.wait(interval_seconds):
        try:
            reconcile_pending_crash_recovery_cleanup(app_module, root)
        except Exception:
            logger = getattr(app_module, "LOGGER", None)
            if logger is not None and callable(getattr(logger, "exception", None)):
                logger.exception("Crash Recovery cleanup mode reconciliation failed")


def install_crash_recovery_mode_integration(app_module: Any, project_root: Path | str) -> None:
    root = Path(project_root)
    marker = "_v32319_crash_recovery_mode_integration_installed"
    if getattr(app_module, marker, False):
        return

    names = (
        "run_complete_crash_recovery",
        "run_complete_restore_staging",
        "run_complete_crash_recovery_export",
    )
    raw_functions: dict[str, Any] = {}
    for name in names:
        raw = getattr(app_module, name, None)
        if not callable(raw):
            raise RuntimeError(f"Crash Recovery callable ontbreekt: {name}")
        raw_functions[name] = raw

    raw_cleanup = getattr(app_module, "_cleanup_completed_export", None)
    context = threading.local()

    def make_wrapper(function_name: str, raw: Any):
        def wrapped(*args, **kwargs):
            depth = int(getattr(context, "depth", 0))
            if depth > 0:
                return raw(*args, **kwargs)

            begin_crash_recovery_mode_session(root, operation_class="backup_verify")
            context.depth = depth + 1
            try:
                result = raw(*args, **kwargs)
                outcome, reason = _result_outcome(function_name, result)
                finish_crash_recovery_mode_session(root, outcome=outcome, reason=reason)
                return result
            except Exception as exc:
                state = load_mode_state(root)
                session = _load_session(root)
                if (
                    session
                    and session.get("phase") == "running"
                    and state.active_transition_id == str(session.get("transition_id") or "")
                ):
                    finish_crash_recovery_mode_session(
                        root,
                        outcome="failed_safe",
                        reason=f"{type(exc).__name__}: {exc}",
                    )
                raise
            finally:
                context.depth = depth

        wrapped.__name__ = getattr(raw, "__name__", function_name)
        wrapped.__doc__ = getattr(raw, "__doc__", None)
        return wrapped

    def cleanup_wrapper(*args, **kwargs):
        depth = int(getattr(context, "depth", 0))
        if depth > 0:
            return raw_cleanup(*args, **kwargs)

        begin_crash_recovery_mode_session(root, operation_class="mutating_maintenance")
        context.depth = depth + 1
        try:
            result = raw_cleanup(*args, **kwargs)
            if isinstance(result, dict) and str(result.get("status") or "") == "pending_watcher":
                request_id = str(result.get("request_id") or "").strip()
                if request_id:
                    mark_crash_recovery_cleanup_pending(root, request_id)
                    return result
            reason = (
                str(result.get("warnings") or result.get("error") or "cleanup request was not queued")
                if isinstance(result, dict)
                else "cleanup returned no structured result"
            )
            finish_crash_recovery_mode_session(root, outcome="failed_safe", reason=reason)
            return result
        except Exception as exc:
            state = load_mode_state(root)
            session = _load_session(root)
            if (
                session
                and session.get("phase") == "running"
                and state.active_transition_id == str(session.get("transition_id") or "")
            ):
                finish_crash_recovery_mode_session(
                    root,
                    outcome="failed_safe",
                    reason=f"{type(exc).__name__}: {exc}",
                )
            raise
        finally:
            context.depth = depth

    for name, raw in raw_functions.items():
        setattr(app_module, name, make_wrapper(name, raw))
    if callable(raw_cleanup):
        cleanup_wrapper.__name__ = getattr(raw_cleanup, "__name__", "_cleanup_completed_export")
        cleanup_wrapper.__doc__ = getattr(raw_cleanup, "__doc__", None)
        setattr(app_module, "_cleanup_completed_export", cleanup_wrapper)
    setattr(app_module, marker, True)
