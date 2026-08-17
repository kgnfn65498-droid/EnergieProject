from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
import json
from pathlib import Path
import threading
from typing import Any

from operating_modes import (
    ModeState,
    command_path,
    format_chat_status,
    load_mode_state,
    process_mode_command,
    profile_for,
    save_mode_state,
)
from release_validation_hold import ReleaseHoldState, load_release_hold


_MODE_HISTORY_LOCK = threading.Lock()


def mode_history_path(project_root: Path | str) -> Path:
    return Path(project_root) / "Inbox/logs/operating_mode_history.jsonl"


def _pending_command(project_root: Path | str) -> dict[str, Any] | None:
    path = command_path(project_root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def _append_mode_history(project_root: Path | str, event: dict[str, Any]) -> None:
    path = mode_history_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n"
    with _MODE_HISTORY_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)


def _reconciled_at(now: Any = None) -> str:
    if now is None:
        return datetime.now().astimezone().isoformat()
    if hasattr(now, "isoformat"):
        return now.isoformat()
    return str(now)


def operating_mode_project_root() -> Path:
    from project_paths import find_existing_nas_roots, resolve_nas_roots

    resolved = find_existing_nas_roots()
    if resolved is not None:
        return resolved[1]
    return resolve_nas_roots()[1]


def recover_startup_mode_state(project_root: Path | str) -> ModeState:
    """Discard stale temporary runtime context while preserving the persistent base mode."""
    state = load_mode_state(project_root)
    stale = bool(
        state.active_transition_id
        or state.temporary_reason
        or state.suspended_features
        or state.effective_mode is not state.base_mode
    )
    if not stale:
        return state

    recovered = replace(
        state,
        effective_mode=state.base_mode,
        temporary_reason="",
        active_transition_id="",
        suspended_features=(),
        reconciliation_status="required",
        observed_profile={},
        drift=("stale_temporary_state_recovered",),
    )
    save_mode_state(project_root, recovered)
    desired = asdict(profile_for(recovered.effective_mode))
    _append_mode_history(project_root, {
        "timestamp": datetime.now().astimezone().isoformat(),
        "request_id": "startup-recovery",
        "issued_by": "operating_mode_runtime",
        "action": "startup_recover_stale_temporary",
        "base_mode": recovered.base_mode.value,
        "from_effective_mode": state.effective_mode.value,
        "to_effective_mode": recovered.effective_mode.value,
        "reason": state.temporary_reason or "stale temporary mode after startup",
        "desired_profile": desired,
        "observed_profile": {},
        "reconciliation_status": "required",
    })
    return recovered


def reconcile_state(project_root: Path | str, observed_profile: dict[str, Any], now: Any = None) -> ModeState:
    """Pure profile reconciliation retained for unit tests and non-live callers."""
    state = load_mode_state(project_root)
    desired = asdict(profile_for(state.effective_mode, state.suspended_features))
    observed = dict(observed_profile)
    drift: list[str] = []
    for key, expected in desired.items():
        if key not in observed:
            drift.append(f"{key}: missing")
        elif observed[key] != expected:
            drift.append(f"{key}: expected={expected!r} observed={observed[key]!r}")
    for key in observed:
        if key not in desired:
            drift.append(f"{key}: unexpected")

    updated = replace(
        state,
        observed_profile=observed,
        reconciliation_status="ok" if not drift else "drift",
        last_reconciled_at=_reconciled_at(now),
        drift=tuple(drift),
    )
    save_mode_state(project_root, updated)
    return updated


def observe_operating_mode_runtime(state: ModeState) -> dict[str, Any]:
    """Legacy desired-profile observer for non-live tests only."""
    return asdict(profile_for(state.effective_mode, state.suspended_features))


def _copy_workflow_active(app_module: Any) -> dict[str, Any]:
    active = getattr(app_module, "WORKFLOW_ACTIVE", {})
    lock = getattr(app_module, "WORKFLOW_LOCK_META", None)
    if lock is None:
        return dict(active) if isinstance(active, dict) else {}
    try:
        with lock:
            return dict(active) if isinstance(active, dict) else {}
    except Exception:
        return dict(active) if isinstance(active, dict) else {}


