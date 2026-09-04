import json
from datetime import datetime, timezone
from pathlib import Path

from cr_evidence import evaluate_cr_closure
from health_engine import check_boolean, evaluate_quarter_hour_heartbeat


def _previous_month_key(now: datetime) -> str:
    year, month = now.year, now.month
    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1
    return f'{year:04d}_{month:02d}'


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


class EnergyHealthCollector:
    def __init__(self, project_root, input_root, recovery_root):
        self.project_root = Path(project_root)
        self.input_root = Path(input_root)
        self.recovery_root = Path(recovery_root)

    def collect(self, *, now=None):
        now = now or datetime.now(timezone.utc)
        checks = []

        heartbeat_path = self.input_root / '_scheduler' / 'quarter_hour_heartbeat.json'
        heartbeat = _read_json(heartbeat_path)
        check = evaluate_quarter_hour_heartbeat(heartbeat or {}, now=now)
        check['evidence_ref'] = str(heartbeat_path)
        check['evidence_strength'] = 'verified' if heartbeat is not None else 'unverified'
        checks.append(check)

        month_key = _previous_month_key(now)
        year, month = month_key.split('_')
        closure_path = self.recovery_root / 'Status' / f'MonthClosure_{year}_{month}.json'
        closure = _read_json(closure_path)
        closure_ok = None if closure is None else closure.get('status') == 'CLOSED'
        closure_check = check_boolean(
            'previous_month_closure', closure_ok, failure_status='RED',
            reason_ok='closed', reason_fail='not_closed', details={'month': month_key, 'status': (closure or {}).get('status')}
        )
        closure_check['evidence_ref'] = str(closure_path)
        closure_check['evidence_strength'] = 'verified' if closure is not None else 'unverified'
        checks.append(closure_check)

        version_path = self.project_root / 'App' / 'VERSIE.txt'
        version_exists = version_path.is_file()
        version_value = version_path.read_text(encoding='utf-8').strip() if version_exists else ''
        checks.append({
            'name': 'production_version_source',
            'status': 'GREEN' if version_value else 'ORANGE',
            'reason': 'available' if version_value else 'missing_or_empty',
            'evidence_ref': str(version_path),
            'evidence_strength': 'verified' if version_value else 'unverified',
            'details': {'version': version_value or None},
        })

        mode_path = self.project_root / 'Inbox' / 'operating_mode' / 'operating_mode_state.json'
        mode = _read_json(mode_path)
        checks.append({
            'name': 'operating_mode_source',
            'status': 'GREEN' if isinstance(mode, dict) else 'ORANGE',
            'reason': 'available' if isinstance(mode, dict) else 'missing_or_invalid',
            'evidence_ref': str(mode_path),
            'evidence_strength': 'verified' if isinstance(mode, dict) else 'unverified',
            'details': {'effective_mode': (mode or {}).get('effective_mode') or (mode or {}).get('base_mode') or (mode or {}).get('mode')},
        })

        cr_state_dir = self.project_root / 'Data' / '03_Systeem' / 'Projectmanager' / 'State'
        cr_files = sorted(cr_state_dir.glob('crash_recovery_closure_*.json')) if cr_state_dir.is_dir() else []
        cr_path = cr_files[-1] if cr_files else None
        cr_payload = _read_json(cr_path) if cr_path else None
        cr_result = evaluate_cr_closure(cr_payload)
        checks.append({
            'name': 'crash_recovery_closure',
            'status': cr_result['status'],
            'reason': cr_result['reason'],
            'evidence_ref': str(cr_path) if cr_path else None,
            'evidence_strength': cr_result.get('evidence_strength', 'unverified'),
            'details': cr_result.get('details', {}),
        })

        return checks
