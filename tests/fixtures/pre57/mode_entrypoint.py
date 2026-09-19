from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import main as app
from operating_mode_runtime import (
    install_mode_overrides,
    install_release_hold_guards,
    operating_mode_project_root,
    operating_mode_tick,
    operating_mode_worker,
    recover_startup_mode_state,
)
from operating_mode_web import install_mode_web
from operating_mode_crash_recovery import (
    crash_recovery_mode_worker,
    install_crash_recovery_mode_integration,
    recover_crash_recovery_mode_session,
)
from release_validation_hold import ensure_release_hold_state
from operating_mode_auto_release import automatic_release_hold_daemon as automatic_release_hold_worker
from projectmanager_v2_entrypoint import start_projectmanager_v2
from projectmanager_v2.projectmanager_web import install_projectmanager_web
from projectmanager_v2.release_transition import ReleaseTransitionCoordinator
from projectmanager_v2.release_transition_worker import release_transition_daemon
from projectmanager_v2.startup_timing import StartupTiming
from projectmanager_v2.startup_recovery import startup_recovery_daemon
from process_workspace import ensure_process_workspace

TARGET_RELEASE_VERSION = "32.4.56"
app.APP_VERSION = TARGET_RELEASE_VERSION

_BACKGROUND_LOCK = threading.Lock()
_HOLD_THREAD = None
_TRANSITION_THREAD = None


def _supervise_background_workers(root):
    global _HOLD_THREAD, _TRANSITION_THREAD
    with _BACKGROUND_LOCK:
        pm_thread = start_projectmanager_v2(app.STOP, root, TARGET_RELEASE_VERSION)
        if _TRANSITION_THREAD is None or not _TRANSITION_THREAD.is_alive():
            _TRANSITION_THREAD = threading.Thread(
                target=release_transition_daemon, args=(app.STOP, app, root),
                daemon=True, name="release-transition-coordinator",
            )
            _TRANSITION_THREAD.start()
        if _HOLD_THREAD is None or not _HOLD_THREAD.is_alive():
            _HOLD_THREAD = threading.Thread(
                target=automatic_release_hold_worker,
                args=(app.STOP, app, root, TARGET_RELEASE_VERSION),
                daemon=True,
                name="release-hold-auto-validation",
            )
            _HOLD_THREAD.start()
        return {
            "projectmanager_alive": bool(pm_thread and pm_thread.is_alive()),
            "release_hold_alive": bool(_HOLD_THREAD and _HOLD_THREAD.is_alive()),
            "release_transition_alive": bool(_TRANSITION_THREAD and _TRANSITION_THREAD.is_alive()),
        }



def _load_json_object(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return None
    return value if isinstance(value, dict) else None


def _observe_startup_phases(startup_timing, root):
    runtime = Path(root) / "Inbox/projectmanager_v2/RuntimeV2"
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


def start_operating_mode_runtime() -> None:
    startup_epoch = time.time()
    root = operating_mode_project_root()
    # First substantive startup action: establish/verify the durable release transition.
    ReleaseTransitionCoordinator(root).bootstrap_legacy_if_needed()
    ensure_process_workspace(root)
    startup_timing = StartupTiming(root)
    startup_timing.mark("PROCESS_STARTED")
    ensure_release_hold_state(root, TARGET_RELEASE_VERSION)
    crash_recovery = recover_crash_recovery_mode_session(root)
    if not crash_recovery.get("preserve_temporary"):
        recover_startup_mode_state(root)
    install_mode_overrides(app, root)
    install_release_hold_guards(app, root)
    install_crash_recovery_mode_integration(app, root)
    operating_mode_tick(root, app_module=app)
    install_mode_web(app, root)
    # The approval card is inside authenticated Home Assistant ingress and
    # writes immutable ApprovalIngress envelopes only; it never mutates
    # RuntimeV2 directly.
    install_projectmanager_web(app, root)
    startup_timing.mark("INGRESS_READY")
    _supervise_background_workers(root)
    threading.Thread(
        target=startup_recovery_daemon,
        args=(
            app.STOP, root, TARGET_RELEASE_VERSION,
            os.environ.get("SUPERVISOR_TOKEN", ""), startup_epoch,
        ),
        daemon=True,
        name="pm-startup-recovery",
    ).start()
    threading.Thread(
        target=_observe_startup_phases,
        args=(startup_timing, root),
        daemon=True,
        name="startup-phase-observer",
    ).start()
    threading.Thread(
        target=crash_recovery_mode_worker,
        args=(app.STOP, app, root),
        daemon=True,
        name="crash-recovery-mode-reconcile",
    ).start()
    threading.Thread(
        target=operating_mode_worker,
        args=(app.STOP, root, app),
        kwargs={"lifecycle_tick": lambda: _supervise_background_workers(root)},
        daemon=True,
        name="operating-mode-reconcile",
    ).start()


def main() -> None:
    start_operating_mode_runtime()
    app.main()


if __name__ == "__main__":
    main()
