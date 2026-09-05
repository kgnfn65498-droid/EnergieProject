from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
import threading
import time
import urllib.request

_THREAD = None
_ALERT_COOLDOWN_SECONDS = 21600
_LAST_ALERT_AT = 0.0


def _pm_dir() -> Path:
    return Path(__file__).resolve().parent / 'projectmanager_v2'


def _prepare_imports():
    pm_dir = _pm_dir()
    if str(pm_dir) not in sys.path:
        sys.path.append(str(pm_dir))
    return pm_dir


def _load_config(project_root):
    pm_dir = _prepare_imports()
    from embedded_config import build_embedded_config
    return build_embedded_config(
        project_root,
        pm_dir,
        supervisor_token=os.environ.get('SUPERVISOR_TOKEN', ''),
    )


def _failure_path(config):
    return Path(config.system_root) / 'self_audit' / 'embedded_failure.json'


def _notify_failure(config, detail):
    global _LAST_ALERT_AT
    current = time.time()
    try:
        path = _failure_path(config)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({'status': 'RED', 'detail': detail, 'at': current}, indent=2) + '\n',
            encoding='utf-8',
        )
    except Exception:
        pass

    if current - _LAST_ALERT_AT < _ALERT_COOLDOWN_SECONDS:
        return False
    _LAST_ALERT_AT = current
    token = os.environ.get('SUPERVISOR_TOKEN', '')
    if not token:
        return False
    try:
        data = json.dumps({
            'title': 'Energie Projectmanager V2 — storing',
            'message': detail,
            'notification_id': 'energie_projectmanager_self_failure',
        }).encode('utf-8')
        request = urllib.request.Request(
            'http://supervisor/core/api/services/persistent_notification/create',
            data=data,
            headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(request, timeout=5):
            pass
        return True
    except Exception:
        return False


def _mark_success(config):
    path = _failure_path(config)
    try:
        if path.is_file():
            path.unlink()
    except OSError:
        pass


def _worker(stop_event, project_root):
    while not stop_event.is_set():
        config = None
        try:
            config = _load_config(project_root)
            # Cross-process lock is acquired BEFORE bootstrap/runtime/service
            # construction, so a second process cannot race state recovery.
            from service_lock import FileLock
            lock_path = Path(config.system_root) / 'locks' / 'projectmanager.lock'
            try:
                lock = FileLock(lock_path).acquire()
            except RuntimeError as exc:
                if 'lock already held' in str(exc):
                    logging.warning('Energie Projectmanager V2 niet dubbel gestart; singleton-lock is al bezet')
                    return
                raise
            try:
                from orchestrator import ProjectmanagerRuntime
                from embedded_runtime import run_embedded
                runtime = ProjectmanagerRuntime(config)
                logging.info('Energie Projectmanager V2 embedded gestart; interval=%ss', config.interval_seconds)
                run_embedded(
                    stop_event,
                    runtime=runtime,
                    interval_seconds=config.interval_seconds,
                    on_failure=lambda exc: _notify_failure(config, f'{type(exc).__name__}: {exc}'),
                    on_success=lambda: _mark_success(config),
                )
                return
            finally:
                lock.release()
        except BaseException as exc:
            if stop_event.is_set():
                return
            logging.exception('Projectmanager V2 kon niet starten; primaire Energie-app blijft actief')
            if config is not None:
                try:
                    _notify_failure(config, f'startup failure: {type(exc).__name__}: {exc}')
                except Exception:
                    pass
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
