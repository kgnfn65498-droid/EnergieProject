from __future__ import annotations

"""Bounded startup recovery for the embedded Projectmanager runtime.

The primary Energie GUI must stay available even when the embedded PM stalls.
This module watches only the first fresh PM cycle after add-on startup. If no
fresh current-release status is published within the bounded grace period, it
requests at most one Supervisor restart in a durable window. A second stale
boot fails closed and records evidence instead of creating a restart loop.
"""

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from persistence import atomic_write_json

SCHEMA = "energie_embedded_pm_startup_recovery_v1"
DEFAULT_STALE_AFTER_SECONDS = 15 * 60
DEFAULT_RESTART_WINDOW_SECONDS = 60 * 60
DEFAULT_MAX_RESTART_REQUESTS = 1


def _runtime_root(project_root: Path) -> Path:
    return Path(project_root) / "Inbox/projectmanager_v2/RuntimeV2"


def _state_path(project_root: Path) -> Path:
    return _runtime_root(project_root) / "embedded_startup/recovery.json"


def _load_json(path: Path) -> dict:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _parse_epoch(value) -> float | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def _fresh_current_status(project_root: Path, expected_version: str, startup_epoch: float) -> tuple[bool, dict]:
    status = _load_json(_runtime_root(project_root) / "status/current.json")
    release = status.get("release") if isinstance(status.get("release"), dict) else {}
    updated_epoch = _parse_epoch(status.get("updated_at"))
    current = str(release.get("version") or "") == str(expected_version or "")
    fresh = updated_epoch is not None and updated_epoch >= float(startup_epoch)
    return bool(current and fresh), status


def _cycle_snapshot(project_root: Path) -> dict:
    return _load_json(_runtime_root(project_root) / "embedded_runtime/cycle.json")


def _persist(project_root: Path, payload: dict) -> dict:
    final = {
        "schema": SCHEMA,
        "delete_performed": False,
        **payload,
    }
    atomic_write_json(_state_path(project_root), final)
    return final


def request_supervisor_self_restart(supervisor_token: str) -> bool:
    token = str(supervisor_token or "").strip()
    if not token:
        return False
    request = urllib.request.Request(
        "http://supervisor/addons/self/restart",
        data=b"",
        headers={"Authorization": f"Bearer {token}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            response.read()
        return True
    except Exception:
        return False


def startup_recovery_check(
    project_root: Path,
    *,
    expected_version: str,
    startup_epoch: float,
    now_epoch: float | None = None,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    restart_window_seconds: float = DEFAULT_RESTART_WINDOW_SECONDS,
    max_restart_requests: int = DEFAULT_MAX_RESTART_REQUESTS,
    request_restart: Callable[[], bool] | None = None,
) -> dict:
    now = time.time() if now_epoch is None else float(now_epoch)
    startup = float(startup_epoch)
    fresh, status = _fresh_current_status(project_root, expected_version, startup)
    state = _load_json(_state_path(project_root))
    cycle = _cycle_snapshot(project_root)

    if fresh:
        return _persist(project_root, {
            "status": "GREEN",
            "reason": "fresh_pm_cycle_after_startup",
            "expected_version": str(expected_version),
            "startup_epoch": startup,
            "observed_at_epoch": now,
            "status_updated_at": status.get("updated_at"),
            "cycle": cycle,
            "window_started_at_epoch": now,
            "restart_requests": 0,
        })

    elapsed = max(0.0, now - startup)
    if elapsed < max(1.0, float(stale_after_seconds)):
        window_started = state.get("window_started_at_epoch")
        try:
            window_started = float(window_started)
        except (TypeError, ValueError):
            window_started = startup
        try:
            restart_requests = max(0, int(state.get("restart_requests") or 0))
        except (TypeError, ValueError):
            restart_requests = 0
        return _persist(project_root, {
            "status": "WAITING",
            "reason": "waiting_for_fresh_pm_cycle",
            "expected_version": str(expected_version),
            "startup_epoch": startup,
            "observed_at_epoch": now,
            "elapsed_seconds": elapsed,
            "cycle": cycle,
            "window_started_at_epoch": window_started,
            "restart_requests": restart_requests,
        })

    try:
        window_started = float(state.get("window_started_at_epoch"))
    except (TypeError, ValueError):
        window_started = now
    if now - window_started > max(1.0, float(restart_window_seconds)):
        window_started = now
        restart_requests = 0
    else:
        try:
            restart_requests = max(0, int(state.get("restart_requests") or 0))
        except (TypeError, ValueError):
            restart_requests = 0

    limit = max(0, int(max_restart_requests))
    base = {
        "expected_version": str(expected_version),
        "startup_epoch": startup,
        "observed_at_epoch": now,
        "elapsed_seconds": elapsed,
        "cycle": cycle,
        "window_started_at_epoch": window_started,
        "restart_requests": restart_requests,
    }

    if restart_requests >= limit:
        return _persist(project_root, {
            **base,
            "status": "BLOCKED",
            "reason": "restart_budget_exhausted",
        })

    restart = request_restart or (lambda: False)
    if restart() is not True:
        return _persist(project_root, {
            **base,
            "status": "BLOCKED",
            "reason": "supervisor_restart_request_failed",
        })

    restart_requests += 1
    return _persist(project_root, {
        **base,
        "status": "RESTART_REQUESTED",
        "reason": "pm_first_cycle_stale",
        "restart_requests": restart_requests,
        "restart_requested_at_epoch": now,
    })


def startup_recovery_daemon(
    stop_event,
    project_root: Path,
    expected_version: str,
    supervisor_token: str,
    startup_epoch: float,
    *,
    stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS,
    poll_seconds: float = 5.0,
) -> dict:
    while not stop_event.is_set():
        result = startup_recovery_check(
            project_root,
            expected_version=expected_version,
            startup_epoch=startup_epoch,
            stale_after_seconds=stale_after_seconds,
            request_restart=lambda: request_supervisor_self_restart(supervisor_token),
        )
        if result.get("status") in {"GREEN", "RESTART_REQUESTED", "BLOCKED"}:
            return result
        if stop_event.wait(max(1.0, float(poll_seconds))):
            break
    return {
        "schema": SCHEMA,
        "status": "STOPPED",
        "reason": "primary_app_stopping",
        "delete_performed": False,
    }
