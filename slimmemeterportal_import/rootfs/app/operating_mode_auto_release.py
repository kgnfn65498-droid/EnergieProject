from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
from datetime import datetime, timezone
import json
import os
import tempfile

from operating_mode_runtime import attempt_release_hold
from release_validation_hold import load_release_hold
from transition_state_io import read_transition_state, TransitionStateReadError

DEFAULT_AUTO_RELEASE_RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0, 15.0)


def _write_release_hold_worker_state(
    project_root: Path,
    expected_version: str,
    *,
    status: str,
    last_result: dict[str, Any] | None = None,
) -> None:
    path = project_root / "Inbox/operating_mode/release_hold_worker.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "energie_release_hold_worker_v1",
        "heartbeat_at": datetime.now(timezone.utc).isoformat(),
        "expected_version": str(expected_version),
        "status": str(status),
        "last_result": dict(last_result or {}),
    }
    fd, temp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        except OSError:
            pass


def automatic_release_hold_once(
    app_module: Any,
    project_root: Path | str,
    expected_version: str,
) -> dict[str, Any]:
    root = Path(project_root)
    transition_path = root / "Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json"
    try:
        transition = read_transition_state(transition_path, missing_ok=True)
    except TransitionStateReadError as exc:
        return {"status": "transition_invalid", "fail_closed": True, "error": str(exc)}
    if isinstance(transition, dict) and str(transition.get("to_release") or "") == str(expected_version) and str(transition.get("lifecycle_state") or "") not in {"COMPLETE", "ROLLED_BACK", "CANCELLED"}:
        return {"status": "coordinator_owned", "generation_id": transition.get("generation_id"), "phase": transition.get("phase")}
    if str(expected_version) >= "32.4.54" and not isinstance(transition, dict):
        return {"status": "transition_missing", "fail_closed": True}
    # Closure is a two-state transaction (release hold + atomic journal).
    # Never stop merely because the hold is inactive: after a restart the
    # atomic journal may still require LIVE_ACCEPTANCE -> ACCEPTED recovery.
    return attempt_release_hold(
        app_module,
        root,
        str(expected_version),
        issued_by="projectmanager_auto",
    )


def automatic_release_hold_worker(
    stop_event: Any,
    app_module: Any,
    project_root: Path | str,
    expected_version: str,
    *,
    retry_delays: Iterable[float] = DEFAULT_AUTO_RELEASE_RETRY_DELAYS,
) -> dict[str, Any]:
    root = Path(project_root)
    last: dict[str, Any] = {"status": "not_attempted"}
    for delay in tuple(float(item) for item in retry_delays):
        if stop_event.wait(max(0.0, delay)):
            return {"status": "stopped"}
        try:
            last = automatic_release_hold_once(app_module, root, str(expected_version))
        except Exception as exc:
            last = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
            logger = getattr(app_module, "LOGGER", None)
            if logger is not None and callable(getattr(logger, "exception", None)):
                logger.exception("Automatic release-hold validation failed")
        if last.get("status") in {"released", "already_released"}:
            return last
    return last


def automatic_release_hold_daemon(
    stop_event: Any,
    app_module: Any,
    project_root: Path | str,
    expected_version: str,
    *,
    retry_delays: Iterable[float] = DEFAULT_AUTO_RELEASE_RETRY_DELAYS,
    cycle_delay: float = 15.0,
) -> dict[str, Any]:
    """Keep running bounded validation cycles until release, stop, or shutdown.

    Each cycle preserves the historic bounded retry contract. The daemon is the
    live lifecycle wrapper that prevents a transient startup block from becoming
    a permanent LIVE_ACCEPTANCE deadlock.
    """
    root = Path(project_root)
    last: dict[str, Any] = {"status": "not_attempted"}
    _write_release_hold_worker_state(root, str(expected_version), status="starting", last_result=last)
    while True:
        last = automatic_release_hold_worker(
            stop_event,
            app_module,
            root,
            str(expected_version),
            retry_delays=retry_delays,
        )
        worker_status = str(last.get("status") or "unknown")
        _write_release_hold_worker_state(
            root, str(expected_version), status=worker_status, last_result=last
        )
        if worker_status in {"released", "already_released", "stopped"}:
            return last
        if stop_event.wait(max(0.0, float(cycle_delay))):
            _write_release_hold_worker_state(
                root, str(expected_version), status="stopped", last_result=last
            )
            return {"status": "stopped", "last": last}
