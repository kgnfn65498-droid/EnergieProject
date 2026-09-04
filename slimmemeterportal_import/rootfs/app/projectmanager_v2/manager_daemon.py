import logging
import signal
import sys
import time
from datetime import datetime, timezone

from manager_config import ManagerConfig
from orchestrator import ProjectmanagerRuntime
from service_lock import FileLock

STOP_REQUESTED = False


def request_stop(signum, frame):
    global STOP_REQUESTED
    STOP_REQUESTED = True
    logging.info('Stopsignaal ontvangen: %s', signum)


def next_sleep_seconds(interval_seconds: int) -> int:
    return max(60, int(interval_seconds))


def run_cycle(service, *, now=None) -> dict:
    now = now or datetime.now(timezone.utc)
    try:
        status = service.run_once(now=now)
        return {'state': 'success', 'at': now.isoformat(), 'status': status}
    except Exception as exc:
        logging.exception('Projectmanager-cyclus mislukt')
        return {'state': 'failed', 'at': now.isoformat(), 'error': f'{type(exc).__name__}: {exc}'}


def sleep_interruptible(seconds: int):
    remaining = max(0, int(seconds))
    while remaining > 0 and not STOP_REQUESTED:
        chunk = min(remaining, 30)
        time.sleep(chunk)
        remaining -= chunk


def main() -> int:
    logging.basicConfig(
        level='INFO',
        format='%(asctime)s %(levelname)s %(message)s',
        stream=sys.stdout,
    )
    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    config = ManagerConfig.from_env()
    lock_path = f'{config.system_root}/locks/projectmanager.lock'
    try:
        with FileLock(lock_path):
            service = ProjectmanagerRuntime(config)
            logging.info('Energie Projectmanager V2 gestart; interval=%ss', config.interval_seconds)
            while not STOP_REQUESTED:
                result = run_cycle(service)
                if result['state'] == 'failed':
                    logging.error('Projectmanager-cyclus rood: %s', result['error'])
                sleep_interruptible(next_sleep_seconds(config.interval_seconds))
    except RuntimeError as exc:
        logging.error('Projectmanager niet gestart: %s', exc)
        return 2
    logging.info('Energie Projectmanager V2 gestopt')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
