from __future__ import annotations
from system_path_contract import project_system_path

import json
import os
import threading
import time
from pathlib import Path

import main as app
from projectmanager_v2_entrypoint import start_projectmanager_v2
from projectmanager_v2.projectmanager_web import install_projectmanager_web
from projectmanager_v2.startup_timing import StartupTiming
from process_workspace import ensure_process_workspace

TARGET_RELEASE_VERSION = "32.5.16"
app.APP_VERSION = TARGET_RELEASE_VERSION

_BACKGROUND_LOCK = threading.Lock()


def _supervise_background_workers(root):
    with _BACKGROUND_LOCK:
        pm_thread = start_projectmanager_v2(app.STOP, root, TARGET_RELEASE_VERSION)
        return {
            "projectmanager_alive": bool(pm_thread and pm_thread.is_alive()),
            "release_controller_external": True,
        }



def _load_json_object(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _observe_startup_phases(startup_timing, root):
    runtime = project_system_path(Path(root), 'Inbox/projectmanager_v2/RuntimeV2')
    status_path = runtime / "status/current.json"
    audit_path = runtime / "self_audit/current.json"
    first_status_marked = False
    pm_current_marked = False
    audit_marked = False
    while not app.STOP.is_set():
        status = _load_json_object(status_path)
        if status and not first_status_marked:
            startup_timing.mark("FIRST_STATUS_READY")
            first_status_marked = True
        if status and not pm_current_marked:
            release = status.get("release") if isinstance(status.get("release"), dict) else {}
            if str(release.get("version") or "") == TARGET_RELEASE_VERSION:
                startup_timing.mark("PM_CURRENT")
                pm_current_marked = True
        audit = _load_json_object(audit_path)
        if audit and not audit_marked:
            startup_timing.mark("BACKGROUND_AUDIT_COMPLETE")
            audit_marked = True
        if first_status_marked and pm_current_marked and audit_marked:
            return
        app.STOP.wait(0.1)


def start_runtime() -> None:
    startup_epoch = time.time()
    root = app._runtime_nas_roots_now()[1]
    ensure_process_workspace(root)
    startup_timing = StartupTiming(root)
    startup_timing.mark("PROCESS_STARTED")
    # The approval card is inside authenticated Home Assistant ingress and
    # writes immutable ApprovalIngress envelopes only; it never mutates
    # RuntimeV2 directly.
    install_projectmanager_web(app, root)
    startup_timing.mark("INGRESS_READY")
    _supervise_background_workers(root)
    threading.Thread(
        target=_observe_startup_phases,
        args=(startup_timing, root),
        daemon=True,
        name="startup-phase-observer",
    ).start()



def main() -> None:
    start_runtime()
    app.main()


if __name__ == "__main__":
    main()
