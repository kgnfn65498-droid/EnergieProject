from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
import json
import os
from pathlib import Path
import threading
from typing import Any

from atomic_release_acceptance import finalize_validated_atomic_release
from operating_modes import (
    ModeState,
    command_path,
    format_chat_status,
    load_mode_state,
    process_mode_command,
    profile_for,
    save_mode_state,
)
from release_validation_hold import (
    ReleaseHoldState,
    activate_release_hold,
    load_release_hold,
    record_hold_validation,
    release_hold,
)


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


def _validation_check(ok: bool, detail: str) -> dict[str, Any]:
    return {"ok": bool(ok), "detail": str(detail)}


def _web_runtime_check(app_module: Any) -> dict[str, Any]:
    handler_ok = getattr(app_module, "Handler", None) is not None
    html_ok = callable(getattr(app_module, "html_page", None))
    stop = getattr(app_module, "STOP", None)
    stop_ok = True
    if stop is not None and hasattr(stop, "is_set"):
        stop_ok = not bool(stop.is_set())
    ok = handler_ok and html_ok and stop_ok
    return _validation_check(ok, "web runtime healthy" if ok else "web runtime unavailable/stopping")


def _state_io_check(project_root: Path, expected_version: str) -> dict[str, Any]:
    hold_path = project_root / "Inbox/operating_mode/release_validation_hold.json"
    probe_path = project_root / "Inbox/operating_mode" / f".validation_probe.{os.getpid()}"
    try:
        if not hold_path.is_file():
            return _validation_check(False, "hold state file missing")
        hold = load_release_hold(project_root, expected_version)
        if hold.release_version != expected_version or not hold.active:
            return _validation_check(False, "hold state inconsistent")
        load_mode_state(project_root)
        probe_path.parent.mkdir(parents=True, exist_ok=True)
        payload = f"v32.3.14-state-io:{expected_version}"
        probe_path.write_text(payload, encoding="utf-8")
        if probe_path.read_text(encoding="utf-8") != payload:
            return _validation_check(False, "state io readback mismatch")
        return _validation_check(True, "mode/hold state readable and writable")
    except Exception as exc:
        return _validation_check(False, f"state io failed: {type(exc).__name__}")
    finally:
        try:
            probe_path.unlink(missing_ok=True)
        except Exception:
            pass


def _automatic_runtime_idle_check(observed: dict[str, Any]) -> dict[str, Any]:
    unsafe = []
    if observed.get("workflow_running"):
        unsafe.append("workflow_running")
    for key in (
        "run_on_start_effective",
        "schedule_effective",
        "full_workflow_effective",
        "automatic_month_close_effective",
    ):
        if observed.get(key):
            unsafe.append(key)
    return _validation_check(not unsafe, "idle" if not unsafe else ",".join(unsafe))


def _release_chain_check(project_root: Path, observed: dict[str, Any]) -> dict[str, Any]:
    processing = project_root / "Inbox/processing"
    disk_processing = sorted(path.name for path in processing.glob("*.zip")) if processing.exists() else []
    observed_processing = [str(item) for item in observed.get("release_processing", [])]
    installer_lock = project_root / "Inbox/.installer.lock"
    unsafe = sorted(set(disk_processing + observed_processing))
    if installer_lock.exists():
        return _validation_check(False, "installer lock active")
    if unsafe:
        return _validation_check(False, "processing active: " + ",".join(unsafe))
    return _validation_check(True, "release chain idle")


