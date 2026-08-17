from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
import json
import os
from pathlib import Path
from typing import Any


_HOLD_RELATIVE = Path("Inbox/operating_mode/release_validation_hold.json")


@dataclass(frozen=True)
class ReleaseHoldState:
    schema_version: int = 1
    active: bool = True
    release_version: str = ""
    activated_at: str = ""
    activated_reason: str = ""
    validation_status: str = "required"
    validation_checks: dict[str, Any] = field(default_factory=dict)
    reconcile_status: str = "required"
    released_at: str = ""
    released_by: str = ""
    emergency_release: bool = False
    reasons: tuple[str, ...] = ()


def hold_state_path(project_root: Path | str) -> Path:
    return Path(project_root) / _HOLD_RELATIVE


def _payload(state: ReleaseHoldState) -> dict[str, Any]:
    data = asdict(state)
    data["reasons"] = list(state.reasons)
    return data


def _save(project_root: Path | str, state: ReleaseHoldState) -> ReleaseHoldState:
    path = hold_state_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(_payload(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return state


def _fail_closed(version: str, reason: str) -> ReleaseHoldState:
    return ReleaseHoldState(
        active=True,
        release_version=str(version),
        validation_status="required",
        reconcile_status="required",
        reasons=(reason,),
    )


def activate_release_hold(project_root: Path | str, version: str, reason: str) -> ReleaseHoldState:
    now = datetime.now().astimezone().isoformat()
    state = ReleaseHoldState(
        active=True,
        release_version=str(version),
        activated_at=now,
        activated_reason=str(reason),
        validation_status="required",
        reconcile_status="required",
        reasons=(),
    )
    return _save(project_root, state)


def load_release_hold(project_root: Path | str, installed_version: str) -> ReleaseHoldState:
    path = hold_state_path(project_root)
    if not path.exists():
        return _fail_closed(installed_version, "missing_hold_state")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _fail_closed(installed_version, "invalid_hold_state")
    if not isinstance(raw, dict):
        return _fail_closed(installed_version, "invalid_hold_state")
    try:
        state = ReleaseHoldState(
            schema_version=int(raw.get("schema_version", 1)),
            active=bool(raw["active"]),
            release_version=str(raw["release_version"]),
            activated_at=str(raw.get("activated_at", "")),
            activated_reason=str(raw.get("activated_reason", "")),
            validation_status=str(raw.get("validation_status", "required")),
            validation_checks=dict(raw.get("validation_checks") or {}),
            reconcile_status=str(raw.get("reconcile_status", "required")),
            released_at=str(raw.get("released_at", "")),
            released_by=str(raw.get("released_by", "")),
            emergency_release=bool(raw.get("emergency_release", False)),
            reasons=tuple(str(item) for item in (raw.get("reasons") or [])),
        )
    except (KeyError, TypeError, ValueError):
        return _fail_closed(installed_version, "invalid_hold_state")
    if state.release_version != str(installed_version):
        return _fail_closed(installed_version, "release_version_mismatch")
    return state


def ensure_release_hold_state(project_root: Path | str, installed_version: str) -> ReleaseHoldState:
    """Materialize fail-closed HOLD state for upgrades from releases that could not write the marker yet.

    Valid state for the installed release is left untouched, including an already released HOLD.
    Missing, corrupt, or version-mismatched state is persisted atomically as an active HOLD so
    normal validation can perform its state-I/O readback and later release it safely.
    """
    path = hold_state_path(project_root)
    state = load_release_hold(project_root, installed_version)
    repair_reasons = {"missing_hold_state", "invalid_hold_state", "release_version_mismatch"}
    if path.exists() and not any(reason in repair_reasons for reason in state.reasons):
        return state
    reason = next((reason for reason in state.reasons if reason in repair_reasons), "startup_fail_closed")
    now = datetime.now().astimezone().isoformat()
    materialized = replace(
        state,
        active=True,
        release_version=str(installed_version),
        activated_at=state.activated_at or now,
        activated_reason=state.activated_reason or f"startup_recovery:{reason}",
        validation_status="required",
        reconcile_status="required",
    )
    return _save(project_root, materialized)


def record_hold_validation(
    project_root: Path | str,
    installed_version: str,
    checks: dict[str, Any],
    reconcile_status: str,
) -> ReleaseHoldState:
    state = load_release_hold(project_root, installed_version)
    failed: list[str] = []
    for name, result in checks.items():
        ok = bool(result.get("ok")) if isinstance(result, dict) else bool(result)
        if not ok:
            failed.append(str(name))
    if reconcile_status != "ok":
        failed.append("reconcile")
    validation_status = "ok" if checks and not failed else "blocked"
    return _save(
        project_root,
        replace(
            state,
            validation_status=validation_status,
            validation_checks=dict(checks),
            reconcile_status=str(reconcile_status),
            reasons=tuple(failed),
        ),
    )


def release_hold(
    project_root: Path | str,
    installed_version: str,
    *,
    issued_by: str,
    emergency: bool = False,
    reasons: tuple[str, ...] | list[str] = (),
) -> ReleaseHoldState:
    state = load_release_hold(project_root, installed_version)
    if not state.active:
        return state
    if not emergency and (state.validation_status != "ok" or state.reconcile_status != "ok"):
        raise ValueError("release validation hold is not validated")
    now = datetime.now().astimezone().isoformat()
    final_reasons = tuple(str(item) for item in reasons) if reasons else state.reasons
    return _save(
        project_root,
        replace(
            state,
            active=False,
            released_at=now,
            released_by=str(issued_by),
            emergency_release=bool(emergency),
            reasons=final_reasons,
        ),
    )
