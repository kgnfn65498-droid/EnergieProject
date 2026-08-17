from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any, Iterable


class Mode(str, Enum):
    USER = "USER"
    DEVELOPMENT = "DEVELOPMENT"
    MAINTENANCE = "MAINTENANCE"


@dataclass(frozen=True)
class ModeProfile:
    release_ingress_enabled: bool
    maintenance_request_processing_enabled: bool
    schedule_enabled: bool
    full_workflow_enabled: bool
    automatic_month_close_enabled: bool


@dataclass(frozen=True)
class ModeState:
    schema_version: int = 1
    base_mode: Mode = Mode.USER
    effective_mode: Mode = Mode.USER
    automatic_switching_enabled: bool = True
    temporary_reason: str = ""
    active_transition_id: str = ""
    suspended_features: tuple[str, ...] = ()
    reconciliation_status: str = "required"
    last_reconciled_at: str = ""
    last_processed_request_id: str = ""
    drift: tuple[str, ...] = ()
    observed_profile: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def initial(cls) -> "ModeState":
        return cls()


_STATE_RELATIVE = Path("Data/03_Systeem/Projectmanager/State/operating_mode_state.json")
_COMMAND_RELATIVE = Path("Data/03_Systeem/Projectmanager/State/operating_mode_command.json")
_SUSPENDABLE_FEATURES = frozenset({"schedule", "full_workflow", "automatic_month_close"})


def state_path(project_root: Path | str) -> Path:
    return Path(project_root) / _STATE_RELATIVE


def command_path(project_root: Path | str) -> Path:
    return Path(project_root) / _COMMAND_RELATIVE


def profile_for(mode: Mode | str, suspended_features: Iterable[str] = frozenset()) -> ModeProfile:
    resolved_mode = Mode(mode)
    suspended = frozenset(str(item) for item in suspended_features)
    unknown = suspended - _SUSPENDABLE_FEATURES
    if unknown:
        raise ValueError(f"Unknown suspended feature(s): {', '.join(sorted(unknown))}")
    if suspended and resolved_mode is not Mode.MAINTENANCE:
        raise ValueError("Temporary feature suspension is only allowed in MAINTENANCE")

    profile = ModeProfile(
        release_ingress_enabled=resolved_mode is Mode.DEVELOPMENT,
        maintenance_request_processing_enabled=resolved_mode is Mode.MAINTENANCE,
        schedule_enabled=True,
        full_workflow_enabled=True,
        automatic_month_close_enabled=True,
    )
    if not suspended:
        return profile
    return replace(
        profile,
        schedule_enabled="schedule" not in suspended,
        full_workflow_enabled="full_workflow" not in suspended,
        automatic_month_close_enabled="automatic_month_close" not in suspended,
    )


def _state_payload(state: ModeState) -> dict[str, Any]:
    payload = asdict(state)
    payload["base_mode"] = state.base_mode.value
    payload["effective_mode"] = state.effective_mode.value
    payload["suspended_features"] = list(state.suspended_features)
    payload["drift"] = list(state.drift)
    return payload


