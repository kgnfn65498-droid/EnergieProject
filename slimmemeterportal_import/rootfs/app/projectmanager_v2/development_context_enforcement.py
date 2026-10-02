from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from capability_registry import discover_capabilities
from context_package import build_context_package
from development_handover_sync import evaluate_handover_freshness

MASTER_INDEX = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_MASTER_DEVELOPMENT_INDEX.md'
ACTIVE_CONTEXT = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_ACTIVE_DEVELOPMENT_CONTEXT.md'
MANIFEST = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_DEVELOPMENT_MANIFEST.md'
LEDGER = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/01_UNIFIED_DEVELOPMENT_LEDGER.md'
LEDGER_CURRENT = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/01A_LEDGER_CURRENT_TRUTH.md'
DECISION_LOG = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/02_DECISION_LOG.md'
DEVELOPMENT_CHANGELOG = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/03_DEVELOPMENT_CHANGELOG.md'
SPOCK_CONTEXT = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/04_SPOCK_CONTEXT.md'
FULL_KB_AUDIT = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/05_FULL_KB_AUDIT_20260927.md'
TICKET_ISSUE_INDEX = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/05_TICKET_ISSUE_INDEX.md'
KB_INVENTORY = 'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/06_KNOWLEDGEBASE_INVENTORY_20260927.md'
REQUIREMENTS_DIR = 'Data/03_Systeem/Projectmanager/Requirements'
HANDOVER = 'Data/03_Systeem/Projectmanager/Handover/CURRENT_DEVELOPMENT_HANDOVER.md'
REPORT_KB = 'Data/02_Output/Rapportages/KnowledgeBase'
PM_KB = 'Data/03_Systeem/Projectmanager/KnowledgeBase'
CHECKPOINT_DIR = 'Data/03_Systeem/Projectmanager/ClearUp/State'
PROJECT_AFSPRAKEN = 'App/PROJECT_AFSPRAKEN.md'
PROJECT_AFSPRAKEN_FALLBACK = 'PROJECT_AFSPRAKEN.md'
APP_CHANGELOG = 'App/CHANGELOG.md'


def _regular(path: Path) -> bool:
    return path.exists() and not path.is_symlink() and path.is_file()


def _safe_dir(path: Path) -> bool:
    return path.exists() and not path.is_symlink() and path.is_dir()


def _version_tuple(value: str) -> tuple[int, ...]:
    try:
        return tuple(int(part) for part in str(value).split('.')[:3])
    except ValueError:
        return ()


def discover_requirements(project_root: Path | str) -> list[str]:
    root = Path(project_root)
    req_root = root / REQUIREMENTS_DIR
    if not _safe_dir(req_root):
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in req_root.glob('*.md')
        if path.is_file() and not path.is_symlink()
    )


def discover_hard_requirements(project_root: Path | str) -> list[str]:
    return [p for p in discover_requirements(project_root) if Path(p).name.startswith('HARD_REQUIREMENT_')]


def _checkpoint_rank(payload: dict[str, Any], mtime_ns: int) -> tuple[int, float, str]:
    sequence = payload.get('checkpoint_sequence')
    try:
        if sequence not in (None, ''):
            return (3, float(sequence), 'checkpoint_sequence')
    except (TypeError, ValueError):
        pass
    for key in ('generated_at', 'created_at', 'updated_at', 'timestamp'):
        value = str(payload.get(key) or '').strip()
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
            return (2, parsed.timestamp(), key)
        except ValueError:
            continue
    return (1, float(mtime_ns), 'legacy_mtime_fallback')