def _projectmanager_self_audit_check(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root)
    audit_path = root / "Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json"
    status_path = root / "Inbox/projectmanager_v2/RuntimeV2/status/current.json"
    version_path = root / "App/VERSIE.txt"
    if not audit_path.is_file():
        return _validation_check(False, "projectmanager self-audit missing")
    if not status_path.is_file() or not version_path.is_file():
        return _validation_check(False, "projectmanager self-audit runtime provenance missing")
    try:
        payload = json.loads(audit_path.read_text(encoding="utf-8"))
        status_payload = json.loads(status_path.read_text(encoding="utf-8"))
        app_version = version_path.read_text(encoding="utf-8").strip()
        audit_mtime = audit_path.stat().st_mtime
        status_mtime = status_path.stat().st_mtime
    except (OSError, UnicodeError, json.JSONDecodeError):
        return _validation_check(False, "projectmanager self-audit invalid")
    if not isinstance(payload, dict) or not isinstance(status_payload, dict):
        return _validation_check(False, "projectmanager self-audit invalid")
    status = str(payload.get("status") or "").strip().upper()
    if status not in {"GREEN", "ORANGE", "RED"}:
        return _validation_check(False, "projectmanager self-audit invalid status")

    status_release = str(((status_payload.get("release") or {}).get("version")) or "").strip()

    def _numeric_release(value: str) -> tuple[int, ...]:
        try:
            return tuple(int(part) for part in str(value).strip().split('.'))
        except (TypeError, ValueError):
            return ()

    # 32.4.14 introduces the stronger PM-health gate. Historical release-hold
    # fixtures remain valid for their original contract, while 32.4.14+ is
    # fail-closed unless the only non-green signal is the expected atomic
    # LIVE_ACCEPTANCE transition.
    if _numeric_release(app_version) >= (32, 4, 14):
        health = status_payload.get("health")
        if not isinstance(health, dict):
            return _validation_check(False, "projectmanager health missing or invalid")
        health_status = str(health.get("status") or "").strip().upper()
        health_checks = health.get("checks")
        if health_status not in {"GREEN", "ORANGE", "RED"} or not isinstance(health_checks, list):
            return _validation_check(False, "projectmanager health missing or invalid")
        red_checks = [
            item for item in health_checks
            if isinstance(item, dict) and str(item.get("status") or "").strip().upper() == "RED"
        ]
        non_green = [
            item for item in health_checks
            if isinstance(item, dict) and str(item.get("status") or "").strip().upper() != "GREEN"
        ]

        # Release acceptance is not a declaration that every operational energy
        # signal is healthy.  Gating on the complete PM-health summary creates a
        # deadlock when an unrelated datapoint (for example a temporarily stale
        # quarter-hour snapshot) is RED while the software release itself is
        # valid.  Keep those operational REDs visible in PM health, but make the
        # release-hold gate fail-closed on release-chain checks only.  Version,
        # runtime-idle, state-I/O and self-audit provenance are validated by the
        # other dedicated hold checks in this same transaction.
        release_non_green = [
            item for item in non_green
            if str(item.get('name') or '').startswith('release_')
        ]
        release_red_checks = [
            item for item in release_non_green
            if str(item.get('status') or '').strip().upper() == 'RED'
        ]

        allowed_orange_transition = bool(release_non_green) and all(
            str(item.get('name') or '') == 'release_atomic_state'
            and str(item.get('status') or '').strip().upper() == 'ORANGE'
            and str(item.get('reason') or '') == 'installer_or_atomic_transition_active'
            for item in release_non_green
        )

        def _current_live_acceptance_journal_is_valid() -> bool:
            journal_path = root / 'Inbox/atomic_app_swap_state.json'
            try:
                journal = json.loads(journal_path.read_text(encoding='utf-8'))
            except (OSError, UnicodeError, json.JSONDecodeError):
                return False
            return bool(
                isinstance(journal, dict)
                and str(journal.get('state') or '').strip().upper() == 'LIVE_ACCEPTANCE'
                and str(journal.get('to_version') or '').strip() == app_version
                and bool(str(journal.get('from_version') or '').strip())
            )

        allowed_stale_acceptance_red = False
        if len(release_non_green) == 1:
            only = release_non_green[0]
            exact_stale_red = (
                str(only.get('name') or '') == 'release_atomic_state'
                and str(only.get('status') or '').strip().upper() == 'RED'
                and str(only.get('reason') or '') == 'live_acceptance_blocks_release_ingress'
            )
            allowed_stale_acceptance_red = bool(
                exact_stale_red and _current_live_acceptance_journal_is_valid()
            )

        # 32.4.16: a single next release may legitimately arrive while the
        # current release is finishing LIVE_ACCEPTANCE.  Keep the watcher
        # fail-closed until ACCEPTED, but allow the PM validation itself to
        # finish when (and only when) the two non-green checks are exactly:
        # one waiting incoming ZIP + the current release's atomic transition.
        allowed_waiting_next_release_acceptance = False
        if len(release_non_green) == 2 and _current_live_acceptance_journal_is_valid():
            by_name = {str(item.get('name') or ''): item for item in release_non_green}
            incoming_check = by_name.get('release_incoming')
            atomic_check = by_name.get('release_atomic_state')
            allowed_waiting_next_release_acceptance = bool(
                isinstance(incoming_check, dict)
                and str(incoming_check.get('status') or '').strip().upper() == 'ORANGE'
                and str(incoming_check.get('reason') or '') == 'release_waiting_incoming'
                and int((incoming_check.get('details') or {}).get('count') or 0) == 1
                and isinstance(atomic_check, dict)
                and str(atomic_check.get('status') or '').strip().upper() == 'RED'
                and str(atomic_check.get('reason') or '') == 'live_acceptance_blocks_release_ingress'
            )

        # 32.4.17: the release-validation hold itself is intentionally active
        # until this function proves the release safe. Treating that own hold as
        # a generic ORANGE signal creates a circular dependency: the hold can
        # never validate because its active state makes PM health non-green.
        # Allow only the exact current-release hold + atomic LIVE_ACCEPTANCE
        # combination, optionally with exactly one next release waiting.
        allowed_current_hold_acceptance = False
        if _current_live_acceptance_journal_is_valid():
            by_name = {str(item.get('name') or ''): item for item in release_non_green}
            names = set(by_name)
            allowed_name_sets = (
                {'release_validation_hold', 'release_atomic_state'},
                {'release_validation_hold', 'release_incoming', 'release_atomic_state'},
            )
            hold_check = by_name.get('release_validation_hold')
            atomic_check = by_name.get('release_atomic_state')
            incoming_check = by_name.get('release_incoming')
            hold_expected = bool(
                isinstance(hold_check, dict)
                and str(hold_check.get('status') or '').strip().upper() == 'ORANGE'
                and str(hold_check.get('reason') or '') == 'missing_active_or_unvalidated'
                and (hold_check.get('details') or {}).get('active') is True
                and str((hold_check.get('details') or {}).get('validation_status') or '').strip().lower()
                    in {'required', 'blocked'}
            )
            atomic_expected = bool(
                isinstance(atomic_check, dict)
                and str(atomic_check.get('status') or '').strip().upper() == 'RED'
                and str(atomic_check.get('reason') or '') == 'live_acceptance_blocks_release_ingress'
            )
            incoming_expected = (
                incoming_check is None
                or (
                    isinstance(incoming_check, dict)
                    and str(incoming_check.get('status') or '').strip().upper() == 'ORANGE'
                    and str(incoming_check.get('reason') or '') == 'release_waiting_incoming'
                    and int((incoming_check.get('details') or {}).get('count') or 0) == 1
                )
            )
            allowed_current_hold_acceptance = bool(
                names in allowed_name_sets and hold_expected and atomic_expected and incoming_expected
            )

        red_acceptance_exception = bool(
            allowed_stale_acceptance_red
            or allowed_waiting_next_release_acceptance
            or allowed_current_hold_acceptance
        )
        non_green_acceptance_exception = bool(
            red_acceptance_exception
            or (not release_red_checks and allowed_orange_transition)
        )

        if health_status == 'RED' and not red_checks:
            return _validation_check(False, "projectmanager health RED: summary")
        if release_red_checks and not red_acceptance_exception:
            names = ','.join(str(item.get('name') or 'unknown') for item in release_red_checks)
            return _validation_check(False, f"projectmanager health RED: {names}")
        if release_non_green and not non_green_acceptance_exception:
            names = ','.join(str(item.get('name') or 'unknown') for item in release_non_green)
            return _validation_check(False, f"unexpected non-green projectmanager health: {names}")
    if not app_version or status_release != app_version:
        return _validation_check(
            False,
            f"projectmanager self-audit release mismatch: status={status_release or 'missing'} app={app_version or 'missing'}",
        )
    if _numeric_release(app_version) >= (32, 4, 21):
        # File mtime is not a valid provenance relation here: the PM finalization
        # cycle writes the authoritative self-audit and then rewrites status with
        # the same logical generation. That makes the audit file slightly older
        # by construction and caused a permanent release-hold deadlock. Bind the
        # audit to the exact status generation it inspected instead.
        audit_status_updated_at = str(payload.get('status_updated_at') or '').strip()
        status_updated_at = str(status_payload.get('updated_at') or '').strip()
        if not audit_status_updated_at or audit_status_updated_at != status_updated_at:
            return _validation_check(
                False,
                "projectmanager self-audit provenance mismatch versus current PM status",
            )
    elif audit_mtime < status_mtime:
        return _validation_check(False, "projectmanager self-audit stale versus current PM status")
    return _validation_check(
        status == "GREEN",
        f"projectmanager self-audit {status} for release {app_version}",
    )


