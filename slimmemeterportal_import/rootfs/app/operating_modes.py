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

    return ModeState(
        schema_version=int(raw.get("schema_version", 1)),
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
