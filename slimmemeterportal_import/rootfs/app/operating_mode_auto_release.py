from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from operating_mode_runtime import attempt_release_hold
from release_validation_hold import load_release_hold

DEFAULT_AUTO_RELEASE_RETRY_DELAYS = (1.0, 2.0, 4.0, 8.0, 15.0)


def automatic_release_hold_once(
    app_module: Any,
    project_root: Path | str,
    expected_version: str,
) -> dict[str, Any]:
    root = Path(project_root)
    hold = load_release_hold(root, str(expected_version))
    if not hold.active:
        return {"status": "already_released", "validation": None}
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