def _production_certificate_check(app_module: Any, expected_version: str | None = None) -> dict[str, Any]:
    """Validate production certificate without deadlocking a safe core-version upgrade.

    A clean old-core certificate may be carried as *pending recertification* for
    release acceptance because the automatic scheduler has its own current-core
    readiness gate. Corrupt or otherwise invalid certificate state stays blocked.
    """
    validate = getattr(app_module, "validate_production_certificate", None)
    if not callable(validate):
        def _version_tuple(value: Any) -> tuple[int, ...]:
            try:
                return tuple(int(part) for part in str(value or '').split('.'))
            except (TypeError, ValueError):
                return ()
        legacy_version = expected_version or getattr(app_module, "APP_VERSION", "")
        if _version_tuple(legacy_version) and _version_tuple(legacy_version) < (32, 4, 23):
            return _validation_check(True, "legacy release predates production-certificate hold gate")
        return _validation_check(False, "production certificate validator unavailable")
    try:
        certificate = validate()
    except Exception as exc:
        return _validation_check(False, f"production certificate validation failed: {type(exc).__name__}")
    if not isinstance(certificate, dict):
        return _validation_check(False, "production certificate validation returned invalid payload")
    if certificate.get("valid") is True:
        return _validation_check(True, "current production certificate valid")

    checks = certificate.get("checks") if isinstance(certificate.get("checks"), dict) else {}
    failed = sorted(name for name, ok in checks.items() if ok is not True)
    safe_core_mismatch = bool(
        certificate.get("integrity") == "ok"
        and failed == ["core_revision_current"]
        and checks.get("integrity_ok") is True
    )
    if safe_core_mismatch:
        return _validation_check(
            True,
            "pending recertification: prior certificate integrity is valid; automatic core remains gated",
        )
    detail = str(certificate.get("reason") or "production certificate invalid")
    return _validation_check(False, detail)