def highest_checkpoint(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root)
    cp_root = root / CHECKPOINT_DIR
    if not _safe_dir(cp_root):
        return {'status': 'MISSING', 'path': '', 'mtime_ns': None, 'payload': {}, 'reasons': ['checkpoint_dir_missing']}
    valid = []
    invalid = []
    for path in cp_root.glob('CHECKPOINT*'):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            st = path.stat()
            if path.suffix.lower() != '.json':
                invalid.append({'path': path.name, 'reason': 'unsupported_checkpoint_format'})
                continue
            raw = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(raw, dict) or not raw:
                invalid.append({'path': path.name, 'reason': 'empty_or_invalid_payload'})
                continue
            if not str(raw.get('status') or '').strip():
                # Pre-32.5.28 checkpoints predate the explicit status contract.
                # Keep them readable as historical continuity evidence only;
                # current/new checkpoints remain fail-closed on missing status.
                legacy_live = _version_tuple(str(raw.get('live_release') or raw.get('live_production') or ''))
                if not legacy_live or legacy_live >= (32, 5, 28):
                    invalid.append({'path': path.name, 'reason': 'status_missing'})
                    continue
            valid.append((_checkpoint_rank(raw, st.st_mtime_ns), path.name, path, raw, st.st_mtime_ns))
        except (OSError, ValueError, json.JSONDecodeError, UnicodeError) as exc:
            invalid.append({'path': path.name, 'reason': type(exc).__name__})
    if not valid:
        return {'status': 'RED' if invalid else 'MISSING', 'path': '', 'mtime_ns': None, 'payload': {}, 'reasons': invalid}

    best_rank = max(item[0][:2] for item in valid)
    newest = [item for item in valid if item[0][:2] == best_rank]
    if len(newest) > 1:
        fingerprints = {json.dumps(item[3], ensure_ascii=False, sort_keys=True, separators=(',', ':')) for item in newest}
        if len(fingerprints) > 1:
            return {
                'status': 'RED', 'path': '', 'mtime_ns': max(item[4] for item in newest), 'payload': {},
                'reasons': [{'reason': 'equal_rank_checkpoint_conflict', 'paths': [item[1] for item in newest], 'ranking_basis': newest[0][0][2]}],
            }
    rank, _name, selected, payload, mtime_ns = sorted(newest, key=lambda item: item[1])[-1]
    return {
        'status': 'GREEN',
        'path': selected.relative_to(root).as_posix(),
        'mtime_ns': mtime_ns,
        'payload': payload,
        'ranking_basis': rank[2],
        'ranking_value': rank[1],
        'legacy_rank_fallback': rank[2] == 'legacy_mtime_fallback',
        'invalid_candidates': invalid,
    }


