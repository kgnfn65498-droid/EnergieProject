import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from persistence import atomic_write_json


def _fingerprint_tree(root: Path) -> str:
    base = Path(root)
    digest = hashlib.sha256()
    files = sorted(
        path for path in base.rglob('*.py')
        if '__pycache__' not in path.parts and path.is_file() and not path.is_symlink()
    )
    if not files:
        raise RuntimeError('embedded Projectmanager source set is empty')
    for path in files:
        rel = path.relative_to(base).as_posix().encode('utf-8')
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(4, 'big'))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, 'big'))
        digest.update(data)
    return digest.hexdigest()


_LOADED_PM_ROOT = Path(__file__).resolve().parent
LOADED_RUNTIME_FINGERPRINT = _fingerprint_tree(_LOADED_PM_ROOT)


def _write_runtime_evidence(runtime, status: dict) -> dict:
    config = runtime.config
    generation = str(status.get('cycle_generation') or '').strip()
    provenance = status.get('provenance') if isinstance(status.get('provenance'), dict) else {}
    if not generation or provenance.get('generation') != generation or provenance.get('phase') != 'FINAL':
        raise RuntimeError('embedded Projectmanager cycle is not coherent FINAL')
    observed_epoch = time.time()
    payload = {
        'schema': 'energie_embedded_pm_runtime_v1',
        'status': 'GREEN',
        'pid': os.getpid(),
        'loaded_runtime_fingerprint': LOADED_RUNTIME_FINGERPRINT,
        'runtime_release_version': str(getattr(config, 'running_release_version', '') or '').strip(),
        'cycle_generation': generation,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
        'observed_at_epoch': observed_epoch,
        'observed_at': datetime.fromtimestamp(observed_epoch, timezone.utc).isoformat(),
    }
    target = Path(config.system_root) / 'embedded_runtime' / 'current.json'
    atomic_write_json(target, payload, mode=0o644)
    return payload


def _write_cycle_state(runtime, status: str, *, started_at_epoch: float, error: str = "") -> dict:
    config = runtime.config
    now = time.time()
    payload = {
        "schema": "energie_embedded_pm_cycle_v1",
        "status": str(status),
        "release_version": str(getattr(config, "running_release_version", "") or "").strip(),
        "pid": os.getpid(),
        "started_at_epoch": float(started_at_epoch),
        "observed_at_epoch": now,
        "observed_at": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "error": str(error or ""),
    }
    if status != "RUNNING":
        payload["finished_at_epoch"] = now
    atomic_write_json(Path(config.system_root) / "embedded_runtime" / "cycle.json", payload)
    return payload


def run_embedded(stop_event, *, runtime, interval_seconds=60, on_failure=None, on_success=None):
    """Run PM cycles inside the existing Energie add-on process.

    Ordinary PM exceptions never own or terminate the primary app. Unexpected
    BaseException classes are deliberately allowed to escape to the outer
    worker supervisor, which can alert/restart the PM thread under the same
    singleton lock policy.
    """
    failures = 0
    interval = max(60, int(interval_seconds))
    while not stop_event.is_set():
        cycle_started = time.time()
        try:
            _write_cycle_state(runtime, "RUNNING", started_at_epoch=cycle_started)
            status = runtime.run_once()
            if not isinstance(status, dict):
                raise RuntimeError('embedded Projectmanager cycle returned no status object')
            _write_runtime_evidence(runtime, status)
            _write_cycle_state(runtime, "GREEN", started_at_epoch=cycle_started)
            if on_success is not None:
                try:
                    on_success()
                except Exception:
                    logging.exception('Projectmanager success callback failed safely')
        except Exception as exc:
            failures += 1
            try:
                _write_cycle_state(
                    runtime, "RED", started_at_epoch=cycle_started,
                    error=f"{type(exc).__name__}: {exc}",
                )
            except Exception:
                logging.exception('Embedded Projectmanager cycle-evidence write failed safely')
            logging.exception('Embedded Projectmanager cycle failed; primary Energie app remains active')
            if on_failure is not None:
                try:
                    on_failure(exc)
                except Exception:
                    logging.exception('Projectmanager failure callback failed safely')
        if stop_event.wait(interval):
            break
    return {'state': 'stopped', 'failures': failures}
