from __future__ import annotations

import threading

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
from operating_mode_auto_release import automatic_release_hold_worker
from projectmanager_v2_entrypoint import start_projectmanager_v2

TARGET_RELEASE_VERSION = "32.4.1"
app.APP_VERSION = TARGET_RELEASE_VERSION


def start_operating_mode_runtime() -> None:
    root = operating_mode_project_root()
    ensure_release_hold_state(root, TARGET_RELEASE_VERSION)
    crash_recovery = recover_crash_recovery_mode_session(root)
    if not crash_recovery.get("preserve_temporary"):
        recover_startup_mode_state(root)
    install_mode_overrides(app, root)
    install_release_hold_guards(app, root)
    install_crash_recovery_mode_integration(app, root)
    operating_mode_tick(root, app_module=app)
    install_mode_web(app, root)
    threading.Thread(
        target=automatic_release_hold_worker,
        args=(app.STOP, app, root, TARGET_RELEASE_VERSION),
        daemon=True,
        name="release-hold-auto-validation",
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
        daemon=True,
        name="operating-mode-reconcile",
    ).start()
    start_projectmanager_v2(app.STOP, root)


def main() -> None:
    start_operating_mode_runtime()
    app.main()


if __name__ == "__main__":
    main()