def _inventory_root(root: Path, relative: str) -> dict[str, Any]:
    base = root / relative
    if not _safe_dir(base):
        return {'status': 'MISSING', 'root': relative, 'count': 0, 'paths': [], 'inventory_sha256': ''}
    rows = []
    errors = []
    try:
        for path in sorted(base.rglob('*')):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                data = path.read_bytes()
            except OSError as exc:
                errors.append({'path': path.relative_to(root).as_posix(), 'reason': type(exc).__name__})
                continue
            rows.append({'path': path.relative_to(root).as_posix(), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    except OSError as exc:
        errors.append({'path': relative, 'reason': type(exc).__name__})
    raw = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return {
        'status': 'GREEN' if rows and not errors else ('PARTIAL' if rows else 'RED'),
        'root': relative,
        'count': len(rows),
        'paths': [row['path'] for row in rows],
        'errors': errors,
        'inventory_sha256': hashlib.sha256(raw).hexdigest() if rows else '',
    }


def _project_agreements_path(root: Path) -> str:
    if _regular(root / PROJECT_AFSPRAKEN):
        return PROJECT_AFSPRAKEN
    if _regular(root / PROJECT_AFSPRAKEN_FALLBACK):
        return PROJECT_AFSPRAKEN_FALLBACK
    return PROJECT_AFSPRAKEN


def evaluate_full_kb(project_root: Path | str, *, development_release: bool = True) -> dict[str, Any]:
    root = Path(project_root)
    requirements = discover_requirements(root)
    hard = discover_hard_requirements(root)
    cp = highest_checkpoint(root)
    agreements = _project_agreements_path(root)
    reporting_inventory = _inventory_root(root, REPORT_KB)
    technical_inventory = _inventory_root(root, PM_KB)
    checks = {
        'reporting_kb_root': reporting_inventory.get('status') == 'GREEN',
        'technical_pm_kb_root': technical_inventory.get('status') == 'GREEN',
        'requirements_root': _safe_dir(root / REQUIREMENTS_DIR) and bool(requirements),
        'all_hard_requirements_discovered': bool(hard) and set(hard).issubset(set(requirements)),
        'current_handover': _regular(root / HANDOVER),
        'master_development_index': _regular(root / MASTER_INDEX),
        'active_development_context': _regular(root / ACTIVE_CONTEXT),
        'development_manifest': _regular(root / MANIFEST),
        'unified_development_ledger': _regular(root / LEDGER),
        'ledger_current_truth': _regular(root / LEDGER_CURRENT),
        'decision_log': _regular(root / DECISION_LOG),
        'development_changelog': _regular(root / DEVELOPMENT_CHANGELOG),
        'spock_context': _regular(root / SPOCK_CONTEXT),
        'full_kb_audit': _regular(root / FULL_KB_AUDIT),
        'ticket_issue_index': _regular(root / TICKET_ISSUE_INDEX),
        'knowledgebase_inventory': _regular(root / KB_INVENTORY),
        'highest_checkpoint': cp.get('status') == 'GREEN',
    }
    if development_release:
        checks['project_afspraken'] = _regular(root / agreements)
        checks['app_changelog'] = _regular(root / APP_CHANGELOG)
    missing = sorted(name for name, ok in checks.items() if not ok)
    status = 'COMPLETE' if not missing else ('PARTIAL' if reporting_inventory.get('count') or technical_inventory.get('count') else 'RED')
    return {
        'schema': 'energie_full_kb_runtime_enforcement_v2',
        'status': status,
        'complete': status == 'COMPLETE',
        'checks': checks,
        'missing': missing,
        'master_index': MASTER_INDEX,
        'requirements_index': f'{REQUIREMENTS_DIR}/00_REQUIREMENTS_INDEX.md',
        'requirements': requirements,
        'hard_requirements': hard,
        'requirements_count': len(requirements),
        'hard_requirements_count': len(hard),
        'checkpoint': {k: cp.get(k) for k in ('status', 'path', 'mtime_ns')},
        'project_afspraken': agreements,
        'inventory': {
            'reporting_kb': reporting_inventory,
            'technical_pm_kb': technical_inventory,
            'requirements_inventory_sha256': hashlib.sha256(json.dumps(requirements, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest(),
        },
    }


def current_truth_reconciliation(project_root: Path | str, status: dict | None = None) -> dict[str, Any]:
    root = Path(project_root)
    status = status if isinstance(status, dict) else {}
    conflicts: list[dict[str, Any]] = []
    try:
        live = (root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    except OSError:
        live = ''
    status_release = str(((status.get('release') or {}).get('version')) or '').strip()
    if live and status_release and live != status_release:
        conflicts.append({'kind': 'live_status_release_conflict', 'live': live, 'status': status_release})

    cp = highest_checkpoint(root)
    cp_payload = cp.get('payload') if isinstance(cp.get('payload'), dict) else {}
    cp_live = str(cp_payload.get('live_release') or cp_payload.get('live_production') or '').strip()
    cp_target = str(cp_payload.get('target_release') or '').strip()
    target_reached = bool(
        live and cp_target and live == cp_target
        and cp_payload.get('schema') == 'energie_chat_switch_checkpoint_v2'
        and cp_payload.get('status') == 'READY_FOR_NEW_CHAT'
    )
    if live and cp_live and live != cp_live and not target_reached:
        conflicts.append({'kind': 'checkpoint_live_release_conflict', 'live': live, 'checkpoint': cp_live, 'checkpoint_path': cp.get('path')})

    handover_freshness = {'status': 'NOT_REQUIRED', 'fail_closed': False, 'reasons': []}
    if max(_version_tuple(live), _version_tuple(cp_target)) >= (32, 5, 28):
        handover_freshness = evaluate_handover_freshness(root, checkpoint=cp, status=status)
        if handover_freshness.get('status') != 'GREEN':
            conflicts.append({'kind': 'handover_freshness_conflict', 'checkpoint_path': cp.get('path'), 'reasons': list(handover_freshness.get('reasons') or [])})

    active = status.get('active_task') if isinstance(status.get('active_task'), dict) else {}
    active_target = str((active.get('build_metadata') or {}).get('release_version') or '').strip() if isinstance(active.get('build_metadata'), dict) else ''
    if cp_target and active_target and cp_target != active_target:
        conflicts.append({
            'kind': 'target_release_conflict',
            'checkpoint_target': cp_target,
            'active_task_target': active_target,
            'checkpoint_path': cp.get('path'),
        })
    cp_next = str(cp_payload.get('next_action') or '').strip()
    active_next = str(active.get('next_action') or status.get('next_action') or '').strip()
    cp_blockers = list(cp_payload.get('blockers') or []) if isinstance(cp_payload.get('blockers'), list) else []
    active_blockers = list(active.get('blockers') or []) if isinstance(active.get('blockers'), list) else []

    stale_lower_priority: list[dict[str, Any]] = []
    if cp_next and active_next and cp_next != active_next:
        stale_lower_priority.append({
            'claim': 'next_action', 'authoritative_source': cp.get('path') or 'highest_checkpoint',
            'authoritative_value': cp_next, 'lower_priority_source': 'active_task', 'lower_priority_value': active_next,
        })
    if cp_blockers and active_blockers and cp_blockers != active_blockers:
        stale_lower_priority.append({
            'claim': 'blockers', 'authoritative_source': cp.get('path') or 'highest_checkpoint',
            'authoritative_value': cp_blockers, 'lower_priority_source': 'active_task', 'lower_priority_value': active_blockers,
        })

    first_action = cp_next or active_next
    if not first_action and max(_version_tuple(live), _version_tuple(cp_target)) >= (32, 5, 28):
        conflicts.append({'kind': 'first_unproven_action_missing', 'checkpoint_path': cp.get('path')})

    governing_claims = {
        'live_release': live,
        'target_release': cp_target or active_target,
        'artifact': str(cp_payload.get('artifact') or cp_payload.get('final_artifact') or cp_payload.get('predecessor_artifact') or ''),
        'artifact_sha256': str(cp_payload.get('artifact_sha256') or cp_payload.get('final_artifact_sha256') or cp_payload.get('predecessor_sha256') or ''),
        'artifact_size': cp_payload.get('artifact_size') or cp_payload.get('final_artifact_size') or cp_payload.get('predecessor_size'),
        'checkpoint': cp.get('path') or '',
        'task_id': active.get('id'),
        'task_title': active.get('title'),
        'blockers': cp_blockers if cp_blockers else active_blockers,
        'completed': list(cp_payload.get('completed') or []) if isinstance(cp_payload.get('completed'), list) else [],
        'pending': list(cp_payload.get('pending') or []) if isinstance(cp_payload.get('pending'), list) else [],
        'first_unproven_action': first_action,
    }
    return {
        'schema': 'energie_development_truth_reconciliation_v3',
        'status': 'RED' if conflicts else 'GREEN',
        'fail_closed': bool(conflicts),
        'live_release': live,
        'status_release': status_release,
        'highest_checkpoint': cp.get('path') or '',
        'handover_freshness': handover_freshness,
        'governing_claims': governing_claims,
        'first_unproven_action': first_action,
        'superseded_lower_priority_claims': stale_lower_priority,
        'conflicts': conflicts,
    }


def build_development_context(project_root: Path | str, status: dict | None = None) -> dict[str, Any]:
    root = Path(project_root)
    status = status if isinstance(status, dict) else {}
    requirements = discover_requirements(root)
    full_kb = evaluate_full_kb(root, development_release=True)
    reconciliation = current_truth_reconciliation(root, status)
    capabilities = discover_capabilities(root)
    source_paths = {
        'master_index': MASTER_INDEX,
        'active_context': ACTIVE_CONTEXT,
        'manifest': MANIFEST,
        'ledger_current_truth': LEDGER_CURRENT,
        'spock_context': SPOCK_CONTEXT,
        'current_handover': HANDOVER,
    }
    package = build_context_package(
        root,
        status=status,
        source_paths=source_paths,
        requirements=requirements,
        full_kb=full_kb,
        truth=reconciliation,
        capabilities=capabilities,
    )
    return {
        'runtime_truth': 'Inbox/projectmanager_v2/RuntimeV2/development_context/current.json',
        'runtime_truth_primary': True,
        'master_index': MASTER_INDEX,
        'active_context': ACTIVE_CONTEXT,
        'manifest': MANIFEST,
        'ledger': LEDGER,
        'ledger_current_truth': LEDGER_CURRENT,
        'decision_log': DECISION_LOG,
        'development_changelog': DEVELOPMENT_CHANGELOG,
        'spock_context': SPOCK_CONTEXT,
        'full_kb_audit': FULL_KB_AUDIT,
        'ticket_issue_index': TICKET_ISSUE_INDEX,
        'knowledgebase_inventory': KB_INVENTORY,
        'requirements': requirements,
        'requirements_dynamic_discovery': True,
        'requirements_count': len(requirements),
        'requirements_inventory_crosscheck': {'status': 'GREEN' if len(requirements) == full_kb.get('requirements_count') else 'RED', 'count': len(requirements)},
        'full_kb': full_kb,
        'truth_reconciliation': reconciliation,
        'handover_freshness': reconciliation.get('handover_freshness') or {},
        'capability_registry': capabilities,
        'capability_registry_required_before_unavailable': True,
        'live_handover_primary': True,
        'context_package': package,
        'inventory_complete': package.get('inventory_complete') is True,
        'mandatory_context_complete': package.get('mandatory_context_complete') is True,
    }
