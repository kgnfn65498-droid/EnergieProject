from datetime import datetime, timezone


def _parse_time(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value or '').strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _planning_trend(history):
    points = []
    for item in history or []:
        if not isinstance(item, dict):
            continue
        when = _parse_time(item.get('at'))
        try:
            step = int(item.get('step'))
        except (TypeError, ValueError):
            continue
        if when is not None:
            points.append((when, step))
    points.sort(key=lambda pair: pair[0])
    intervals = []
    for (a_time, a_step), (b_time, b_step) in zip(points, points[1:]):
        delta_steps = b_step - a_step
        seconds = (b_time - a_time).total_seconds()
        if delta_steps > 0 and seconds >= 0:
            intervals.append(seconds / delta_steps)
    if len(intervals) < 2:
        return 'insufficient_data'
    previous = sum(intervals[:-1]) / len(intervals[:-1])
    latest = intervals[-1]
    if previous <= 0:
        return 'stable'
    ratio = latest / previous
    if ratio <= 0.85:
        return 'faster'
    if ratio >= 1.15:
        return 'slower'
    return 'stable'


def build_task_progress(task, *, now=None):
    if not isinstance(task, dict) or not task:
        return None
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    try:
        total = max(1, int(task.get('steps_total') or 1))
    except (TypeError, ValueError):
        total = 1
    try:
        step = max(1, min(total, int(task.get('step') or 1)))
    except (TypeError, ValueError):
        step = 1
    status = str(task.get('status') or 'ACTIVE').upper()
    completed = total if status == 'DONE' else max(0, step - 1)
    remaining = max(0, total - completed)
    created = _parse_time(task.get('created_at'))
    elapsed = max(0, int((now - created).total_seconds())) if created is not None else None

    history = task.get('progress_history') or []
    rates = []
    normalized = []
    for item in history:
        if not isinstance(item, dict):
            continue
        at = _parse_time(item.get('at'))
        try:
            history_step = int(item.get('step'))
        except (TypeError, ValueError):
            continue
        if at is not None:
            normalized.append((at, history_step))
    normalized.sort(key=lambda pair: pair[0])
    for (a_time, a_step), (b_time, b_step) in zip(normalized, normalized[1:]):
        step_delta = b_step - a_step
        seconds = (b_time - a_time).total_seconds()
        if step_delta > 0 and seconds >= 0:
            rates.append(seconds / step_delta)
    eta = None
    if rates and status != 'DONE':
        average = sum(rates) / len(rates)
        eta = max(0, int(round(average * remaining)))
    elif status == 'DONE':
        eta = 0

    color = {
        'BLOCKED': 'RED',
        'WAITING_APPROVAL': 'ORANGE',
        'PAUSED': 'ORANGE',
        'DONE': 'GREEN',
        'ACTIVE': 'GREEN',
    }.get(status, 'ORANGE')
    percent = 100 if status == 'DONE' else int(round((step / total) * 100))
    return {
        'step_label': f'Stap {step}/{total}',
        'step': step,
        'steps_total': total,
        'completed_steps': completed,
        'remaining_steps': remaining,
        'next_step': str(task.get('next_action') or ''),
        'elapsed_seconds': elapsed,
        'estimated_remaining_seconds': eta,
        'blockers': list(task.get('blockers') or []),
        'status_color': color,
        'progress_percent': percent,
        'planning_trend': _planning_trend(history),
    }
