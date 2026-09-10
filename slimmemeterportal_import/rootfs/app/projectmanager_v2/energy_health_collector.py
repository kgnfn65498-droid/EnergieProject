import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from month_closure_truth import closure_status_is_deep_verified
from cr_evidence import evaluate_cr_closure
from health_engine import evaluate_quarter_hour_heartbeat
from project_hygiene import ngrok_security_check, project_hygiene_check

VALID_MODES = {'USER', 'DEVELOPMENT', 'MAINTENANCE'}
LOCAL_TZ = ZoneInfo('Europe/Amsterdam')
LIVE_REQUIRED_ENTITY_IDS = {
    'p1': 'sensor.p1_meter_energie_import',
    'enphase': 'sensor.envoy_122335051406_lifetime_energy_production',
    'nordpool': 'sensor.nordpool_kwh_nl_eur_3_10_021',
    'nextenergy': 'sensor.nextenergy_actuele_stroomprijs',
}
BAD_ENTITY_STATES = {'unknown', 'unavailable', 'none', ''}


def _local(now):
    return now.astimezone(LOCAL_TZ) if now.tzinfo else now.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)


def _month_key(now):
    local = _local(now)
    return f'{local.year:04d}_{local.month:02d}'


def _previous_month_key(now):
    local = _local(now)
    year, month = local.year, local.month
    if month == 1:
        year -= 1
        month = 12
    else:
        month -= 1
    return f'{year:04d}_{month:02d}'


def _read_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None


def _check(name, status, reason, path=None, details=None, *, verified=None):
    if verified is None:
        verified = status == 'GREEN'
    return {
        'name': name,
        'status': status,
        'reason': reason,
        'evidence_ref': str(path) if path else None,
        'evidence_strength': 'verified' if verified else 'unverified',
        'details': details or {},
    }


def _age_seconds(path, now):
    try:
        return max(0.0, now.timestamp() - Path(path).stat().st_mtime)
    except OSError:
        return None


def _latest_file(directory, pattern):
    root = Path(directory)
    if not root.is_dir():
        return None
    files = [path for path in root.glob(pattern) if path.is_file()]
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with Path(path).open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
    except OSError:
        return ''
    return digest.hexdigest()


def _sidecar_sha_matches(zip_path: Path, sha_path: Path) -> bool:
    try:
        expected = sha_path.read_text(encoding='utf-8').split()[0]
    except (OSError, IndexError):
        return False
    return len(expected) == 64 and expected == _sha256_file(zip_path)


def _runtime_version(project_root: Path) -> str:
    try:
        return (Path(project_root) / 'App' / 'VERSIE.txt').read_text(encoding='utf-8').strip()
    except OSError:
        return ''