def _fallback_runtime_probe(app_module: Any) -> dict[str, Any]:
    workflow_lock = getattr(app_module, "WORKFLOW_LOCK", None)
    if workflow_lock is None or not hasattr(workflow_lock, "locked"):
        raise RuntimeError("workflow lock unavailable")

    load_state = getattr(app_module, "load_state", None)
    if not callable(load_state):
        raise RuntimeError("runtime state unavailable")
    runtime_state = load_state()
    if not isinstance(runtime_state, dict):
        raise RuntimeError("runtime state invalid")

    options_loader = getattr(getattr(app_module, "Options", None), "load", None)
    if not callable(options_loader):
        raise RuntimeError("options runtime unavailable")
    options = options_loader()

    processing_root = getattr(app_module, "NAS_RELEASE_PROCESSING", None)
    if processing_root is None:
        release_processing: list[str] = []
    else:
        processing_path = Path(processing_root)
        release_processing = sorted(path.name for path in processing_path.glob("*.zip")) if processing_path.exists() else []

    return {
        "workflow_running": bool(workflow_lock.locked()),
        "workflow_active": _copy_workflow_active(app_module),
        "cancel_requested": bool(runtime_state.get("cancel_requested")),
        "run_on_start_effective": bool(getattr(options, "run_on_start", False)),
        "schedule_effective": bool(getattr(options, "schedule_enabled", False)),
        "full_workflow_effective": bool(getattr(options, "full_workflow_enabled", False)),
        "automatic_month_close_effective": bool(getattr(options, "automatic_month_close_enabled", False)),
        "release_processing": release_processing,
    }


