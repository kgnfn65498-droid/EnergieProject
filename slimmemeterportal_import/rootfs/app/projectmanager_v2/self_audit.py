import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

VALID_MODES = {'USER', 'DEVELOPMENT', 'MAINTENANCE'}
VALID_HEALTH = {'GREEN', 'ORANGE', 'RED'}
VALID_TASK = {'ACTIVE', 'PAUSED', 'BLOCKED', 'WAITING_APPROVAL', 'DONE'}
VALID_DECISION = {'PENDING', 'APPROVED', 'REJECTED'}
VALID_COMMAND = {
    'PENDING', 'PROCESSING', 'WAITING_APPROVAL', 'APPROVED_READY',
    'APPROVED_WAITING_EXECUTOR', 'INTERRUPTED', 'DONE', 'FAILED', 'CANCELLED',
}
VALID_HANDOFF = {'OPEN', 'DONE', 'BLOCKED', 'CANCELLED'}
VALID_APPROVED_ACTION = {'APPROVED_AWAITING_SAFETY_OR_EXECUTOR', 'DONE', 'CANCELLED', 'FAILED'}
SUPPORTED_EXECUTOR_ACTIONS = {'production_deploy'}
REQUIRED_RUNTIME_FILES = (
    'status/current.json',
    'heartbeat/manager.json',
    'handover/current.json',
    'audit/events.jsonl',
)