def validate_release_hold(
    app_module: Any,
    project_root: Path | str,
    expected_version: str,
) -> dict[str, Any]:
    """Run compact release checks plus one measured reconcile, including current PM self-audit."""
    root = Path(project_root)
    hold = load_release_hold(root, expected_version)
    state = load_mode_state(root)

    version_ok = str(getattr(app_module, "APP_VERSION", "")) == str(expected_version)
    try:
        observed = observe_measured_runtime(app_module, root, state, hold)
        runtime_error = None
    except Exception as exc:
        observed = {
            "workflow_running": True,
            "workflow_active": {},
            "cancel_requested": False,
            "run_on_start_effective": True,
            "schedule_effective": True,
            "full_workflow_effective": True,
            "automatic_month_close_effective": True,
            "release_processing": [],
        }
        runtime_error = type(exc).__name__

    checks = {
        "version": _validation_check(
            version_ok,
            f"installed={getattr(app_module, 'APP_VERSION', '')} expected={expected_version}",
        ),
        "web_runtime": _web_runtime_check(app_module),
        "state_io": _state_io_check(root, expected_version),
        "automatic_runtime_idle": (
            _validation_check(False, f"runtime probe unavailable: {runtime_error}")
            if runtime_error
            else _automatic_runtime_idle_check(observed)
        ),
        "release_chain": (
            _validation_check(False, f"runtime probe unavailable: {runtime_error}")
            if runtime_error
            else _release_chain_check(root, observed)
        ),
        "projectmanager_self_audit": _projectmanager_self_audit_check(root),
        "production_certificate": _production_certificate_check(app_module, expected_version),
    }

    reconciled = reconcile_measured_runtime(root, app_module)
    all_green = all(bool(item.get("ok")) for item in checks.values())
    validation_status = "ok" if all_green and reconciled.reconciliation_status == "ok" else "blocked"
    record_hold_validation(root, expected_version, checks, reconciled.reconciliation_status)
    return {
        "status": validation_status,
        "version": expected_version,
        "checks": checks,
        "reconcile_status": reconciled.reconciliation_status,
        "drift": list(reconciled.drift),
    }


def _audit_hold_event(app_module: Any, action: str, status: str, details: dict[str, Any]) -> None:
    audit = getattr(app_module, "append_audit_event", None)
    if not callable(audit):
        return
    try:
        audit("release_validation_hold", action=action, status=status, details=details)
    except Exception:
        pass