def save_mode_state(project_root: Path | str, state: ModeState) -> None:
    path = state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(
        json.dumps(_state_payload(state), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _migrated_user_state(reason: str) -> ModeState:
    return replace(ModeState.initial(), drift=(reason,))


def load_mode_state(project_root: Path | str) -> ModeState:
    path = state_path(project_root)
    if not path.exists():
        return ModeState.initial()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return _migrated_user_state("legacy_or_invalid_state_migrated")
    if not isinstance(raw, dict):
        return _migrated_user_state("legacy_or_invalid_state_migrated")

    try:
        base_mode = Mode(str(raw.get("base_mode", "")))
        effective_mode = Mode(str(raw.get("effective_mode", "")))
    except ValueError:
        return _migrated_user_state("legacy_or_invalid_state_migrated")

    automatic = raw.get("automatic_switching_enabled", True)
    if not isinstance(automatic, bool):
        return _migrated_user_state("legacy_or_invalid_state_migrated")

    suspended_raw = raw.get("suspended_features", [])
    drift_raw = raw.get("drift", [])
    observed_raw = raw.get("observed_profile", {})
    if not isinstance(suspended_raw, (list, tuple)) or not isinstance(drift_raw, (list, tuple)) or not isinstance(observed_raw, dict):
        return _migrated_user_state("legacy_or_invalid_state_migrated")
    suspended = tuple(str(item) for item in suspended_raw)
    try:
        profile_for(effective_mode, suspended)
    except ValueError:
        return _migrated_user_state("legacy_or_invalid_state_migrated")

    try:
        schema_version = int(raw.get("schema_version", 1))
    except (TypeError, ValueError):
        return _migrated_user_state("legacy_or_invalid_state_migrated")

    return ModeState(
        schema_version=schema_version,
        base_mode=base_mode,
        effective_mode=effective_mode,
        automatic_switching_enabled=automatic,
        temporary_reason=str(raw.get("temporary_reason", "")),
        active_transition_id=str(raw.get("active_transition_id", "")),
        suspended_features=suspended,
        reconciliation_status=str(raw.get("reconciliation_status", "required")),
        last_reconciled_at=str(raw.get("last_reconciled_at", "")),
        last_processed_request_id=str(raw.get("last_processed_request_id", "")),
        drift=tuple(str(item) for item in drift_raw),
        observed_profile=dict(observed_raw),
    )


def format_chat_status(state: ModeState) -> str:
    auto = "AAN" if state.automatic_switching_enabled else "UIT"
    text = f"[MODE] {state.effective_mode.value} · AUTO {auto} · basis {state.base_mode.value}"
    if state.temporary_reason:
        text += f" · {state.temporary_reason}"
    return text


_COMMAND_ACTIONS = frozenset({"set_base", "set_auto", "begin_temporary", "end_temporary", "reconcile"})


@dataclass(frozen=True)
class ModeCommand:
    schema_version: int
    request_id: str
    action: str
    requested_mode: Mode | None = None
    reason: str = ""
    issued_by: str = ""
    enabled: bool | None = None
    transition_id: str = ""
    suspended_features: tuple[str, ...] = ()

    @classmethod
    def from_payload(cls, raw: dict[str, Any]) -> "ModeCommand":
        if not isinstance(raw, dict):
            raise ValueError("Mode command must be a JSON object")
        request_id = str(raw.get("request_id", "")).strip()
        if not request_id:
            raise ValueError("request_id is required")
        action = str(raw.get("action", "")).strip()
        if action not in _COMMAND_ACTIONS:
            raise ValueError(f"Unsupported mode action: {action}")

        requested_mode: Mode | None = None
        if raw.get("requested_mode") not in (None, ""):
            requested_mode = Mode(str(raw["requested_mode"]))

        enabled = raw.get("enabled")
        if enabled is not None and not isinstance(enabled, bool):
            raise ValueError("enabled must be a boolean")

        suspended_raw = raw.get("suspended_features", [])
        if not isinstance(suspended_raw, (list, tuple)):
            raise ValueError("suspended_features must be a list")
        suspended = tuple(str(item) for item in suspended_raw)

        command = cls(
            schema_version=int(raw.get("schema_version", 1)),
            request_id=request_id,
            action=action,
            requested_mode=requested_mode,
            reason=str(raw.get("reason", "")).strip(),
            issued_by=str(raw.get("issued_by", "")).strip(),
            enabled=enabled,
            transition_id=str(raw.get("transition_id", "")).strip(),
            suspended_features=suspended,
        )
        if action in {"set_base", "begin_temporary"} and requested_mode is None:
            raise ValueError(f"requested_mode is required for {action}")
        if action == "set_auto" and enabled is None:
            raise ValueError("enabled is required for set_auto")
        if action == "end_temporary" and not command.transition_id:
            raise ValueError("transition_id is required for end_temporary")
        return command


def _add_drift(state: ModeState, item: str) -> ModeState:
    if item in state.drift:
        return state
    return replace(state, drift=state.drift + (item,))


def set_base_mode(state: ModeState, mode: Mode | str) -> ModeState:
    resolved = Mode(mode)
    if state.active_transition_id:
        return _add_drift(state, "base_mode_change_blocked_active_transition")
    return replace(
        state,
        base_mode=resolved,
        effective_mode=resolved,
        temporary_reason="",
        active_transition_id="",
        suspended_features=(),
    )


def set_automatic_switching(state: ModeState, enabled: bool) -> ModeState:
    return replace(state, automatic_switching_enabled=bool(enabled))


def begin_temporary_mode(
    state: ModeState,
    requested_mode: Mode | str,
    reason: str,
    transition_id: str,
    suspended_features: Iterable[str] = (),
) -> ModeState:
    resolved = Mode(requested_mode)
    if not state.automatic_switching_enabled:
        return _add_drift(state, "automatic_switching_disabled")
    if resolved is Mode.USER:
        return _add_drift(state, "temporary_user_mode_not_allowed")
    if not transition_id:
        return _add_drift(state, "temporary_transition_id_required")
    if state.active_transition_id and state.active_transition_id != transition_id:
        return _add_drift(state, "temporary_transition_already_active")

    suspended = tuple(str(item) for item in suspended_features)
    try:
        profile_for(resolved, suspended)
    except ValueError as exc:
        return _add_drift(state, f"invalid_temporary_profile:{exc}")

    return replace(
        state,
        effective_mode=resolved,
        temporary_reason=str(reason).strip(),
        active_transition_id=transition_id,
        suspended_features=suspended,
    )


def end_temporary_mode(state: ModeState, transition_id: str) -> ModeState:
    if not state.active_transition_id or transition_id != state.active_transition_id:
        return _add_drift(state, "temporary_transition_id_mismatch")
    return replace(
        state,
        effective_mode=state.base_mode,
        temporary_reason="",
        active_transition_id="",
        suspended_features=(),
    )


def process_mode_command(project_root: Path | str, now: Any = None) -> ModeState:
    del now
    state = load_mode_state(project_root)
    path = command_path(project_root)
    if not path.exists():
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        command = ModeCommand.from_payload(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        failed = _add_drift(state, f"invalid_mode_command:{type(exc).__name__}")
        save_mode_state(project_root, failed)
        return failed

    if command.request_id == state.last_processed_request_id:
        return state

    updated = state
    if command.action == "set_base":
        updated = set_base_mode(state, command.requested_mode)
    elif command.action == "set_auto":
        updated = set_automatic_switching(state, bool(command.enabled))
    elif command.action == "begin_temporary":
        updated = begin_temporary_mode(
            state,
            command.requested_mode,
            command.reason,
            command.request_id,
            command.suspended_features,
        )
    elif command.action == "end_temporary":
        updated = end_temporary_mode(state, command.transition_id)
    elif command.action == "reconcile":
        updated = state

    updated = replace(
        updated,
        last_processed_request_id=command.request_id,
        reconciliation_status="required",
    )
    save_mode_state(project_root, updated)
    return updated