def observe_measured_runtime(
    app_module: Any,
    project_root: Path | str,
    state: ModeState,
    hold: ReleaseHoldState,
) -> dict[str, Any]:
    """Measure independent live runtime signals; never derive them from the desired profile."""
    del project_root, state, hold
    probe = getattr(app_module, "operating_runtime_probe", None)
    raw = probe() if callable(probe) else _fallback_runtime_probe(app_module)
    if not isinstance(raw, dict):
        raise RuntimeError("runtime probe returned non-object")

    required = (
        "workflow_running",
        "workflow_active",
        "cancel_requested",
        "run_on_start_effective",
        "schedule_effective",
        "full_workflow_effective",
        "automatic_month_close_effective",
        "release_processing",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise RuntimeError("runtime probe missing: " + ",".join(missing))
    if not isinstance(raw.get("workflow_active"), dict):
        raise RuntimeError("workflow_active must be object")
    if not isinstance(raw.get("release_processing"), (list, tuple)):
        raise RuntimeError("release_processing must be list")

    return {
        "workflow_running": bool(raw["workflow_running"]),
        "workflow_active": dict(raw["workflow_active"]),
        "cancel_requested": bool(raw["cancel_requested"]),
        "run_on_start_effective": bool(raw["run_on_start_effective"]),
        "schedule_effective": bool(raw["schedule_effective"]),
        "full_workflow_effective": bool(raw["full_workflow_effective"]),
        "automatic_month_close_effective": bool(raw["automatic_month_close_effective"]),
        "release_processing": [str(item) for item in raw["release_processing"]],
    }


def _request_controlled_cancellation(app_module: Any) -> bool:
    update_state = getattr(app_module, "update_state", None)
    if not callable(update_state):
        return False
    try:
        update_state(
            cancel_requested=True,
            workflow_cancel_reason="release_validation_hold_drift",
        )
        return True
    except Exception:
        return False


def reconcile_measured_runtime(
    project_root: Path | str,
    app_module: Any,
    now: Any = None,
) -> ModeState:
    """Reconcile against measured runtime. Probe failure is fail-closed and never OK."""
    root = Path(project_root)
    state = load_mode_state(root)
    hold = load_release_hold(root, str(app_module.APP_VERSION))
    reconciled_at = _reconciled_at(now)

    try:
        observed = observe_measured_runtime(app_module, root, state, hold)
    except Exception as exc:
        updated = replace(
            state,
            observed_profile={},
            reconciliation_status="required",
            last_reconciled_at=reconciled_at,
            drift=(f"runtime_probe_unavailable:{type(exc).__name__}",),
        )
        save_mode_state(root, updated)
        return updated

    drift: list[str] = []
    if hold.active:
        if observed["workflow_running"]:
            drift.append("workflow_running_during_release_hold")
        if observed["run_on_start_effective"]:
            drift.append("run_on_start_enabled_during_release_hold")
        if observed["schedule_effective"]:
            drift.append("schedule_enabled_during_release_hold")
        if observed["full_workflow_effective"]:
            drift.append("full_workflow_enabled_during_release_hold")
        if observed["automatic_month_close_effective"]:
            drift.append("automatic_month_close_enabled_during_release_hold")
    else:
        desired = profile_for(state.effective_mode, state.suspended_features)
        if observed["schedule_effective"] != desired.schedule_enabled:
            drift.append(
                f"schedule_effective: expected={desired.schedule_enabled!r} observed={observed['schedule_effective']!r}"
            )
        if observed["full_workflow_effective"] != desired.full_workflow_enabled:
            drift.append(
                f"full_workflow_effective: expected={desired.full_workflow_enabled!r} observed={observed['full_workflow_effective']!r}"
            )
        if observed["automatic_month_close_effective"] != desired.automatic_month_close_enabled:
            drift.append(
                "automatic_month_close_effective: "
                f"expected={desired.automatic_month_close_enabled!r} observed={observed['automatic_month_close_effective']!r}"
            )

    if hold.active and observed["workflow_running"]:
        if not _request_controlled_cancellation(app_module):
            drift.append("controlled_cancellation_request_failed")

    updated = replace(
        state,
        observed_profile=observed,
        reconciliation_status="ok" if not drift else "drift",
        last_reconciled_at=reconciled_at,
        drift=tuple(drift),
    )
    save_mode_state(root, updated)
    return updated


def operating_mode_snapshot(state: ModeState) -> dict[str, Any]:
    desired = asdict(profile_for(state.effective_mode, state.suspended_features))
    return {
        "base_mode": state.base_mode.value,
        "effective_mode": state.effective_mode.value,
        "automatic_switching_enabled": state.automatic_switching_enabled,
        "development_session_active": state.development_session_active,
        "temporary_reason": state.temporary_reason,
        "active_transition_id": state.active_transition_id,
        "suspended_features": list(state.suspended_features),
        "reconciliation_status": state.reconciliation_status,
        "last_reconciled_at": state.last_reconciled_at,
        "last_processed_request_id": state.last_processed_request_id,
        "drift": list(state.drift),
        "desired_profile": desired,
        "observed_profile": dict(state.observed_profile),
        "chat_status": format_chat_status(state),
    }


def operating_mode_tick(
    project_root: Path | str | None = None,
    app_module: Any = None,
) -> dict[str, Any]:
    root = Path(project_root) if project_root is not None else operating_mode_project_root()
    before = load_mode_state(root)
    pending = _pending_command(root)
    state = process_mode_command(root)
    if app_module is None:
        observed = observe_operating_mode_runtime(state)
        state = reconcile_state(root, observed)
    else:
        state = reconcile_measured_runtime(root, app_module)
    snapshot = operating_mode_snapshot(state)
    request_id = str((pending or {}).get("request_id") or "")
    if request_id and request_id != before.last_processed_request_id and request_id == state.last_processed_request_id:
        _append_mode_history(root, {
            "timestamp": state.last_reconciled_at or datetime.now().astimezone().isoformat(),
            "request_id": request_id,
            "issued_by": str((pending or {}).get("issued_by") or ""),
            "action": str((pending or {}).get("action") or ""),
            "base_mode": state.base_mode.value,
            "from_effective_mode": before.effective_mode.value,
            "to_effective_mode": state.effective_mode.value,
            "reason": str((pending or {}).get("reason") or ""),
            "desired_profile": snapshot["desired_profile"],
            "observed_profile": snapshot["observed_profile"],
            "reconciliation_status": state.reconciliation_status,
        })
    return snapshot


def operating_mode_worker(
    stop_event: Any,
    project_root: Path | str | None = None,
    app_module: Any = None,
    interval_seconds: float = 5.0,
) -> None:
    root = Path(project_root) if project_root is not None else operating_mode_project_root()
    while not stop_event.wait(interval_seconds):
        operating_mode_tick(root, app_module=app_module)


def effective_options_for_mode(options: Any, state: ModeState) -> Any:
    profile = profile_for(state.effective_mode, state.suspended_features)
    return replace(
        options,
        schedule_enabled=profile.schedule_enabled,
        full_workflow_enabled=profile.full_workflow_enabled,
        automatic_month_close_enabled=profile.automatic_month_close_enabled,
    )


def effective_options_for_runtime(options: Any, state: ModeState, hold: ReleaseHoldState) -> Any:
    """Apply normal mode policy, then fail closed for automatic mutating work while HOLD is active."""
    effective = effective_options_for_mode(options, state)
    if not hold.active:
        return effective
    return replace(
        effective,
        run_on_start=False,
        schedule_enabled=False,
        full_workflow_enabled=False,
        automatic_month_close_enabled=False,
    )


def is_fully_closed_month(month_key: str, now: Any = None) -> bool:
    if now is None:
        now = datetime.now().astimezone()
    year_text, month_text = month_key.split("_", 1)
    year, month = int(year_text), int(month_text)
    if not 1 <= month <= 12:
        raise ValueError(f"Invalid month key: {month_key}")
    return (year, month) < (now.year, now.month)


def install_mode_overrides(app_module: Any, project_root: Path | str) -> None:
    root = Path(project_root)
    if not getattr(app_module.Options, "_operating_mode_wrapper_installed", False):
        raw_loader = app_module.Options.load

        def effective_load(cls):
            del cls
            raw_options = raw_loader()
            state = load_mode_state(root)
            return effective_options_for_mode(raw_options, state)

        app_module.Options.load = classmethod(effective_load)
        app_module.Options._operating_mode_wrapper_installed = True

    if not getattr(app_module, "_operating_mode_close_guard_installed", False):
        raw_execute = app_module.execute_automatic_month_close

        def guarded_execute(options, month_key, *args, **kwargs):
            trigger = kwargs.get("trigger")
            if trigger is None and args:
                trigger = args[0]
            now = datetime.now(app_module.TZ)
            if trigger == "automatic" and not is_fully_closed_month(month_key, now):
                try:
                    app_module.append_audit_event(
                        "automatic_month_close",
                        action="blocked_current_month",
                        status="blocked",
                        details={"month": month_key, "reason": "current_calendar_month"},
                    )
                except Exception:
                    app_module.LOGGER.exception("Audit logging current-month block failed")
                return {
                    "status": "blocked_current_month",
                    "month": month_key,
                    "trigger": trigger,
                }
            return raw_execute(options, month_key, *args, **kwargs)

        app_module.execute_automatic_month_close = guarded_execute
        app_module._operating_mode_close_guard_installed = True


def install_release_hold_guards(app_module: Any, project_root: Path | str) -> None:
    """Install a second, independent safety layer before the scheduler can start."""
    root = Path(project_root)

    if not getattr(app_module.Options, "_release_hold_wrapper_installed", False):
        raw_loader = app_module.Options.load

        def hold_safe_load(cls):
            del cls
            raw_options = raw_loader()
            state = load_mode_state(root)
            hold = load_release_hold(root, str(app_module.APP_VERSION))
            return effective_options_for_runtime(raw_options, state, hold)

        app_module.Options.load = classmethod(hold_safe_load)
        app_module.Options._release_hold_wrapper_installed = True

    if not getattr(app_module, "_release_hold_close_guard_installed", False):
        raw_execute = app_module.execute_automatic_month_close

        def hold_guarded_execute(options, month_key, *args, **kwargs):
            trigger = kwargs.get("trigger")
            if trigger is None and args:
                trigger = args[0]
            hold = load_release_hold(root, str(app_module.APP_VERSION))
            if trigger == "automatic" and hold.active:
                try:
                    app_module.append_audit_event(
                        "automatic_month_close",
                        action="blocked_release_validation_hold",
                        status="blocked",
                        details={
                            "month": month_key,
                            "reason": "release_validation_hold",
                            "release_version": hold.release_version,
                        },
                    )
                except Exception:
                    app_module.LOGGER.exception("Audit logging release-hold block failed")
                return {
                    "status": "blocked_release_validation_hold",
                    "month": month_key,
                    "trigger": trigger,
                    "release_version": hold.release_version,
                }
            return raw_execute(options, month_key, *args, **kwargs)

        app_module.execute_automatic_month_close = hold_guarded_execute
        app_module._release_hold_close_guard_installed = True
