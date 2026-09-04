from __future__ import annotations

import logging
import os
from pathlib import Path
import sys
import threading

_THREAD = None


def _pm_dir() -> Path:
    return Path(__file__).resolve().parent / 'projectmanager_v2'


def _load_runtime(project_root):
    pm_dir = _pm_dir()
    if str(pm_dir) not in sys.path:
        # Append, never prepend: existing Energie app modules keep precedence.
        sys.path.append(str(pm_dir))
    from embedded_config import build_embedded_config
    from orchestrator import ProjectmanagerRuntime
    from embedded_runtime import run_embedded
    config = build_embedded_config(
        project_root,
        pm_dir,
        supervisor_token=os.environ.get('SUPERVISOR_TOKEN', ''),
    )
    return ProjectmanagerRuntime(config), run_embedded, config


def _worker(stop_event, project_root):
    while not stop_event.is_set():
        try:
            runtime, run_embedded, config = _load_runtime(project_root)
            logging.info('Energie Projectmanager V2 embedded gestart; interval=%ss', config.interval_seconds)
            run_embedded(stop_event, runtime=runtime, interval_seconds=config.interval_seconds)
            return
        except Exception:
            logging.exception('Projectmanager V2 kon niet starten; primaire Energie-app blijft actief')
            if stop_event.wait(60):
                return


def start_projectmanager_v2(stop_event, project_root):
    global _THREAD
    if _THREAD is not None and _THREAD.is_alive():
        return _THREAD
    _THREAD = threading.Thread(
        target=_worker,
        args=(stop_event, Path(project_root)),
        daemon=True,
        name='energie-projectmanager-v2',
    )
    _THREAD.start()
    return _THREAD