def _canonical_cr_regex(version: str, cr_type: str) -> re.Pattern[str]:
    return re.compile(
        rf'^\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}\.\d{{2}} {re.escape(version)} CR {re.escape(cr_type)}\.zip$'
    )


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
        scheduler = evaluate_quarter_hour_heartbeat(heartbeat or {}, now=now)
        scheduler['evidence_ref'] = str(heartbeat_path)
        scheduler['evidence_strength'] = 'verified' if heartbeat is not None else 'unverified'
        checks.append(scheduler)

        current_key = _month_key(now)
        quarter_dir = self.input_root / current_key / 'HomeAssistant' / 'QuarterHour'
        latest_quarter = _latest_file(quarter_dir, 'home_assistant_quarter_*.json')
        snapshot = _read_json(latest_quarter) if latest_quarter else None
        age = _age_seconds(latest_quarter, now) if latest_quarter else None
        snapshot_ok = isinstance(snapshot, dict) and bool(snapshot.get('entities')) and age is not None and age <= 1800
        checks.append(_check(
            'current_quarter_hour_snapshot',
            'GREEN' if snapshot_ok else 'RED',
            'fresh' if snapshot_ok else 'missing_invalid_or_stale',
            latest_quarter or quarter_dir,
            {'month': current_key, 'age_seconds': round(age, 1) if age is not None else None, 'entity_count': (snapshot or {}).get('entity_count')},
            verified=snapshot_ok,
        ))

        if snapshot:
            entities = {
                str(item.get('entity_id')): item
                for item in snapshot.get('entities', [])
                if isinstance(item, dict) and item.get('entity_id')
            }
            for source, entity_id in LIVE_REQUIRED_ENTITY_IDS.items():
                item = entities.get(entity_id)
                state = str((item or {}).get('state') or '').strip().lower()
                good = item is not None and state not in BAD_ENTITY_STATES
                checks.append(_check(
                    f'live_source_{source}',
                    'GREEN' if good else 'ORANGE',
                    'present_in_fresh_snapshot' if good else 'missing_or_unavailable_in_fresh_snapshot',
                    latest_quarter,
                    {'entity_id': entity_id, 'state': (item or {}).get('state')},
                    verified=good,
                ))
            socket_good = any(
                entity_id.startswith('sensor.energy_socket_energy_import')
                and str((item or {}).get('state') or '').strip().lower() not in BAD_ENTITY_STATES
                for entity_id, item in entities.items()
            )
            checks.append(_check(
                'live_source_homewizard_sockets',
                'GREEN' if socket_good else 'ORANGE',
                'present_in_fresh_snapshot' if socket_good else 'missing_or_unavailable_in_fresh_snapshot',
                latest_quarter,
                verified=socket_good,
            ))

        month_key = _previous_month_key(now)
        year, month = month_key.split('_')
        closure_path = self.recovery_root / 'Status' / f'MonthClosure_{year}_{month}.json'
        closure = _read_json(closure_path)
        closure_ok = closure_status_is_deep_verified(closure)
        checks.append(_check(
            'previous_month_closure',
            'GREEN' if closure_ok else ('ORANGE' if closure is None else 'RED'),
            'closed_deep_verified' if closure_ok else 'missing_or_not_fully_verified',
            closure_path,
            {'month': month_key, 'status': (closure or {}).get('status')},
            verified=closure_ok,
        ))

        version_path = self.project_root / 'App' / 'VERSIE.txt'
        try:
            version = version_path.read_text(encoding='utf-8').strip() if version_path.is_file() else ''
        except OSError:
            version = ''
        checks.append(_check('production_version_source', 'GREEN' if version else 'ORANGE', 'available' if version else 'missing_or_empty', version_path, {'version': version or None}, verified=bool(version)))

        mode_path = self.project_root / 'Inbox' / 'operating_mode' / 'operating_mode_state.json'
        mode_data = _read_json(mode_path)
        mode = (mode_data or {}).get('effective_mode') or (mode_data or {}).get('base_mode') or (mode_data or {}).get('mode')
        valid_mode = isinstance(mode_data, dict) and mode in VALID_MODES
        checks.append(_check('operating_mode_source', 'GREEN' if valid_mode else 'RED', 'valid' if valid_mode else 'missing_or_invalid_mode', mode_path, {'effective_mode': mode}, verified=valid_mode))

        hold_path = self.project_root / 'Inbox' / 'operating_mode' / 'release_validation_hold.json'
        hold = _read_json(hold_path)
        hold_ok = isinstance(hold, dict) and hold.get('active') is False and hold.get('validation_status') == 'ok'
        checks.append(_check(
            'release_validation_hold', 'GREEN' if hold_ok else 'ORANGE',
            'released_ok' if hold_ok else 'missing_active_or_unvalidated', hold_path,
            {'active': (hold or {}).get('active'), 'validation_status': (hold or {}).get('validation_status')}, verified=hold_ok,
        ))

        cr_dir = self.project_root / 'Data' / '03_Systeem' / 'Projectmanager' / 'State'
        cr_files = sorted(cr_dir.glob('crash_recovery_closure_*.json')) if cr_dir.is_dir() else []
        cr_path = cr_files[-1] if cr_files else None
        cr_payload = _read_json(cr_path) if cr_path else None
        cr_result = evaluate_cr_closure(cr_payload)
        cr_age = _age_seconds(cr_path, now) if cr_path else None
        cr_fresh = cr_age is not None and cr_age <= 30 * 86400
        cr_status = cr_result['status']
        cr_reason = cr_result['reason']
        cr_strength = cr_result.get('evidence_strength', 'unverified')
        if cr_status == 'GREEN' and not cr_fresh:
            cr_status = 'ORANGE'
            cr_reason = 'three_domain_closure_is_old'
            cr_strength = 'partial'
        checks.append({
            'name': 'crash_recovery_closure',
            'status': cr_status,
            'reason': cr_reason,
            'evidence_ref': str(cr_path) if cr_path else None,
            'evidence_strength': cr_strength,
            'details': {**cr_result.get('details', {}), 'age_seconds': round(cr_age, 1) if cr_age is not None else None},
        })

        month_dir = self.input_root / month_key
        validation_path = month_dir / 'month_input_validation.json'
        validation = _read_json(validation_path)
        validation_ok = (
            isinstance(validation, dict)
            and validation.get('status') == 'completed'
            and not validation.get('missing_required')
            and not validation.get('empty_required')
        )
        checks.append(_check(
            'previous_month_import_pipeline', 'GREEN' if validation_ok else 'ORANGE',
            'completed' if validation_ok else 'missing_or_incomplete', validation_path,
            {'month': month_key, 'missing_required': (validation or {}).get('missing_required', [])}, verified=validation_ok,
        ))

        for filename, key in (
            ('P1e.csv', 'p1_electricity'),
            ('P1g.csv', 'p1_gas'),
            ('Enphase.csv', 'enphase'),
            ('NextEnergy actuele stroomprijs.csv', 'nextenergy_price'),
            ('Nordpool elektriciteit.csv', 'nordpool_price'),
        ):
            path = month_dir / filename
            try:
                good = path.is_file() and path.stat().st_size > 0
            except OSError:
                good = False
            checks.append(_check(
                f'previous_month_source_{key}', 'GREEN' if good else 'ORANGE',
                'available' if good else 'missing_or_empty', path, {'month': month_key}, verified=good,
            ))

        report_path = self.project_root / 'Data' / '02_Output' / 'Rapportages' / month_key / 'report_manifest.json'
        report = _read_json(report_path)
        report_ok = isinstance(report, dict) and report.get('status') == 'completed' and bool(report.get('files'))
        checks.append(_check(
            'previous_month_reporting', 'GREEN' if report_ok else 'ORANGE',
            'completed' if report_ok else 'missing_or_incomplete', report_path, {'month': month_key}, verified=report_ok,
        ))

        version = _runtime_version(self.project_root)
        project_cr_dir = self.recovery_root / 'CrashRecovery'
        project_all_zips = [path for path in project_cr_dir.glob('*.zip') if path.is_file()] if project_cr_dir.is_dir() else []
        project_pattern = _canonical_cr_regex(version, 'EnergieProject') if version else None
        project_canonical = [path for path in project_all_zips if project_pattern and project_pattern.fullmatch(path.name)]
        project_zip = max(project_canonical, key=lambda path: path.stat().st_mtime) if project_canonical else None
        if project_zip:
            stem = project_zip.with_suffix('')
            project_sha = Path(str(stem) + '.sha256')
            project_manifest = Path(str(stem) + '.manifest.json')
            project_restore = Path(str(stem) + '.restore.txt')
            project_set_ok = (
                project_manifest.is_file() and project_restore.is_file()
                and _sidecar_sha_matches(project_zip, project_sha)
            )
            project_age = _age_seconds(project_zip, now)
            project_fresh = (
                project_set_ok and len(project_all_zips) == 1
                and project_age is not None and project_age <= 30 * 86400
            )
        else:
            project_set_ok = False; project_age = None; project_fresh = False
        checks.append(_check(
            'project_crash_recovery_set', 'GREEN' if project_fresh else 'ORANGE',
            'one_canonical_complete_recent_set' if project_fresh else 'retention_canonical_set_incomplete_or_old',
            project_zip or project_cr_dir,
            {
                'zip_count': len(project_all_zips), 'canonical_count': len(project_canonical),
                'runtime_version': version,
                'age_seconds': round(project_age, 1) if project_age is not None else None,
                'complete_set': project_set_ok,
            },
            verified=project_fresh,
        ))

        nas_dir = self.recovery_root / 'NAS Container'
        nas_zips = [path for path in nas_dir.glob('*.zip') if path.is_file()] if nas_dir.is_dir() else []
        nas_pattern = _canonical_cr_regex(version, 'NAS Containers') if version else None
        nas_canonical = [path for path in nas_zips if nas_pattern and nas_pattern.fullmatch(path.name)]
        nas_zip = max(nas_canonical, key=lambda path: path.stat().st_mtime) if nas_canonical else None
        if nas_zip:
            nas_sha = Path(str(nas_zip) + '.sha256')
            verify = nas_zip.with_name(nas_zip.stem + ' VERIFY.txt')
            nas_age = _age_seconds(nas_zip, now)
            try:
                verify_text = verify.read_text(encoding='utf-8', errors='replace')
            except OSError:
                verify_text = ''
            nas_set_ok = (
                _sidecar_sha_matches(nas_zip, nas_sha)
                and all(marker in verify_text for marker in (
                    'NAS_CONTAINER_CR_ACCEPTANCE_OK',
                    'PRODUCTION_CONTAINERS_CHANGED=NO',
                    'NAS_CR_RETENTION_MAX1_OK',
                ))
            )
            nas_ok = (
                nas_set_ok and len(nas_zips) == 1
                and nas_age is not None and nas_age <= 30 * 86400
            )
        else:
            nas_age = None; nas_set_ok = False; nas_ok = False
        checks.append(_check(
            'nas_container_crash_recovery_retention', 'GREEN' if nas_ok else 'ORANGE',
            'one_canonical_complete_recent_set' if nas_ok else 'retention_canonical_set_incomplete_or_old', nas_zip or nas_dir,
            {
                'zip_count': len(nas_zips), 'canonical_count': len(nas_canonical),
                'runtime_version': version,
                'age_seconds': round(nas_age, 1) if nas_age is not None else None,
                'complete_set': nas_set_ok,
            },
            verified=nas_ok,
        ))

        try:
            usage = shutil.disk_usage(self.project_root)
            free_pct = (usage.free / usage.total * 100.0) if usage.total else 0.0
            storage_status = 'GREEN' if free_pct >= 10.0 else ('ORANGE' if free_pct >= 5.0 else 'RED')
            checks.append(_check(
                'project_storage_free_space', storage_status,
                'sufficient' if storage_status == 'GREEN' else 'low_free_space', self.project_root,
                {'free_bytes': usage.free, 'total_bytes': usage.total, 'free_pct': round(free_pct, 2)}, verified=storage_status == 'GREEN',
            ))
        except OSError as exc:
            checks.append(_check('project_storage_free_space', 'ORANGE', 'disk_usage_failed', self.project_root, {'error': str(exc)}, verified=False))

        # 32.4.25: expose project-structure debt and ngrok boundary safety as
        # read-only operational health.  These checks never move/delete files
        # and are deliberately non-release-prefixed so they cannot create a
        # circular release-acceptance dependency.
        checks.append(project_hygiene_check(self.project_root, keep_rollbacks=3))
        checks.append(ngrok_security_check(self.project_root))

        return checks
