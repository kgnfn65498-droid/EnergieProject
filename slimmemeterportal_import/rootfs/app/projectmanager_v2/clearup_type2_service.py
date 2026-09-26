from __future__ import annotations
from system_path_contract import project_system_path

import base64
import hashlib
import json
import os
import re
import secrets
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

AFFIRMATIVE = {'akkoord', 'ja', 'yes', 'approve', 'goedgekeurd', 'goedkeuren', 'ontvangen', 'bevestigd', 'confirmed'}
CLEARUP_ID_RE = re.compile(r'^ClearUp_[0-9]{3,}$')
PLAN_SCHEMA = 'energie_clearup_type2_plan_v1'
TYPE2_REQUEST_SCHEMA = 'energie_clearup_type2_request_v1'
TYPE2_RESULT_SCHEMA = 'energie_clearup_type2_result_v1'
PLAN_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Plans')
STAGING_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Staging')
EXPORT_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Exports')
STATE_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/State')
VALIDATION_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Validation')
EXTERNAL_GATE_REL = STATE_ROOT_REL / 'TYPE2_EXTERNAL_RECOVERY_GATE.json'
TYPE2_REQUIRED_IDS = tuple(f'ClearUp_{i:03d}' for i in range(2, 13))
WATCHER_REQUEST_REL = Path('Inbox/project_clearup_move_request.json')
WATCHER_RESULT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Runtime/project_clearup_move_result.json')
WATCHER_TIMEOUT_SECONDS = 90.0
MAX_EXPORT_CHUNK = 32768
PROTECTED_SOURCE_PREFIXES = (
    'Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed',
)
ALLOWED_SOURCE_PREFIXES = ('Inbox/',)
ALLOWED_DEST_PREFIXES = ('Data/03_Systeem/',)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _json_sha(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def _token(text: str) -> str:
    return ' '.join(str(text or '').strip().lower().strip(' .,!?:;').split())


def _safe_relative(value: str) -> str:
    text = str(value or '').strip().replace('\\', '/')
    p = Path(text)
    if not text or p.is_absolute() or '..' in p.parts or text.startswith('/'):
        raise RuntimeError(f'unsafe relative path: {value!r}')
    return p.as_posix()


def _safe(root: Path, rel: str) -> Path:
    rel = _safe_relative(rel)
    p = (root / rel).resolve()
    if p == root or root not in p.parents:
        raise RuntimeError('unsafe Type2 path')
    return p


def _release_idle(root: Path) -> None:
    current = project_system_path(root, 'Inbox/release_controller/current.json')
    if not current.is_file():
        raise RuntimeError('release controller state missing; Type2 blocked')
    try:
        state = json.loads(current.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError('release controller state unreadable') from exc
    if str(state.get('status') or '').upper() != 'COMPLETE' or str(state.get('phase') or '').upper() != 'COMPLETE':
        raise RuntimeError('release controller not COMPLETE; Type2 blocked')
    processing = root / 'Inbox/processing'
    if processing.is_dir() and any(p.is_file() and p.name.startswith('EnergieProject_v') and p.suffix == '.zip' for p in processing.iterdir()):
        raise RuntimeError('release processing active; Type2 blocked')


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = [int(x) for x in re.findall(r'\d+', str(value))]
    return tuple(parts[:4]) or (0,)


def _plan_path(root: Path, clearup_id: str) -> Path:
    if not CLEARUP_ID_RE.fullmatch(clearup_id):
        raise RuntimeError('invalid Type2 clearup_id')
    external = root / PLAN_ROOT_REL / f'{clearup_id}.json'
    if external.is_file() and not external.is_symlink():
        return external
    bundled = root / 'App/tools/clearup_type2_plans' / f'{clearup_id}.json'
    return bundled


def _load_plan(root: Path, clearup_id: str) -> dict[str, Any]:
    path = _plan_path(root, clearup_id)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError(f'Type2 plan missing/unsafe: {clearup_id}')
    try:
        plan = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError('Type2 plan unreadable') from exc
    if not isinstance(plan, dict) or plan.get('schema') != PLAN_SCHEMA:
        raise RuntimeError('Type2 plan schema invalid')
    if str(plan.get('clearup_id') or '') != clearup_id or str(plan.get('classification') or '').upper() != 'TYPE2':
        raise RuntimeError('Type2 plan identity mismatch')
    if str(plan.get('status') or '').upper() != 'READY':
        raise RuntimeError('Type2 plan is not READY')
    min_release = str(plan.get('minimum_release') or '32.5.7')
    active = (root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    if _version_tuple(active) < _version_tuple(min_release):
        raise RuntimeError(f'Type2 plan requires release >= {min_release}')
    items = plan.get('items')
    if not isinstance(items, list) or not items:
        raise RuntimeError('Type2 plan items missing')
    normalized = []
    seen_src: set[str] = set(); seen_dst: set[str] = set()
    for raw in items:
        if not isinstance(raw, dict):
            raise RuntimeError('Type2 plan item invalid')
        source = _safe_relative(str(raw.get('source') or ''))
        destination = _safe_relative(str(raw.get('destination') or ''))
        if not source.startswith(ALLOWED_SOURCE_PREFIXES) or source.startswith(PROTECTED_SOURCE_PREFIXES):
            raise RuntimeError(f'Type2 source outside bounded Inbox scope: {source}')
        if not destination.startswith(ALLOWED_DEST_PREFIXES):
            raise RuntimeError(f'Type2 destination outside system scope: {destination}')
        if source in seen_src or destination in seen_dst or source == destination:
            raise RuntimeError('Type2 plan contains duplicate/conflicting paths')
        seen_src.add(source); seen_dst.add(destination)
        checks = raw.get('contract_checks')
        if not isinstance(checks, list) or not checks:
            raise RuntimeError(f'Type2 item requires contract_checks: {source}')
        normalized_checks = []
        for check in checks:
            if not isinstance(check, dict):
                raise RuntimeError('Type2 contract check invalid')
            path = _safe_relative(str(check.get('path') or ''))
            must_contain = [str(x) for x in (check.get('must_contain') or []) if str(x)]
            must_not_contain = [str(x) for x in (check.get('must_not_contain') or []) if str(x)]
            if not must_contain and not must_not_contain:
                raise RuntimeError('Type2 contract check must assert content')
            normalized_checks.append({'path': path, 'must_contain': must_contain, 'must_not_contain': must_not_contain})
        runtime_proof_paths = [_safe_relative(str(x)) for x in (raw.get('runtime_proof_paths') or []) if str(x).strip()]
        normalized.append({
            'source': source,
            'destination': destination,
            'reason': str(raw.get('reason') or '').strip(),
            'optional': raw.get('optional') is True,
            'path_key': str(raw.get('path_key') or '').strip(),
            'runtime_proof_paths': runtime_proof_paths,
            'contract_checks': normalized_checks,
        })
    plan = dict(plan)
    plan['minimum_release'] = min_release
    plan['items'] = normalized
    plan['plan_sha256'] = _json_sha({k: v for k, v in plan.items() if k != 'plan_sha256'})
    return plan


def _contract_checks(root: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    results = []
    for item in plan['items']:
        for check in item['contract_checks']:
            path = _safe(root, check['path'])
            if path.is_symlink() or not path.is_file():
                raise RuntimeError(f'Type2 contract file missing/unsafe: {check["path"]}')
            try:
                text = path.read_text(encoding='utf-8')
            except Exception as exc:
                raise RuntimeError(f'Type2 contract file unreadable: {check["path"]}') from exc
            for needle in check['must_contain']:
                if needle not in text:
                    raise RuntimeError(f'Type2 contract missing required reference {needle!r} in {check["path"]}')
            for needle in check['must_not_contain']:
                if needle in text:
                    raise RuntimeError(f'Type2 contract still contains old reference {needle!r} in {check["path"]}')
            results.append({'path': check['path'], 'sha256': _sha(path)})
    return results


def _snapshot_release_dirs(root: Path) -> dict[str, list[dict[str, Any]]]:
    # JSON-canonical representation: watcher requests round-trip through JSON,
    # therefore tuples are forbidden here.  All four release mailboxes are
    # protected, not only incoming/processing.
    result: dict[str, list[dict[str, Any]]] = {}
    for rel in ('Inbox/incoming', 'Inbox/processing', 'Inbox/processed', 'Inbox/failed'):
        base = root / rel
        rows: list[dict[str, Any]] = []
        if base.is_dir():
            for p in sorted(base.rglob('*')):
                if p.is_symlink():
                    raise RuntimeError(f'release mailbox symlink refused: {p}')
                if p.is_file():
                    rows.append({'path': p.relative_to(base).as_posix(), 'size': p.stat().st_size, 'sha256': _sha(p)})
        result[rel] = rows
    return result


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f'unsafe request/result path: {path}')
    tmp = path.with_name(f'.{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}')
    try:
        with tmp.open('x', encoding='utf-8') as h:
            json.dump(payload, h, ensure_ascii=False, indent=2, sort_keys=True)
            h.write('\n'); h.flush(); os.fsync(h.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _watcher_call(root: Path, *, operation: str, clearup_id: str, plan: dict[str, Any], explicit_user_text: str = '', validation_proof: dict[str, Any] | None = None) -> dict[str, Any]:
    request_path = root / WATCHER_REQUEST_REL; result_path = project_system_path(root, str(WATCHER_RESULT_REL))
    if request_path.exists():
        raise RuntimeError('ClearUp watcher request already active')
    request_id = secrets.token_hex(16)
    payload = {
        'schema': TYPE2_REQUEST_SCHEMA,
        'request_id': request_id,
        'operation': operation,
        'clearup_id': clearup_id,
        'release_version': (root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip(),
        'created_at': datetime.now(timezone.utc).isoformat(),
        'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=WATCHER_TIMEOUT_SECONDS + 15.0)).isoformat(),
        'plan_sha256': plan['plan_sha256'],
        'explicit_user_approval': _token(explicit_user_text) in AFFIRMATIVE,
        'mailbox_snapshot_before': _snapshot_release_dirs(root),
        'result_path': result_path.relative_to(root).as_posix(),
    }
    if validation_proof is not None:
        payload['validation_proof'] = validation_proof
    _atomic_json(request_path, payload)
    def _matching_result() -> dict[str, Any] | None:
        if not result_path.is_file():
            return None
        try:
            response = json.loads(result_path.read_text(encoding='utf-8'))
        except Exception:
            return None
        if not isinstance(response, dict) or response.get('request_id') != request_id:
            return None
        if response.get('schema') != TYPE2_RESULT_SCHEMA:
            raise RuntimeError('Type2 watcher result schema mismatch')
        if response.get('status') != 'completed':
            raise RuntimeError('Type2 watcher operation failed: ' + str(response.get('error') or response.get('status')))
        result = response.get('result')
        if not isinstance(result, dict):
            raise RuntimeError('Type2 watcher result missing')
        return result

    deadline = time.monotonic() + WATCHER_TIMEOUT_SECONDS
    try:
        while time.monotonic() < deadline:
            result = _matching_result()
            if result is not None:
                return result
            time.sleep(0.25)
        # Close the watcher/PM deadline-edge race for the exact same request-id.
        grace_deadline = time.monotonic() + 10.0
        while time.monotonic() < grace_deadline:
            result = _matching_result()
            if result is not None:
                return result
            time.sleep(0.25)
        raise RuntimeError('Type2 watcher operation timeout')
    finally:
        try:
            if request_path.is_file():
                current = json.loads(request_path.read_text(encoding='utf-8'))
                if current.get('request_id') == request_id:
                    request_path.unlink(missing_ok=True)
        except Exception:
            pass


def prepare_type2(project_root: Path | str, *, clearup_id: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if source != 'mcp_remote':
        raise RuntimeError('Type2 prepare requires chat/MCP request')
    _release_idle(root)
    plan = _load_plan(root, clearup_id)
    result = _watcher_call(root, operation='type2_prepare', clearup_id=clearup_id, plan=plan)
    result.update({'status': 'GREEN', 'clearup_id': clearup_id, 'plan_sha256': plan['plan_sha256'], 'contract_checks_required_before_migration': True, 'deletion_performed': False})
    return result


def refresh_recovery_type2(project_root: Path | str, *, clearup_id: str, source: str) -> dict[str, Any]:
    """Rebuild recovery evidence non-destructively in PREPARED or migrated state."""
    root = Path(project_root).resolve()
    if source != 'mcp_remote':
        raise RuntimeError('Type2 recovery refresh requires chat/MCP request')
    _release_idle(root)
    plan = _load_plan(root, clearup_id)
    state_path = root / STATE_ROOT_REL / f'{clearup_id}.json'
    try:
        state = json.loads(state_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError('Type2 recovery refresh requires existing state') from exc
    if not isinstance(state, dict) or state.get('plan_sha256') != plan['plan_sha256']:
        raise RuntimeError('Type2 recovery refresh requires matching state')

    phase = str(state.get('phase') or '')
    if phase == 'PREPARED':
        if state.get('status') != 'GREEN' or state.get('deletion_performed') is not False:
            raise RuntimeError('Type2 prepared recovery refresh requires GREEN pre-migrate state')
        result = _watcher_call(root, operation='type2_refresh_recovery', clearup_id=clearup_id, plan=plan)
        path, _manifest = _verify_export(root, clearup_id, plan)
        result.update({
            'status': 'GREEN', 'clearup_id': clearup_id, 'plan_sha256': plan['plan_sha256'],
            'artifact': path.name, 'size': path.stat().st_size, 'sha256': _sha(path),
            'prepared_recovery_refresh': True, 'post_migrate_recovery_refresh': False,
            'deletion_performed': False,
        })
        return result

    if phase != 'MIGRATED_PENDING_VALIDATION':
        raise RuntimeError('Type2 recovery refresh requires PREPARED or matching migrated state')
    if state.get('source_preserved') is not True or state.get('deletion_performed') is not False:
        raise RuntimeError('Type2 recovery refresh requires preserved pre-delete source')

    validation_path = root / VALIDATION_ROOT_REL / f'{clearup_id}.json'
    try:
        validation = json.loads(validation_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError('Type2 migrated recovery refresh requires validated state') from exc
    if (
        not isinstance(validation, dict)
        or validation.get('schema') != 'energie_clearup_type2_validation_v2'
        or validation.get('status') != 'GREEN'
        or validation.get('plan_sha256') != plan['plan_sha256']
        or list(validation.get('failures') or [])
    ):
        raise RuntimeError('Type2 recovery refresh requires GREEN matching validation')
    result = _watcher_call(root, operation='type2_refresh_recovery', clearup_id=clearup_id, plan=plan)
    path, _manifest = _verify_export(root, clearup_id, plan)
    result.update({
        'status': 'GREEN', 'clearup_id': clearup_id, 'plan_sha256': plan['plan_sha256'],
        'artifact': path.name, 'size': path.stat().st_size, 'sha256': _sha(path),
        'post_migrate_recovery_refresh': True, 'prepared_recovery_refresh': False,
        'deletion_performed': False,
    })
    return result


def _verify_export(root: Path, clearup_id: str, plan: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    path = root / EXPORT_ROOT_REL / f'{clearup_id}_Type2_recovery.zip'
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Type2 recovery ZIP missing/unsafe')
    try:
        with zipfile.ZipFile(path) as z:
            bad = z.testzip()
            if bad:
                raise RuntimeError(f'Type2 recovery ZIP corrupt: {bad}')
            manifest = json.loads(z.read('TYPE2_MANIFEST.json'))
    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:
        raise RuntimeError('Type2 recovery ZIP verification failed') from exc
    if not isinstance(manifest, dict) or manifest.get('clearup_id') != clearup_id or manifest.get('plan_sha256') != plan['plan_sha256']:
        raise RuntimeError('Type2 recovery ZIP belongs to another/stale plan')
    active_release = (root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    strict_manifest = _version_tuple(active_release) >= (32, 5, 15)
    if strict_manifest and (
        manifest.get('schema') != 'energie_clearup_type2_recovery_v1'
        or manifest.get('classification') != 'TYPE2'
        or manifest.get('deletion_performed') is not False
    ):
        raise RuntimeError('Type2 recovery ZIP manifest contract invalid')
    if not strict_manifest:
        if manifest.get('schema') not in (None, 'energie_clearup_type2_recovery_v1'):
            raise RuntimeError('Type2 recovery ZIP manifest schema invalid')
        if manifest.get('classification') not in (None, 'TYPE2'):
            raise RuntimeError('Type2 recovery ZIP manifest classification invalid')
        if manifest.get('deletion_performed') not in (None, False):
            raise RuntimeError('Type2 recovery ZIP is not pre-delete')
    try:
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            for item in manifest.get('items') or []:
                rows = item.get('source_rows') if isinstance(item, dict) else None
                if not isinstance(rows, list):
                    raise RuntimeError('Type2 recovery manifest source_rows missing')
                for row in rows:
                    if not isinstance(row, dict) or row.get('type') != 'file':
                        continue
                    member = 'original/' + str(row.get('path') or '')
                    if member not in names:
                        raise RuntimeError(f'Type2 recovery ZIP payload missing: {member}')
                    data = z.read(member)
                    if len(data) != int(row.get('size') if row.get('size') is not None else -1):
                        raise RuntimeError(f'Type2 recovery ZIP payload size mismatch: {member}')
                    if hashlib.sha256(data).hexdigest() != str(row.get('sha256') or ''):
                        raise RuntimeError(f'Type2 recovery ZIP payload hash mismatch: {member}')
    except (OSError, zipfile.BadZipFile, KeyError) as exc:
        raise RuntimeError('Type2 recovery ZIP deep verification failed') from exc
    return path, manifest


def export_info(project_root: Path | str, *, clearup_id: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if source != 'mcp_remote':
        raise RuntimeError('Type2 export info requires chat/MCP request')
    plan = _load_plan(root, clearup_id)
    path, manifest = _verify_export(root, clearup_id, plan)
    return {'status': 'GREEN', 'clearup_id': clearup_id, 'artifact': path.name, 'size': path.stat().st_size, 'sha256': _sha(path), 'plan_sha256': plan['plan_sha256'], 'item_count': len(manifest.get('items') or [])}


def export_chunk(project_root: Path | str, *, clearup_id: str, offset: int, max_bytes: int, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if source != 'mcp_remote':
        raise RuntimeError('Type2 export chunk requires chat/MCP request')
    if type(offset) is not int or offset < 0:
        raise RuntimeError('offset must be non-negative integer')
    if type(max_bytes) is not int or max_bytes < 1 or max_bytes > MAX_EXPORT_CHUNK:
        raise RuntimeError(f'max_bytes must be 1..{MAX_EXPORT_CHUNK}')
    info = export_info(root, clearup_id=clearup_id, source=source)
    path = root / EXPORT_ROOT_REL / info['artifact']
    total = path.stat().st_size
    if offset > total:
        raise RuntimeError('offset beyond EOF')
    with path.open('rb') as f:
        f.seek(offset); data = f.read(max_bytes)
    nxt = offset + len(data)
    return {**info, 'offset': offset, 'bytes': len(data), 'next_offset': nxt, 'eof': nxt >= total, 'chunk_sha256': hashlib.sha256(data).hexdigest(), 'base64': base64.b64encode(data).decode('ascii')}


def _verified_required_exports(root: Path) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    for required_id in TYPE2_REQUIRED_IDS:
        required_plan = _load_plan(root, required_id)
        path, manifest = _verify_export(root, required_id, required_plan)
        verified.append({
            'clearup_id': required_id,
            'artifact': path.name,
            'size': path.stat().st_size,
            'sha256': _sha(path),
            'plan_sha256': required_plan['plan_sha256'],
            'item_count': len(manifest.get('items') or []),
        })
    return verified


def _load_external_gate(root: Path) -> dict[str, Any]:
    path = root / EXTERNAL_GATE_REL
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Type2 external recovery gate missing/unsafe')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError('Type2 external recovery gate unreadable') from exc
    if not isinstance(value, dict):
        raise RuntimeError('Type2 external recovery gate invalid')
    return value


def _assert_external_recovery_confirmed(root: Path) -> dict[str, Any]:
    try:
        active = (root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    except OSError as exc:
        raise RuntimeError('active release unreadable for Type2 external gate') from exc
    if _version_tuple(active) < (32, 5, 16):
        return {'status': 'LEGACY_PRE_32_5_16', 'delete_allowed': True}
    gate = _load_external_gate(root)
    if gate.get('status') != 'EXTERNAL_COPY_CONFIRMED' or gate.get('delete_allowed') is not True:
        raise RuntimeError('Type2 finalize blocked until external recovery copy is explicitly confirmed')
    confirmed = gate.get('confirmed_exports')
    if not isinstance(confirmed, list) or len(confirmed) != len(TYPE2_REQUIRED_IDS):
        raise RuntimeError('Type2 external recovery confirmation set incomplete')
    by_id = {str(row.get('clearup_id') or ''): row for row in confirmed if isinstance(row, dict)}
    current = _verified_required_exports(root)
    for row in current:
        prior = by_id.get(row['clearup_id'])
        if not isinstance(prior, dict):
            raise RuntimeError(f"Type2 external recovery confirmation missing: {row['clearup_id']}")
        if prior.get('artifact') != row['artifact'] or prior.get('size') != row['size'] or prior.get('sha256') != row['sha256']:
            raise RuntimeError(f"Type2 recovery artifact changed after external confirmation: {row['clearup_id']}")
    return gate


def confirm_external_recovery_type2(project_root: Path | str, *, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if source != 'mcp_remote' or _token(explicit_user_text) not in AFFIRMATIVE:
        raise RuntimeError('explicit user confirmation missing for Type2 external recovery')
    _release_idle(root)
    verified = _verified_required_exports(root)
    anchor_plan = _load_plan(root, TYPE2_REQUIRED_IDS[0])
    result = _watcher_call(
        root, operation='type2_external_recovery_confirm', clearup_id=TYPE2_REQUIRED_IDS[0],
        plan=anchor_plan, explicit_user_text=explicit_user_text,
    )
    gate = _assert_external_recovery_confirmed(root)
    return {
        **result, 'status': 'GREEN', 'confirmed': True, 'delete_allowed': True,
        'verified_count': len(verified), 'confirmed_at': gate.get('confirmed_at'),
    }


def migrate_type2(project_root: Path | str, *, clearup_id: str, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if source != 'mcp_remote' or _token(explicit_user_text) not in AFFIRMATIVE:
        raise RuntimeError('explicit user approval missing for Type2 migration')
    _release_idle(root)
    plan = _load_plan(root, clearup_id)
    _verify_export(root, clearup_id, plan)
    checks = _contract_checks(root, plan)
    result = _watcher_call(root, operation='type2_migrate', clearup_id=clearup_id, plan=plan, explicit_user_text=explicit_user_text)
    return {**result, 'status': 'GREEN', 'clearup_id': clearup_id, 'plan_sha256': plan['plan_sha256'], 'contract_checks': checks, 'deletion_performed': False}


def _tree_rows_for_validation(root: Path, base: Path) -> list[dict[str, Any]]:
    if not base.exists() or base.is_symlink():
        raise RuntimeError(f'Type2 validation path missing/unsafe: {base}')
    out=[]
    seq=[base] if base.is_file() else [base,*sorted(base.rglob('*'))]
    for q in seq:
        if q.is_symlink():
            raise RuntimeError(f'Type2 validation symlink refused: {q}')
        rel=q.relative_to(root).as_posix()
        if q.is_file(): out.append({'path':rel,'type':'file','size':q.stat().st_size,'sha256':_sha(q)})
        elif q.is_dir(): out.append({'path':rel,'type':'directory'})
    return out


def _baseline_paths_present(destination_rows: list[dict[str, Any]], baseline_rows: list[dict[str, Any]], source: str, destination: str) -> bool:
    got={row['path']:row for row in destination_rows}
    for row in baseline_rows:
        suffix=Path(row['path']).relative_to(source).as_posix() if row['path'] != source else '.'
        dest_path=destination if suffix=='.' else f'{destination}/{suffix}'
        candidate=got.get(dest_path)
        if not candidate or candidate.get('type') != row.get('type'):
            return False
    return True


def validate_type2(project_root: Path | str, *, clearup_id: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if source != 'mcp_remote':
        raise RuntimeError('Type2 validate requires chat/MCP request')
    _release_idle(root)
    plan = _load_plan(root, clearup_id)
    _verify_export(root, clearup_id, plan)
    _contract_checks(root, plan)
    state_path = root / STATE_ROOT_REL / f'{clearup_id}.json'
    try:
        state = json.loads(state_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError('Type2 migrated state missing/unreadable') from exc
    if not isinstance(state, dict) or state.get('phase') != 'MIGRATED_PENDING_VALIDATION' or state.get('plan_sha256') != plan['plan_sha256']:
        raise RuntimeError('Type2 validate requires matching migrated state')
    cutover = state.get('cutover_rows') or {}
    activated_at=float(state.get('activated_at_epoch') or 0.0)
    if not isinstance(cutover,dict) or not cutover or activated_at <= 0:
        raise RuntimeError('Type2 cutover evidence missing')

    # First prove that every mapping resolves to its destination and that the
    # destination still contains every path present at cutover.  File contents
    # may legitimately change after cutover; path loss may not.
    checks=[]; failures=[]
    source_before={}
    for item in plan['items']:
        src=root/item['source']; dst=root/item['destination']
        if not src.exists() or src.is_symlink(): failures.append(f"source_missing:{item['source']}"); continue
        if not dst.exists() or dst.is_symlink(): failures.append(f"destination_missing:{item['destination']}"); continue
        key=str(item.get('path_key') or '').strip()
        if key:
            marker=root/Path('Data/03_Systeem/Projectmanager/ClearUp/PathActivation')/f'{key}.json'
            try: m=json.loads(marker.read_text(encoding='utf-8'))
            except Exception: m={}
            if not isinstance(m,dict) or m.get('active') is not True or m.get('plan_sha256') != plan['plan_sha256'] or m.get('destination') != item['destination']:
                failures.append(f'activation_missing:{key}')
            if project_system_path(root,item['source']).resolve() != dst.resolve():
                failures.append(f'active_path_not_destination:{key}')
        src_rows=_tree_rows_for_validation(root,src)
        dst_rows=_tree_rows_for_validation(root,dst)
        baseline=cutover.get(item['source'])
        if not isinstance(baseline,list) or not _baseline_paths_present(dst_rows,baseline,item['source'],item['destination']):
            failures.append(f'cutover_paths_missing:{item["destination"]}')
        source_before[item['source']]=src_rows
        checks.append({'source':item['source'],'destination':item['destination'],'path_key':key or None,
                       'source_rows_sha256':_json_sha(src_rows),'destination_rows_sha256':_json_sha(dst_rows)})

    if failures:
        status='RED'
    else:
        # Old source must be quiescent after path activation.  This detects a
        # stale writer before destructive finalization.
        quiet=max(0.05,float(os.environ.get('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS','2.0')))
        time.sleep(quiet)
        for item in plan['items']:
            src=root/item['source']
            now=_tree_rows_for_validation(root,src)
            if now != source_before[item['source']]:
                failures.append(f'old_source_still_mutating:{item["source"]}')

        # For long-lived runtime producers, require a fresh write at the new
        # destination after activation.  Static/state-only mappings omit this.
        timeout=max(0.1,float(os.environ.get('ENERGIE_CLEARUP_TYPE2_PROOF_TIMEOUT_SECONDS','75')))
        deadline=time.monotonic()+timeout
        pending=[]
        while True:
            pending=[]
            for item in plan['items']:
                proofs=item.get('runtime_proof_paths') or []
                if not proofs: continue
                ok=False
                for rel in proofs:
                    p=(root/item['destination']/rel) if (root/item['destination']).is_dir() else None
                    if p is not None and p.is_file() and not p.is_symlink() and p.stat().st_mtime >= activated_at - 1.0:
                        ok=True; break
                if not ok: pending.append(item['source'])
            if not pending or time.monotonic() >= deadline: break
            time.sleep(min(0.5,max(0.05,deadline-time.monotonic())))
        for source_rel in pending:
            failures.append(f'runtime_writer_proof_missing:{source_rel}')
        status='GREEN' if not failures else 'RED'

    # Refresh hashes after the observation window.  Finalize will require only
    # the old source hash to remain stable; destination may continue changing.
    final_checks=[]
    for item in plan['items']:
        src=root/item['source']; dst=root/item['destination']
        if src.exists() and dst.exists():
            final_checks.append({'source':item['source'],'destination':item['destination'],'path_key':item.get('path_key') or None,
                                 'source_rows_sha256':_json_sha(_tree_rows_for_validation(root,src)),
                                 'destination_rows_sha256':_json_sha(_tree_rows_for_validation(root,dst))})
    proof={'schema':'energie_clearup_type2_validation_v2','status':status,'clearup_id':clearup_id,
           'plan_sha256':plan['plan_sha256'],'checked_at':datetime.now(timezone.utc).isoformat(),
           'checks':final_checks,'failures':failures,
           'evidence':[x['destination'] for x in final_checks],
           'old_source_quiescence_seconds':max(0.05,float(os.environ.get('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS','2.0')))}
    # Commit validation evidence through the bounded privileged watcher. The
    # embedded PM user does not own the system Validation directory on NAS.
    committed = _watcher_call(
        root,
        operation='type2_validation_commit',
        clearup_id=clearup_id,
        plan=plan,
        validation_proof=proof,
    )
    if committed.get('validation_status') != status or committed.get('clearup_id') != clearup_id:
        raise RuntimeError('Type2 validation commit readback mismatch')
    return proof

def finalize_type2(project_root: Path | str, *, clearup_id: str, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if source != 'mcp_remote' or _token(explicit_user_text) not in AFFIRMATIVE:
        raise RuntimeError('explicit user approval missing for Type2 finalize')
    _release_idle(root)
    plan = _load_plan(root, clearup_id)
    _verify_export(root, clearup_id, plan)
    _contract_checks(root, plan)
    validation = root / VALIDATION_ROOT_REL / f'{clearup_id}.json'
    if validation.is_symlink() or not validation.is_file():
        raise RuntimeError('Type2 live validation evidence missing')
    try:
        proof = json.loads(validation.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError('Type2 live validation evidence unreadable') from exc
    if not isinstance(proof, dict) or str(proof.get('status') or '').upper() != 'GREEN' or proof.get('plan_sha256') != plan['plan_sha256']:
        raise RuntimeError('Type2 live validation evidence does not match current plan')
    evidence = proof.get('evidence')
    if not isinstance(evidence, list) or not evidence:
        raise RuntimeError('Type2 live validation requires evidence refs')
    _assert_external_recovery_confirmed(root)
    result = _watcher_call(root, operation='type2_finalize', clearup_id=clearup_id, plan=plan, explicit_user_text=explicit_user_text)
    return {**result, 'status': 'GREEN', 'clearup_id': clearup_id, 'plan_sha256': plan['plan_sha256'], 'live_validation': proof, 'deletion_performed': True}


def restore_type2(project_root: Path | str, *, clearup_id: str, explicit_user_text: str, source: str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if source != 'mcp_remote' or _token(explicit_user_text) not in AFFIRMATIVE:
        raise RuntimeError('explicit user approval missing for Type2 restore')
    _release_idle(root)
    plan = _load_plan(root, clearup_id)
    _verify_export(root, clearup_id, plan)
    result = _watcher_call(root, operation='type2_restore', clearup_id=clearup_id, plan=plan, explicit_user_text=explicit_user_text)
    return {**result, 'status': 'GREEN', 'clearup_id': clearup_id, 'plan_sha256': plan['plan_sha256']}
