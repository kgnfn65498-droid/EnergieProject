#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import control_plane_runtime_guard
import embedded_pm_runtime_guard

SCHEMA = 'energie_release_preflight_v1'
TERMINAL_TRANSITIONS = {'COMPLETE', 'ROLLED_BACK', 'CANCELLED'}
PM_STALE_SECONDS = 180.0


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_symlink():
            return None
        value = json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _numeric(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value).strip().split('.'))
    except (TypeError, ValueError):
        return ()


def _safe_member(name: str) -> bool:
    path = Path(name)
    return bool(name) and not path.is_absolute() and '..' not in path.parts and '\\' not in name


def _parse_manifest(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if '  ' not in line:
            raise ValueError('manifest line invalid')
        digest, name = line.split('  ', 1)
        digest = digest.strip().lower(); name = name.strip()
        if len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
            raise ValueError('manifest digest invalid')
        if not _safe_member(name) or name in result:
            raise ValueError('manifest path invalid or duplicate')
        result[name] = digest
    if not result:
        raise ValueError('manifest empty')
    return result


def _parse_sums(raw: str) -> dict[str, str]:
    data = json.loads(raw)
    rows = data.get('files') if isinstance(data, dict) else None
    if not isinstance(rows, list):
        raise ValueError('SHA256SUMS files invalid')
    result: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError('SHA256SUMS row invalid')
        name = str(row.get('path') or '')
        digest = str(row.get('sha256') or '').lower()
        if not _safe_member(name) or name in result:
            raise ValueError('SHA256SUMS path invalid or duplicate')
        if len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
            raise ValueError('SHA256SUMS digest invalid')
        result[name] = digest
    return result


def _verify_source_tree(app: Path) -> tuple[bool, str]:
    manifest_path = app / 'MANIFEST.sha256'
    sums_path = app / 'SHA256SUMS.json'
    try:
        if manifest_path.is_symlink() or sums_path.is_symlink():
            return False, ''
        manifest = _parse_manifest(manifest_path.read_text(encoding='utf-8'))
        sums = _parse_sums(sums_path.read_text(encoding='utf-8'))
        if sums != manifest:
            return False, _sha256(manifest_path)
        for name, expected in manifest.items():
            path = app / name
            if path.is_symlink() or not path.is_file() or _sha256(path) != expected:
                return False, _sha256(manifest_path)
        return True, _sha256(manifest_path)
    except Exception:
        return False, ''


def _verify_candidate(path: Path) -> dict[str, str]:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('candidate missing or unsafe')
    with zipfile.ZipFile(path, 'r') as zf:
        infos = zf.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise RuntimeError('candidate duplicate members')
        for info in infos:
            if not _safe_member(info.filename):
                raise RuntimeError('candidate unsafe member')
            mode = (info.external_attr >> 16) & 0o170000
            if mode == stat.S_IFLNK:
                raise RuntimeError('candidate symlink member')
        required = {'VERSIE.txt', 'MANIFEST.sha256', 'SHA256SUMS.json'}
        if not required.issubset(set(names)):
            raise RuntimeError('candidate metadata missing')
        if zf.getinfo('VERSIE.txt').file_size > 128:
            raise RuntimeError('candidate VERSIE.txt too large')
        version = zf.read('VERSIE.txt').decode('utf-8').strip()
        manifest_raw = zf.read('MANIFEST.sha256').decode('utf-8')
        sums_raw = zf.read('SHA256SUMS.json').decode('utf-8')
        manifest = _parse_manifest(manifest_raw)
        sums = _parse_sums(sums_raw)
        if sums != manifest:
            raise RuntimeError('candidate metadata maps differ')
        payload_names = {
            info.filename for info in infos
            if not info.is_dir() and info.filename not in {'MANIFEST.sha256', 'SHA256SUMS.json'}
        }
        if payload_names != set(manifest):
            raise RuntimeError('candidate manifest path set mismatch')
        for name, expected in manifest.items():
            if _sha_bytes(zf.read(name)) != expected:
                raise RuntimeError(f'candidate hash mismatch: {name}')
        return {
            'version': version,
            'artifact_sha256': _sha256(path),
            'manifest_sha256': _sha_bytes(manifest_raw.encode('utf-8')),
        }


def _parse_iso_epoch(value: Any) -> float | None:
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp()
    except (TypeError, ValueError):
        return None


def _pm_final_snapshot(root: Path, current_version: str, *, now: float) -> tuple[bool, dict | None]:
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    status = _read_json(runtime / 'status/current.json')
    audit = _read_json(runtime / 'self_audit/current.json')
    if not isinstance(status, dict) or not isinstance(audit, dict):
        return False, status
    generation = str(status.get('cycle_generation') or '').strip()
    status_prov = status.get('provenance') if isinstance(status.get('provenance'), dict) else {}
    audit_prov = audit.get('provenance') if isinstance(audit.get('provenance'), dict) else {}
    status_epoch = _parse_iso_epoch(status.get('updated_at'))
    audit_epoch = _parse_iso_epoch(audit.get('status_updated_at'))
    if status_epoch is None or audit_epoch is None:
        return False, status
    fresh = max(0.0, float(now) - min(status_epoch, audit_epoch)) <= PM_STALE_SECONDS
    ok = bool(
        generation and fresh
        and str(((status.get('release') or {}).get('version')) or '').strip() == current_version
        and status_prov.get('generation') == generation
        and status_prov.get('phase') == 'FINAL'
        and str(audit.get('status') or '').upper() == 'GREEN'
        and str(audit.get('cycle_generation') or '') == generation
        and audit_prov.get('generation') == generation
        and audit_prov.get('phase') == 'FINAL'
        and str(audit.get('status_updated_at') or '') == str(status.get('updated_at') or '')
    )
    return ok, status


def _health_green(status: dict | None, name: str) -> bool:
    checks = ((status or {}).get('health') or {}).get('checks') or []
    return any(isinstance(item, dict) and item.get('name') == name and item.get('status') == 'GREEN' for item in checks)


def _command_ingress_clean(root: Path) -> bool:
    directory = root / 'Data/03_Systeem/Projectmanager/CommandIngress'
    runtime_commands = root / 'Inbox/projectmanager_v2/RuntimeV2/commands'
    receipts = _read_json(runtime_commands / 'ingress_receipts.json')
    queue = _read_json(runtime_commands / 'queue.json')
    if not directory.is_dir() or directory.is_symlink() or not isinstance(receipts, dict) or not isinstance(queue, dict):
        return False
    items = receipts.get('items'); queue_items = queue.get('items')
    if not isinstance(items, dict) or not isinstance(queue_items, list):
        return False
    by_id = {str(row.get('id') or ''): row for row in queue_items if isinstance(row, dict) and row.get('id')}
    for path in directory.glob('*.json'):
        if path.is_symlink() or not path.is_file():
            return False
        ingress_id = path.stem
        receipt = items.get(ingress_id)
        if not isinstance(receipt, dict):
            return False
        status = str(receipt.get('status') or '')
        if status == 'REJECTED':
            continue
        if status != 'IMPORTED':
            return False
        command_id = str(receipt.get('command_id') or '')
        command = by_id.get(command_id)
        if not isinstance(command, dict) or str(command.get('ingress_id') or '') != ingress_id:
            return False
    return True


def _has_stale_release_task(root: Path, current_version: str) -> bool:
    data = _read_json(root/'Inbox/projectmanager_v2/RuntimeV2/state/tasks.json')
    if not isinstance(data, dict) or not isinstance(data.get('tasks'), list):
        return True
    current = _numeric(current_version)
    active = {'ACTIVE', 'BLOCKED', 'WAITING_APPROVAL'}
    for task in data['tasks']:
        if not isinstance(task, dict) or task.get('status') not in active:
            continue
        owner = str(task.get('release_owner') or '').strip()
        if not owner:
            metadata = task.get('build_metadata') if isinstance(task.get('build_metadata'), dict) else {}
            owner = str(metadata.get('release_version') or '').strip()
        if owner and _numeric(owner) and _numeric(owner) <= current:
            return True
    return False


def probe(project_root: Path | str, candidate: Path | str, *, now: float | None = None) -> dict[str, Any]:
    root = Path(project_root).resolve()
    candidate_path = Path(candidate)
    current_time = float(time.time() if now is None else now)
    blockers: list[str] = []
    try:
        current_version = (root/'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    except OSError:
        current_version = ''
        blockers.append('current_version_missing')

    source_ok, current_manifest_sha = _verify_source_tree(root/'App')
    if not source_ok:
        blockers.append('current_source_integrity_invalid')

    incoming = root/'Inbox/incoming'
    processing = root/'Inbox/processing'
    incoming_files = sorted(path for path in incoming.glob('*.zip') if path.is_file() and not path.is_symlink()) if incoming.is_dir() else []
    processing_files = sorted(path for path in processing.glob('*.zip') if path.is_file() and not path.is_symlink()) if processing.is_dir() else []
    candidate_abs = candidate_path.absolute()
    if len(incoming_files) != 1 or incoming_files[0].absolute() != candidate_abs:
        blockers.append('incoming_not_exact_single_candidate')
    if processing_files:
        blockers.append('processing_not_empty')
    if (root/'Inbox/.installer.lock').exists():
        blockers.append('installer_not_idle')

    candidate_version = ''
    candidate_sha = ''
    candidate_manifest_sha = ''
    try:
        verified = _verify_candidate(candidate_path)
        candidate_version = verified['version']
        candidate_sha = verified['artifact_sha256']
        candidate_manifest_sha = verified['manifest_sha256']
    except Exception:
        blockers.append('candidate_integrity_invalid')
    if not current_version or not candidate_version or _numeric(candidate_version) <= _numeric(current_version):
        blockers.append('candidate_version_not_newer')

    mode = _read_json(root/'Inbox/operating_mode/operating_mode_state.json') or {}
    if not (
        str(mode.get('base_mode') or '').upper() == 'DEVELOPMENT'
        and str(mode.get('effective_mode') or '').upper() == 'DEVELOPMENT'
        and str(mode.get('reconciliation_status') or '') == 'ok'
        and not (mode.get('drift') or [])
    ):
        blockers.append('operating_mode_not_clean_development')

    hold = _read_json(root/'Inbox/operating_mode/release_validation_hold.json') or {}
    if not (hold.get('active') is False and str(hold.get('validation_status') or '') == 'ok'):
        blockers.append('previous_release_hold_not_settled')

    atomic = _read_json(root/'Inbox/atomic_app_swap_state.json') or {}
    if not (
        str(atomic.get('state') or '').upper() in {'ACCEPTED','ROLLED_BACK'}
        and str(atomic.get('to_version') or '') == current_version
    ):
        blockers.append('previous_atomic_not_settled')

    transition = _read_json(root/'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json')
    if _numeric(current_version) >= (32,4,54):
        if not isinstance(transition, dict) or str(transition.get('lifecycle_state') or '').upper() not in TERMINAL_TRANSITIONS or str(transition.get('to_release') or '') != current_version:
            blockers.append('previous_transition_not_terminal')

    pm_ok, pm_status = _pm_final_snapshot(root, current_version, now=current_time)
    if not pm_ok:
        blockers.append('projectmanager_final_snapshot_invalid')
    if not _health_green(pm_status, 'release_watcher'):
        blockers.append('watcher_runtime_not_green')
    if not _health_green(pm_status, 'watcher_container_contract'):
        blockers.append('watcher_contract_not_green')
    if not _health_green(pm_status, 'native_mcp_runtime'):
        blockers.append('native_mcp_runtime_not_green')
    if _numeric(current_version) >= (32,4,55) and not _health_green(pm_status, 'command_ingress_consumer'):
        blockers.append('command_ingress_consumer_not_green')

    watcher = _read_json(root/'Inbox/watcher_container_contract.json') or {}
    if not (watcher.get('status') == 'GREEN' and watcher.get('ready') is True):
        blockers.append('watcher_contract_not_green')

    native = _read_json(root/'Inbox/native_mcp_runtime/runtime_guard.json') or {}
    if not (
        native.get('status') == 'GREEN' and native.get('ready') is True
        and native.get('expected_fingerprint') == native.get('runtime_fingerprint')
    ):
        blockers.append('native_mcp_runtime_not_green')

    cp = control_plane_runtime_guard.probe(root, now=current_time, stale_seconds=30)
    if cp.get('ready') is not True:
        blockers.append('control_plane_runtime_not_green')

    embedded = embedded_pm_runtime_guard.probe(root, now=current_time, stale_seconds=PM_STALE_SECONDS)
    if embedded.get('ready') is not True:
        blockers.append('embedded_pm_runtime_not_green')

    if not _command_ingress_clean(root):
        blockers.append('command_ingress_unconsumed')
    if _has_stale_release_task(root, current_version):
        blockers.append('stale_release_owned_task')

    return {
        'schema': SCHEMA,
        'status': 'GREEN' if not blockers else 'BLOCKED',
        'ready': not blockers,
        'blockers': sorted(set(blockers)),
        'current_version': current_version,
        'current_manifest_sha256': current_manifest_sha or None,
        'current_source_integrity': 'GREEN' if source_ok else 'RED',
        'candidate_version': candidate_version,
        'candidate_sha256': candidate_sha or None,
        'candidate_manifest_sha256': candidate_manifest_sha or None,
        'candidate_integrity': 'GREEN' if candidate_sha and candidate_manifest_sha else 'RED',
        'candidate': str(candidate_abs),
        'control_plane': cp,
        'embedded_pm': embedded,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Read-only N+1 release preflight')
    parser.add_argument('--root', required=True)
    parser.add_argument('--candidate', required=True)
    args = parser.parse_args()
    result = probe(Path(args.root), Path(args.candidate))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get('ready') else 3


if __name__ == '__main__':
    raise SystemExit(main())
