import logging


def run_embedded(stop_event, *, runtime, interval_seconds=300, on_failure=None, on_success=None):
    """Run PM cycles inside the existing Energie add-on process.

    Ordinary PM exceptions never own or terminate the primary app. Unexpected
    BaseException classes are deliberately allowed to escape to the outer
    worker supervisor, which can alert/restart the PM thread under the same
    singleton lock policy.
    """
    failures = 0
    interval = max(60, int(interval_seconds))
    while not stop_event.is_set():
        try:
            runtime.run_once()
            if on_success is not None:
                try:
                    on_success()
                except Exception:
                    logging.exception('Projectmanager success callback failed safely')
        except Exception as exc:
            failures += 1
            logging.exception('Embedded Projectmanager cycle failed; primary Energie app remains active')
            if on_failure is not None:
                try:
                    on_failure(exc)
                except Exception:
                    logging.exception('Projectmanager failure callback failed safely')
        if stop_event.wait(interval):
            break
    return {'state': 'stopped', 'failures': failures}