def _atomic_release_journal(project_root: Path | str) -> dict[str, Any] | None:
    path = Path(project_root) / "Inbox/atomic_app_swap_state.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def attempt_release_hold(
    app_module: Any,
    project_root: Path | str,
    expected_version: str,
    *,
    issued_by: str,
) -> dict[str, Any]:
    """Close a validated release as an idempotent two-state transaction.

    Safe order for a normal closure is atomic ACCEPTED first, then hold release.
    If the process restarts between either state write, this function reconciles
    the remaining half.  Inactive+LIVE_ACCEPTANCE is accepted only when the
    persisted hold proves a prior non-emergency validation and a fresh validation
    still passes.  Every ambiguous combination stays fail-closed.
    """
    root = Path(project_root)
    expected = str(expected_version)
    hold = load_release_hold(root, expected)
    journal = _atomic_release_journal(root)
    atomic_state = str((journal or {}).get("state") or "").strip().upper()
    atomic_target = str((journal or {}).get("to_version") or "").strip()

    # Recovery for the historic 32.4.17 failure window: the hold was persisted
    # inactive before atomic ACCEPTED.  Do not trust an arbitrary inactive hold;
    # require validated, reconciled, non-emergency provenance and revalidate now.
    if not hold.active:
        if atomic_state == "ACCEPTED" and atomic_target == expected:
            return {"status": "already_released", "validation": None, "hold": asdict(hold)}
        if atomic_state == "LIVE_ACCEPTANCE" and atomic_target == expected:
            provenance_ok = bool(
                hold.validation_status == "ok"
                and hold.reconcile_status == "ok"
                and hold.emergency_release is False
            )
            if not provenance_ok:
                details = {
                    "version": expected,
                    "atomic_state": atomic_state,
                    "validation_status": hold.validation_status,
                    "reconcile_status": hold.reconcile_status,
                    "emergency_release": hold.emergency_release,
                }
                _audit_hold_event(app_module, "atomic_recovery_blocked", "blocked", details)
                return {"status": "blocked_atomic_recovery", "validation": None, "details": details}
            # Re-arm before fresh validation so a temporarily blocked PM/runtime
            # can never leave automatic functionality unguarded while atomic is live.
            activate_release_hold(root, expected, "startup_recovery:inactive_hold_live_acceptance")
            validation = validate_release_hold(app_module, root, expected)
            if validation["status"] != "ok":
                _audit_hold_event(app_module, "atomic_recovery_validation_blocked", "blocked", validation)
                return {"status": "blocked_atomic_recovery", "validation": validation}
            try:
                atomic_acceptance = finalize_validated_atomic_release(root, expected)
            except Exception as exc:
                details = {
                    "version": expected,
                    "error": f"{type(exc).__name__}: {exc}",
                    "validation": validation,
                }
                _audit_hold_event(app_module, "atomic_recovery_failed", "blocked", details)
                return {"status": "blocked_atomic_acceptance", "validation": validation, "error": details["error"]}
            try:
                released = release_hold(root, expected, issued_by=issued_by)
            except Exception as exc:
                details = {
                    "version": expected,
                    "error": f"{type(exc).__name__}: {exc}",
                    "validation": validation,
                    "atomic_acceptance": atomic_acceptance,
                }
                _audit_hold_event(app_module, "hold_release_after_recovery_blocked", "blocked", details)
                return {"status": "blocked_hold_release", "validation": validation, "error": details["error"]}
            _audit_hold_event(app_module, "released", "ok", {
                "version": expected,
                "issued_by": issued_by,
                "emergency": False,
                "recovered_inactive_hold": True,
                "atomic_acceptance": atomic_acceptance,
            })
            return {
                "status": "released",
                "validation": validation,
                "hold": asdict(released),
                "atomic_acceptance": atomic_acceptance,
                "recovered_inactive_hold": True,
            }
        # No current atomic transition remains: historical non-atomic installs
        # may legitimately have an already released hold.  Any current mismatched
        # transition is ambiguous and remains blocked.
        if journal is None:
            return {"status": "already_released", "validation": None, "hold": asdict(hold)}
        details = {"version": expected, "atomic_state": atomic_state, "atomic_target": atomic_target}
        _audit_hold_event(app_module, "atomic_recovery_blocked", "blocked", details)
        return {"status": "blocked_atomic_recovery", "validation": None, "details": details}

    validation = validate_release_hold(app_module, root, expected)
    if validation["status"] != "ok":
        _audit_hold_event(app_module, "release_blocked", "blocked", validation)
        return {"status": "blocked", "validation": validation}

    # Commit the atomic release first.  If we restart here, the active validated
    # hold remains fail-closed and the next daemon pass safely releases it.
    try:
        atomic_acceptance = finalize_validated_atomic_release(root, expected)
    except Exception as exc:
        details = {
            "version": expected,
            "error": f"{type(exc).__name__}: {exc}",
            "validation": validation,
        }
        _audit_hold_event(app_module, "atomic_acceptance_blocked", "blocked", details)
        return {"status": "blocked_atomic_acceptance", "validation": validation, "error": details["error"]}

    try:
        released = release_hold(root, expected, issued_by=issued_by)
    except Exception as exc:
        # Atomic ACCEPTED is already durable. Keep the hold active; retry will
        # observe already_accepted and finish this remaining safe half.
        details = {
            "version": expected,
            "error": f"{type(exc).__name__}: {exc}",
            "validation": validation,
            "atomic_acceptance": atomic_acceptance,
        }
        _audit_hold_event(app_module, "hold_release_after_acceptance_blocked", "blocked", details)
        return {"status": "blocked_hold_release", "validation": validation, "error": details["error"]}

    _audit_hold_event(
        app_module,
        "released",
        "ok",
        {
            "version": expected,
            "issued_by": issued_by,
            "emergency": False,
            "atomic_acceptance": atomic_acceptance,
        },
    )
    return {
        "status": "released",
        "validation": validation,
        "hold": asdict(released),
        "atomic_acceptance": atomic_acceptance,
    }


