import logging


def run_embedded(stop_event, *, runtime, interval_seconds=300):
    """Run PM cycles inside an existing process; never own process signals."""
    failures=0
    interval=max(60,int(interval_seconds))
    while not stop_event.is_set():
        try:
            runtime.run_once()
        except Exception:
            failures += 1
            logging.exception('Embedded Projectmanager cycle failed; primary Energie app remains active')
        if stop_event.wait(interval):
            break
    return {'state':'stopped','failures':failures}
