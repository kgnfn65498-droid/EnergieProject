from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from operating_modes import (
    ModeState,
    format_chat_status,
    load_mode_state,
    process_mode_command,
    profile_for,
    save_mode_state,
)


def operating_mode_project_root() -> Path:
    from project_paths import find_existing_nas_roots, resolve_nas_roots

    resolved = find_existing_nas_roots()
    if resolved is not None:
        return resolved[1]
    return resolve_nas_roots()[1]


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
    state = process_mode_command(root)
    observed = observe_operating_mode_runtime(state)
    state = reconcile_state(root, observed)
    return operating_mode_snapshot(state)


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
