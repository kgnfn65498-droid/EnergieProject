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

    if now is None:
        reconciled_at = datetime.now().astimezone().isoformat()
    elif hasattr(now, "isoformat"):
        reconciled_at = now.isoformat()
    else:
        reconciled_at = str(now)

    updated = replace(
        state,
        observed_profile=observed,
        reconciliation_status="ok" if not drift else "drift",
        last_reconciled_at=reconciled_at,
        drift=tuple(drift),
    )
    save_mode_state(project_root, updated)
    return updated


def observe_operating_mode_runtime(state: ModeState) -> dict[str, Any]:
    return asdict(profile_for(state.effective_mode, state.suspended_features))


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


def operating_mode_tick(project_root: Path | str | None = None) -> dict[str, Any]:
    root = Path(project_root) if project_root is not None else operating_mode_project_root()
    before = load_mode_state(root)
    pending = _pending_command(root)
    state = process_mode_command(root)
    observed = observe_operating_mode_runtime(state)
    state = reconcile_state(root, observed)
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


def operating_mode_worker(stop_event: Any, project_root: Path | str | None = None, interval_seconds: float = 5.0) -> None:
    root = Path(project_root) if project_root is not None else operating_mode_project_root()
    while not stop_event.wait(interval_seconds):
        operating_mode_tick(root)


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