def _parse_iso(value):
    try:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _canonical_hash(spec):
    raw = json.dumps(spec, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


class SelfAuditor:
    def __init__(self, runtime_root, *, max_age_seconds=900, production_version_path=None,
                 quarantine_warning_seconds=86400, canonical_roadmap_path=None,
                 handoff_warning_seconds=172800):
        self.root = Path(runtime_root)
        self.max_age_seconds = int(max_age_seconds)
        self.production_version_path = Path(production_version_path) if production_version_path else None
        self.quarantine_warning_seconds = int(quarantine_warning_seconds)
        self.canonical_roadmap_path = Path(canonical_roadmap_path) if canonical_roadmap_path else None
        self.handoff_warning_seconds = int(handoff_warning_seconds)

    def _json(self, rel):
        path = self.root / rel
        try:
            value = json.loads(path.read_text(encoding='utf-8'))
            return value if isinstance(value, dict) else None
        except (OSError, json.JSONDecodeError):
            return None

    def _fresh(self, value, now):
        dt = _parse_iso(value)
        if dt is None:
            return None
        return max(0.0, (now.astimezone(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds()) <= self.max_age_seconds

    def run(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        missing = [rel for rel in REQUIRED_RUNTIME_FILES if not (self.root / rel).is_file()]
        invalid = []
        warnings = []
        if missing:
            return {'status': 'RED', 'missing': missing, 'invalid': invalid, 'warnings': warnings, 'required_files': list(REQUIRED_RUNTIME_FILES)}

        status = self._json('status/current.json')
        heartbeat = self._json('heartbeat/manager.json')
        handover = self._json('handover/current.json')
        if status is None:
            invalid.append({'path': 'status/current.json', 'reason': 'invalid_json_or_schema'})
        if heartbeat is None:
            invalid.append({'path': 'heartbeat/manager.json', 'reason': 'invalid_json_or_schema'})
        if handover is None:
            invalid.append({'path': 'handover/current.json', 'reason': 'invalid_json_or_schema'})

        try:
            lines = (self.root / 'audit/events.jsonl').read_text(encoding='utf-8').splitlines()
            if not lines:
                raise ValueError('empty')
            for line in lines[-50:]:
                if line.strip():
                    event = json.loads(line)
                    if not isinstance(event, dict) or not event.get('event_type'):
                        raise ValueError('invalid event schema')
        except (OSError, json.JSONDecodeError, ValueError):
            invalid.append({'path': 'audit/events.jsonl', 'reason': 'invalid_jsonl_or_schema'})

        if status is not None:
            if status.get('mode') not in VALID_MODES:
                invalid.append({'path': 'status/current.json', 'reason': 'invalid_mode'})
            if (status.get('health') or {}).get('status') not in VALID_HEALTH:
                invalid.append({'path': 'status/current.json', 'reason': 'invalid_health'})
            fresh = self._fresh(status.get('updated_at'), now)
            if fresh is None:
                invalid.append({'path': 'status/current.json', 'reason': 'invalid_updated_at'})
            elif not fresh:
                invalid.append({'path': 'status/current.json', 'reason': 'stale'})
            release = (status.get('release') or {}).get('version')
            if not release:
                invalid.append({'path': 'status/current.json', 'reason': 'release_missing'})
            elif self.production_version_path and self.production_version_path.is_file():
                try:
                    actual = self.production_version_path.read_text(encoding='utf-8').strip()
                except OSError:
                    actual = None
                if actual and release != actual:
                    invalid.append({'path': 'status/current.json', 'reason': 'release_mismatch', 'status_release': release, 'production_release': actual})

        if heartbeat is not None:
            if heartbeat.get('mode') not in VALID_MODES:
                invalid.append({'path': 'heartbeat/manager.json', 'reason': 'invalid_mode'})
            if heartbeat.get('health') not in VALID_HEALTH:
                invalid.append({'path': 'heartbeat/manager.json', 'reason': 'invalid_health'})
            fresh = self._fresh(heartbeat.get('heartbeat_at'), now)
            if fresh is None:
                invalid.append({'path': 'heartbeat/manager.json', 'reason': 'invalid_heartbeat_at'})
            elif not fresh:
                invalid.append({'path': 'heartbeat/manager.json', 'reason': 'stale'})
            if status and heartbeat.get('mode') != status.get('mode'):
                invalid.append({'path': 'heartbeat/manager.json', 'reason': 'mode_mismatch'})
            if status and heartbeat.get('health') != (status.get('health') or {}).get('status'):
                invalid.append({'path': 'heartbeat/manager.json', 'reason': 'health_mismatch'})

        if handover is not None:
            if handover.get('mode') not in VALID_MODES:
                invalid.append({'path': 'handover/current.json', 'reason': 'invalid_mode'})
            if status and handover.get('mode') != status.get('mode'):
                invalid.append({'path': 'handover/current.json', 'reason': 'mode_mismatch'})
            h_release = (handover.get('release') or {}).get('version')
            s_release = ((status or {}).get('release') or {}).get('version')
            if status and h_release != s_release:
                invalid.append({'path': 'handover/current.json', 'reason': 'release_mismatch'})

        mode_state = self._json('state/mode.json') if (self.root / 'state/mode.json').is_file() else None
        if mode_state is not None:
            if mode_state.get('mode') not in VALID_MODES:
                invalid.append({'path': 'state/mode.json', 'reason': 'invalid_mode'})
            elif status and mode_state.get('mode') != status.get('mode'):
                invalid.append({'path': 'state/mode.json', 'reason': 'mode_mismatch'})

        for rel, key, allowed in (
            ('state/tasks.json', 'tasks', VALID_TASK),
            ('decisions/queue.json', 'items', VALID_DECISION),
            ('commands/queue.json', 'items', VALID_COMMAND),
            ('handoffs/queue.json', 'items', VALID_HANDOFF),
            ('approved_actions/queue.json', 'items', VALID_APPROVED_ACTION),
        ):
            path = self.root / rel
            if not path.is_file():
                continue
            data = self._json(rel)
            if data is None or not isinstance(data.get(key, []), list):
                invalid.append({'path': rel, 'reason': 'invalid_json_or_schema'})
                continue
            for item in data.get(key, []):
                if not isinstance(item, dict) or item.get('status') not in allowed:
                    invalid.append({'path': rel, 'reason': 'invalid_item_status'})
                    break
            if rel == 'commands/queue.json' and any(item.get('status') == 'PROCESSING' for item in data.get('items', [])):
                invalid.append({'path': rel, 'reason': 'stranded_processing'})

        tasks_data = self._json('state/tasks.json') or {'tasks': []}
        handoffs_data = self._json('handoffs/queue.json') or {'items': []}
        open_handoffs = {item.get('task_id'): item for item in handoffs_data.get('items', []) if item.get('status') == 'OPEN'}
        for task in tasks_data.get('tasks', []):
            if task.get('status') in {'ACTIVE', 'BLOCKED'} and str(task.get('next_action') or '').startswith('handoff:'):
                handoff = open_handoffs.get(task.get('id'))
                if handoff is None:
                    invalid.append({'path': 'handoffs/queue.json', 'reason': 'active_handoff_task_without_open_handoff', 'task_id': task.get('id')})
                    continue
                created = _parse_iso(handoff.get('created_at'))
                if created is not None:
                    age = max(0.0, (now.astimezone(timezone.utc) - created.astimezone(timezone.utc)).total_seconds())
                    if age > self.handoff_warning_seconds:
                        warnings.append({'path': 'handoffs/queue.json', 'reason': 'handoff_waiting_too_long', 'task_id': task.get('id'), 'age_seconds': round(age, 1)})

        actions_data = self._json('approved_actions/queue.json') or {'items': []}
        for action in actions_data.get('items', []):
            if action.get('status') == 'APPROVED_AWAITING_SAFETY_OR_EXECUTOR' and action.get('action') not in SUPPORTED_EXECUTOR_ACTIONS:
                invalid.append({'path': 'approved_actions/queue.json', 'reason': 'approved_action_without_supported_executor', 'action': action.get('action')})

        roadmap = self._json('roadmap/queue.json')
        if self.canonical_roadmap_path is not None:
            try:
                canonical = json.loads(self.canonical_roadmap_path.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError):
                canonical = None
            if not isinstance(canonical, dict):
                invalid.append({'path': 'roadmap/queue.json', 'reason': 'canonical_roadmap_missing_or_invalid'})
            elif roadmap is None:
                invalid.append({'path': 'roadmap/queue.json', 'reason': 'runtime_roadmap_missing_or_invalid'})
            else:
                meta = roadmap.get('canonical') or {}
                expected_hash = _canonical_hash(canonical)
                if meta.get('sha256') != expected_hash or meta.get('version') != canonical.get('version'):
                    invalid.append({'path': 'roadmap/queue.json', 'reason': 'canonical_roadmap_drift'})

        quarantine = self.root / 'quarantine'
        if quarantine.is_dir():
            recent = []
            for path in quarantine.glob('*.corrupt'):
                try:
                    age = max(0.0, now.timestamp() - path.stat().st_mtime)
                except OSError:
                    continue
                if age <= self.quarantine_warning_seconds:
                    recent.append((path, age))
            recent.sort(key=lambda item: item[1])
            if recent:
                warnings.append({'path': 'quarantine', 'reason': 'recent_recovered_corruption_present', 'latest': recent[0][0].name, 'latest_age_seconds': round(recent[0][1], 1), 'recent_count': len(recent)})

        result_status = 'RED' if invalid else ('ORANGE' if warnings else 'GREEN')
        return {'status': result_status, 'missing': missing, 'invalid': invalid, 'warnings': warnings, 'required_files': list(REQUIRED_RUNTIME_FILES)}