def attempt_emergency_release_hold(
    app_module: Any,
    project_root: Path | str,
    expected_version: str,
    *,
    issued_by: str,
    confirmed: bool,
) -> dict[str, Any]:
    root = Path(project_root)
    hold = load_release_hold(root, expected_version)
    if not hold.active:
        return {"status": "already_released"}
    if not confirmed:
        return {"status": "confirmation_required"}

    state = load_mode_state(root)
    try:
        observed = observe_measured_runtime(app_module, root, state, hold)
    except Exception as exc:
        return {"status": "blocked", "reason": f"runtime_probe_unavailable:{type(exc).__name__}"}

    unsafe = []
    if observed["workflow_running"]:
        unsafe.append("workflow_running")
    for key in (
        "run_on_start_effective",
        "schedule_effective",
        "full_workflow_effective",
        "automatic_month_close_effective",
    ):
        if observed[key]:
            unsafe.append(key)
    if observed["release_processing"]:
        unsafe.append("release_processing")
    if (root / "Inbox/.installer.lock").exists():
        unsafe.append("installer_lock")
    if unsafe:
        _audit_hold_event(
            app_module,
            "emergency_release_blocked",
            "blocked",
            {"version": expected_version, "unsafe": unsafe, "issued_by": issued_by},
        )
        return {"status": "blocked", "reason": ",".join(unsafe)}

    released = release_hold(
        root,
        expected_version,
        issued_by=issued_by,
        emergency=True,
        reasons=("manual_emergency_release",),
    )
    _audit_hold_event(
        app_module,
        "emergency_release",
        "warning",
        {"version": expected_version, "issued_by": issued_by, "readback": observed},
    )
    return {"status": "released_emergency", "hold": asdict(released)}


def operating_mode_snapshot(state: ModeState, hold: ReleaseHoldState | None = None) -> dict[str, Any]:
    desired = asdict(profile_for(state.effective_mode, state.suspended_features))
    chat_status = format_chat_status(state)
    snapshot = {
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
        "chat_status": chat_status,
    }
    if hold is not None:
        hold_payload = asdict(hold)
        hold_payload["reasons"] = list(hold.reasons)
        snapshot["release_validation_hold"] = hold_payload
        if hold.active:
            snapshot["chat_status"] = chat_status + " · RELEASE VALIDATION HOLD"
    return snapshot


def operating_mode_tick(
    project_root: Path | str | None = None,
    app_module: Any = None,
) -> dict[str, Any]:
    root = Path(project_root) if project_root is not None else operating_mode_project_root()
    before = load_mode_state(root)
    pending = _pending_command(root)
    state = process_mode_command(root)
    hold: ReleaseHoldState | None = None
    if app_module is None:
        observed = observe_operating_mode_runtime(state)
        state = reconcile_state(root, observed)
    else:
        state = reconcile_measured_runtime(root, app_module)
        hold = load_release_hold(root, str(app_module.APP_VERSION))
    snapshot = operating_mode_snapshot(state, hold)
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
