from __future__ import annotations
from system_path_contract import project_system_path

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any, Iterable
from transition_state_io import read_transition_state


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
    development_session_active: bool = False
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


_SUSPENDABLE_FEATURES = frozenset({"schedule", "full_workflow", "automatic_month_close"})


def state_path(project_root: Path | str) -> Path:
    return project_system_path(Path(project_root), 'Inbox/operating_mode/operating_mode_state.json')


def command_path(project_root: Path | str) -> Path:
    return project_system_path(Path(project_root), 'Inbox/operating_mode/operating_mode_command.json')


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

    development_session = raw.get("development_session_active", base_mode is Mode.DEVELOPMENT)
    if not isinstance(development_session, bool):
        return _migrated_user_state("legacy_or_invalid_state_migrated")
    if development_session and base_mode is not Mode.DEVELOPMENT:
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
        development_session_active=development_session,
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
    if state.development_session_active:
        text += " · ontwikkelsessie actief"
    if state.temporary_reason:
        text += f" · {state.temporary_reason}"
    return text


_COMMAND_ACTIONS = frozenset({
    "set_base",
    "set_auto",
    "begin_temporary",
    "end_temporary",
    "reconcile",
    "close_development_session",
    "transition_owned_temporary_maintenance",
})


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
    confirmed_by_user: bool = False
    transition_fence: dict[str, str] = field(default_factory=dict)

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

        confirmed_by_user = raw.get("confirmed_by_user", False)
        if not isinstance(confirmed_by_user, bool):
            raise ValueError("confirmed_by_user must be a boolean")

        suspended_raw = raw.get("suspended_features", [])
        if not isinstance(suspended_raw, (list, tuple)):
            raise ValueError("suspended_features must be a list")
        suspended = tuple(str(item) for item in suspended_raw)
        fence_raw = raw.get("transition_fence", {})
        if not isinstance(fence_raw, dict):
            raise ValueError("transition_fence must be an object")
        fence = {str(key): str(value).strip() for key, value in fence_raw.items()}

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
            confirmed_by_user=confirmed_by_user,
            transition_fence=fence,
        )
        if action in {"set_base", "begin_temporary"} and requested_mode is None:
            raise ValueError(f"requested_mode is required for {action}")
        if action == "set_auto" and enabled is None:
            raise ValueError("enabled is required for set_auto")
        if action == "end_temporary" and not command.transition_id:
            raise ValueError("transition_id is required for end_temporary")
        if action == "transition_owned_temporary_maintenance" and requested_mode is not Mode.MAINTENANCE:
            raise ValueError("transition-owned recovery requires MAINTENANCE")
        return command


def _add_drift(state: ModeState, item: str) -> ModeState:
    if item in state.drift:
        return state
    return replace(state, drift=state.drift + (item,))


def set_base_mode(state: ModeState, mode: Mode | str, *, confirmed_by_user: bool = False) -> ModeState:
    resolved = Mode(mode)
    if state.active_transition_id:
        return _add_drift(state, "base_mode_change_blocked_active_transition")
    if state.development_session_active and resolved is not Mode.DEVELOPMENT and not confirmed_by_user:
        return _add_drift(state, "development_session_requires_explicit_close")
    return replace(
        state,
        base_mode=resolved,
        effective_mode=resolved,
        development_session_active=resolved is Mode.DEVELOPMENT,
        temporary_reason="",
        active_transition_id="",
        suspended_features=(),
    )


