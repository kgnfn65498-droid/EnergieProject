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

TARGET_RELEASE_VERSION = "32.3.13"
app.APP_VERSION = TARGET_RELEASE_VERSION


def start_operating_mode_runtime() -> None:
    root = operating_mode_project_root()
    recover_startup_mode_state(root)
    operating_mode_tick(root)
    install_mode_overrides(app, root)
    install_release_hold_guards(app, root)
    install_mode_web(app, root)
    threading.Thread(
        target=operating_mode_worker,
        args=(app.STOP, root),
        daemon=True,
        name="operating-mode-reconcile",
    ).start()


def main() -> None:
    start_operating_mode_runtime()
    app.main()


if __name__ == "__main__":
    main()
