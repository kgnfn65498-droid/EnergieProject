from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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


def discover_requirements(project_root: Path | str) -> list[str]:
    root = Path(project_root)
    req_root = root / REQUIREMENTS_DIR
    if not _safe_dir(req_root):
        return []
    result = []
    for path in req_root.glob('*.md'):
        if path.is_symlink() or not path.is_file():
            continue
        result.append(path.relative_to(root).as_posix())
    return sorted(result)


def discover_hard_requirements(project_root: Path | str) -> list[str]:
    return [p for p in discover_requirements(project_root) if Path(p).name.startswith('HARD_REQUIREMENT_')]


def highest_checkpoint(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root)
    cp_root = root / CHECKPOINT_DIR
    if not _safe_dir(cp_root):
        return {'status': 'MISSING', 'path': '', 'mtime_ns': None, 'payload': {}}
    candidates = []
    for path in cp_root.glob('CHECKPOINT*'):
        if path.is_symlink() or not path.is_file():
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        candidates.append((st.st_mtime_ns, path.name, path))
    if not candidates:
        return {'status': 'MISSING', 'path': '', 'mtime_ns': None, 'payload': {}}
    _mtime, _name, selected = max(candidates)
    payload: dict[str, Any] = {}
    if selected.suffix.lower() == '.json':
        try:
            raw = json.loads(selected.read_text(encoding='utf-8'))
            payload = raw if isinstance(raw, dict) else {}
        except (OSError, ValueError, json.JSONDecodeError):
            payload = {}
    return {
        'status': 'GREEN',
        'path': selected.relative_to(root).as_posix(),
        'mtime_ns': selected.stat().st_mtime_ns,
        'payload': payload,
    }


def _has_content(root: Path, relative: str) -> bool:
    path = root / relative
    if not _safe_dir(path):
        return False
    try:
        return any(item.is_file() and not item.is_symlink() for item in path.rglob('*'))
    except OSError:
        return False


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
    checks = {
        'reporting_kb_root': _has_content(root, REPORT_KB),
        'technical_pm_kb_root': _has_content(root, PM_KB),
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
    roots_present = sum(bool(checks.get(name)) for name in ('reporting_kb_root', 'technical_pm_kb_root'))
    if missing:
        status = 'PARTIAL' if roots_present == 1 else 'RED'
    else:
        status = 'COMPLETE'
    return {
        'schema': 'energie_full_kb_runtime_enforcement_v1',
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
        live
        and cp_target
        and live == cp_target
        and cp_payload.get('schema') == 'energie_chat_switch_checkpoint_v2'
        and cp_payload.get('status') == 'READY_FOR_NEW_CHAT'
    )
    if live and cp_live and live != cp_live and not target_reached:
        conflicts.append({'kind': 'checkpoint_live_release_conflict', 'live': live, 'checkpoint': cp_live, 'checkpoint_path': cp.get('path')})
    return {
        'schema': 'energie_development_truth_reconciliation_v1',
        'status': 'RED' if conflicts else 'GREEN',
        'fail_closed': bool(conflicts),
        'live_release': live,
        'status_release': status_release,
        'highest_checkpoint': cp.get('path') or '',
        'conflicts': conflicts,
    }


def build_development_context(project_root: Path | str, status: dict | None = None) -> dict[str, Any]:
    root = Path(project_root)
    requirements = discover_requirements(root)
    full_kb = evaluate_full_kb(root, development_release=True)
    reconciliation = current_truth_reconciliation(root, status)
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
        'full_kb': full_kb,
        'truth_reconciliation': reconciliation,
        'live_handover_primary': True,
    }