def close_development_session(state: ModeState, confirmed_by_user: bool) -> ModeState:
    if not state.development_session_active:
        return _add_drift(state, "development_session_not_active")
    if not confirmed_by_user:
        return _add_drift(state, "development_session_close_requires_user_confirmation")
    if state.active_transition_id:
        return _add_drift(state, "development_session_close_blocked_active_transition")
    return replace(
        state,
        base_mode=Mode.USER,
        effective_mode=Mode.USER,
        development_session_active=False,
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


def _active_release_transition(project_root: Path | str) -> dict[str, Any] | None:
    root = Path(project_root)
    try:
        live = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
        if tuple(int(part) for part in live.split(".")) >= (32, 4, 57):
            return None
    except (OSError, ValueError):
        pass
    path = project_system_path(root, 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json')
    value = read_transition_state(path, missing_ok=True)
    if not isinstance(value, dict):
        return None
    lifecycle = str(value.get("lifecycle_state") or "").upper()
    if lifecycle in {"COMPLETE", "ROLLED_BACK", "CANCELLED"}:
        return None
    return value


def _transition_owned_project_cr_maintenance_allowed(
    project_root: Path | str, command: ModeCommand, transition: dict[str, Any]
) -> bool:
    """Accept one explicitly approved, coordinator-fenced Project-CR bridge.

    This is deliberately separate from ordinary mode commands: every identity
    at the transition, queue and bridge boundaries must match before a mode can
    change while a release transition is active.
    """
    if command.action != "transition_owned_temporary_maintenance":
        return False
    if command.requested_mode is not Mode.MAINTENANCE or not command.confirmed_by_user:
        return False
    fence = command.transition_fence
    if not str(fence.get("approval_reference") or "").strip():
        return False
    ticket = transition.get("current_ticket") if isinstance(transition.get("current_ticket"), dict) else {}
    if (
        transition.get("lifecycle_state") != "ACTIVE"
        or transition.get("phase") != "PROJECT_CR"
        or transition.get("phase_status") != "WAITING_RESULT"
    ):
        return False
    required = {
        "generation_id": transition.get("generation_id"),
        "phase": transition.get("phase"),
        "phase_status": transition.get("phase_status"),
        "lifecycle_state": transition.get("lifecycle_state"),
        "ticket_request_id": ticket.get("request_id"),
        "idempotency_key": ticket.get("idempotency_key"),
        "executor_name": "project_cr_create",
        "release_owner": transition.get("to_release"),
    }
    if ticket.get("executor_name") != "project_cr_create":
        return False
    if any(not value or str(fence.get(key) or "") != str(value) for key, value in required.items()):
        return False
    root = Path(project_root)
    try:
        live_release = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
        request = json.loads((project_system_path(root, 'Inbox/project_cr_local/request.json')).read_text(encoding="utf-8"))
        queue_raw = json.loads((project_system_path(root, 'Inbox/projectmanager_v2/RuntimeV2/commands/queue.json')).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(request, dict):
        return False
    if isinstance(queue_raw, list):
        queue = queue_raw
    elif isinstance(queue_raw, dict) and isinstance(queue_raw.get("items"), list):
        queue = queue_raw["items"]
    else:
        return False
    if live_release != str(required["release_owner"]):
        return False
    command_id = str(fence.get("command_id") or "")
    request_id = str(fence.get("project_cr_request_id") or "")
    if not command_id or not request_id:
        return False
    if not (
        request.get("schema") == "energie_project_cr_local_request_v1"
        and request.get("operation") == "project_cr_create"
        and str(request.get("request_id") or "") == request_id
        and str(request.get("command_id") or "") == command_id
        and str(request.get("expected_runtime_version") or "") == live_release
    ):
        return False
    queued = next((item for item in queue if isinstance(item, dict) and str(item.get("id") or "") == command_id), None)
    if not isinstance(queued, dict) or queued.get("status") != "PENDING":
        return False
    queue_required = {
        "intent": "project_cr_create",
        "transition_generation": required["generation_id"],
        "transition_phase": required["phase"],
        "transition_request_id": required["ticket_request_id"],
        "transition_idempotency_key": required["idempotency_key"],
        "executor_name": required["executor_name"],
        "release_owner": required["release_owner"],
        "release_version": required["release_owner"],
    }
    return all(str(queued.get(key) or "") == str(value) for key, value in queue_required.items())


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

    # Public/ordinary mode commands must be consumed but cannot mutate mode
    # while one durable release transition owns the release lifecycle. This
    # prevents a stale GUI/API command from applying later after restart.
    transition = _active_release_transition(project_root)
    if transition is not None and _transition_owned_project_cr_maintenance_allowed(project_root, command, transition):
        updated = set_base_mode(state, Mode.MAINTENANCE, confirmed_by_user=True)
        updated = replace(updated, last_processed_request_id=command.request_id, reconciliation_status="ok")
        save_mode_state(project_root, updated)
        return updated
    if transition is not None:
        updated = _add_drift(state, "release_transition_active_normal_mutation_blocked")
        updated = replace(
            updated,
            last_processed_request_id=command.request_id,
            reconciliation_status="required",
        )
        save_mode_state(project_root, updated)
        return updated

    updated = state
    if command.action == "set_base":
        updated = set_base_mode(state, command.requested_mode, confirmed_by_user=command.confirmed_by_user)
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
    elif command.action == "close_development_session":
        updated = close_development_session(state, command.confirmed_by_user)
    elif command.action == "reconcile":
        updated = state

    updated = replace(
        updated,
        last_processed_request_id=command.request_id,
        reconciliation_status="required",
    )
    save_mode_state(project_root, updated)
    return updated
