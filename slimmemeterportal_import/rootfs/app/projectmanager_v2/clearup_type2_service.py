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

AFFIRMATIVE = {'akkoord', 'ja', 'yes', 'approve', 'goedgekeurd', 'goedkeuren'}
CLEARUP_ID_RE = re.compile(r'^ClearUp_[0-9]{3,}$')
PLAN_SCHEMA = 'energie_clearup_type2_plan_v1'
TYPE2_REQUEST_SCHEMA = 'energie_clearup_type2_request_v1'
TYPE2_RESULT_SCHEMA = 'energie_clearup_type2_result_v1'
PLAN_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Plans')
STAGING_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Staging')
EXPORT_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Exports')
STATE_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/State')
VALIDATION_ROOT_REL = Path('Data/03_Systeem/Projectmanager/ClearUp/Validation')
WATCHER_REQUEST_REL = Path('Inbox/project_clearup_move_request.json')
WATCHER_RESULT_REL = Path('Inbox/logs/project_clearup_move_result.json')
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
        normalized.append({
            'source': source,
            'destination': destination,
            'reason': str(raw.get('reason') or '').strip(),
            'optional': raw.get('optional') is True,
            'path_key': str(raw.get('path_key') or '').strip(),
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


def _snapshot_release_dirs(root: Path) -> dict[str, list[tuple[str, int, str]]]:
    result = {}
    for rel in ('Inbox/incoming', 'Inbox/processing'):
        base = root / rel
        rows = []
        if base.is_dir():
            for p in sorted(base.rglob('*')):
                if p.is_symlink():
                    raise RuntimeError(f'release mailbox symlink refused: {p}')
                if p.is_file():
                    rows.append((p.relative_to(base).as_posix(), p.stat().st_size, _sha(p)))
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


def _watcher_call(root: Path, *, operation: str, clearup_id: str, plan: dict[str, Any], explicit_user_text: str = '') -> dict[str, Any]:
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
        'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=WATCHER_TIMEOUT_SECONDS)).isoformat(),
        'plan_sha256': plan['plan_sha256'],
        'explicit_user_approval': _token(explicit_user_text) in AFFIRMATIVE,
        'mailbox_snapshot_before': _snapshot_release_dirs(root),
        'result_path': result_path.relative_to(root).as_posix(),
    }
    _atomic_json(request_path, payload)
    deadline = time.monotonic() + WATCHER_TIMEOUT_SECONDS
    try:
        while time.monotonic() < deadline:
            if result_path.is_file():
                try:
                    response = json.loads(result_path.read_text(encoding='utf-8'))
                except Exception:
                    response = {}
                if isinstance(response, dict) and response.get('request_id') == request_id:
                    if response.get('schema') != TYPE2_RESULT_SCHEMA:
                        raise RuntimeError('Type2 watcher result schema mismatch')
                    if response.get('status') != 'completed':
                        raise RuntimeError('Type2 watcher operation failed: ' + str(response.get('error') or response.get('status')))
                    result = response.get('result')
                    if not isinstance(result, dict):
                        raise RuntimeError('Type2 watcher result missing')
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
    manifest_path = root / STAGING_ROOT_REL / clearup_id / 'TYPE2_MANIFEST.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except Exception as exc:
        raise RuntimeError('Type2 recovery manifest missing/unreadable') from exc
    checks=[]; failures=[]
    for item in manifest.get('items') or []:
        src = root / item['source']; dst = root / item['destination']
        if not src.exists() or src.is_symlink():
            failures.append(f"source_missing:{item['source']}"); continue
        if not dst.exists() or dst.is_symlink():
            failures.append(f"destination_missing:{item['destination']}"); continue
        # Local copy of executor tree-row logic for read-only validation.  The
        # live source is authoritative during the migration window: self-hosted
        # components may finish the command that activated the new path after
        # the initial copy.  Finalize is therefore allowed only when destination
        # exactly matches the *current* preserved source, not merely the older
        # recovery snapshot.
        def rows(base: Path):
            out=[]
            seq=[base] if base.is_file() else [base,*sorted(base.rglob('*'))]
            for q in seq:
                if q.is_symlink(): raise RuntimeError(f'Type2 validation symlink refused: {q}')
                rel=q.relative_to(root).as_posix()
                if q.is_file(): out.append({'path':rel,'type':'file','size':q.stat().st_size,'sha256':_sha(q)})
                elif q.is_dir(): out.append({'path':rel,'type':'directory'})
            return out
        live_source_rows=rows(src)
        expected=[]
        for row in live_source_rows:
            suffix = Path(row['path']).relative_to(item['source']).as_posix() if row['path'] != item['source'] else '.'
            dest_path = item['destination'] if suffix == '.' else f"{item['destination']}/{suffix}"
            expected.append({**row,'path':dest_path})
        destination_rows=rows(dst)
        source_rows_sha256=_json_sha(live_source_rows)
        destination_rows_sha256=_json_sha(destination_rows)
        if destination_rows != expected:
            failures.append(f"destination_live_source_mismatch:{item['destination']}")
        key=str(item.get('path_key') or '').strip()
        if key:
            marker=root / Path('Data/03_Systeem/Projectmanager/ClearUp/PathActivation') / f'{key}.json'
            try: m=json.loads(marker.read_text(encoding='utf-8'))
            except Exception: m={}
            if not isinstance(m,dict) or m.get('active') is not True or m.get('plan_sha256') != plan['plan_sha256']:
                failures.append(f'activation_missing:{key}')
            resolved=project_system_path(root,item['source'])
            if resolved.resolve() != dst.resolve():
                failures.append(f'active_path_not_destination:{key}')
        checks.append({'source':item['source'],'destination':item['destination'],'path_key':key or None,'source_rows_sha256':source_rows_sha256,'destination_rows_sha256':destination_rows_sha256})
    # Runtime-writer proof for batches whose producer exposes a heartbeat/state file.
    runtime_proofs=[]
    proof_candidates={
        'ClearUp_002':['status/current.json','heartbeat/manager.json'],
        'ClearUp_005':['runtime.json','current.json'],
        'ClearUp_006':['current.json','runtime_guard.json'],
        'ClearUp_007':['runtime.json'],
    }
    for rel in proof_candidates.get(clearup_id,[]):
        found=False
        for item in manifest.get('items') or []:
            p=(root/item['destination']/rel) if (root/item['destination']).is_dir() else None
            if p is not None and p.is_file() and not p.is_symlink():
                runtime_proofs.append({'path':p.relative_to(root).as_posix(),'sha256':_sha(p)})
                found=True; break
        if found: break
    if clearup_id in proof_candidates and not runtime_proofs:
        failures.append('runtime_writer_proof_missing_restart_or_recreate_required')
    status='GREEN' if not failures else 'RED'
    proof={'schema':'energie_clearup_type2_validation_v1','status':status,'clearup_id':clearup_id,'plan_sha256':plan['plan_sha256'],'checked_at':datetime.now(timezone.utc).isoformat(),'checks':checks,'runtime_proofs':runtime_proofs,'failures':failures,'evidence':[x['destination'] for x in checks]+[x['path'] for x in runtime_proofs]}
    validation=root / VALIDATION_ROOT_REL / f'{clearup_id}.json'
    _atomic_json(validation,proof)
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
