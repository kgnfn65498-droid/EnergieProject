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
        and existing.get("phase") in {"starting", "running", "unsafe_hold"}
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
        "started_at": started_at,
        "completed_at": "",
    }
    _atomic_write_json(crash_recovery_session_path(root), session)

    updated = begin_temporary_mode(
        state,
        Mode.MAINTENANCE,
        "crash_recovery",
        transition_id,
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


def install_crash_recovery_mode_integration(app_module: Any, project_root: Path | str) -> None:
    root = Path(project_root)
    marker = "_v32316_crash_recovery_mode_integration_installed"
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

    for name, raw in raw_functions.items():
        setattr(app_module, name, make_wrapper(name, raw))
    setattr(app_module, marker, True)
