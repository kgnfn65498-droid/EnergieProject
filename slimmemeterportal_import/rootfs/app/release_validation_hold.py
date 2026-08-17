from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
