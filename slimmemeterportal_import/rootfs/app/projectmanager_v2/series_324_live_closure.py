from __future__ import annotations

from typing import Any

PM_TECHNICAL_CHECKS = (
    'watcher_container_contract',
    'native_mcp_runtime',
)
PROJECT_CLOSE_CHECKS = (
    'project_crash_recovery_set',
    'nas_container_crash_recovery_retention',
    'project_structure_hygiene',
)
REQUIRED_CHECKS = PM_TECHNICAL_CHECKS + PROJECT_CLOSE_CHECKS
CLEARUP_DONE = {'completed', 'already_completed', 'no_action'}


def _map(checks: list[dict[str, Any]]) -> dict[str, str]:
    return {str(item.get('name')): str(item.get('status')) for item in checks if isinstance(item, dict)}


def evaluate(checks: list[dict[str, Any]], *, clearup: dict[str, Any] | None, release_version: str) -> dict[str, Any]:
    by_name = _map(checks)
    pm_failed = [name for name in PM_TECHNICAL_CHECKS if by_name.get(name) != 'GREEN']
    project_failed = [name for name in PROJECT_CLOSE_CHECKS if by_name.get(name) != 'GREEN']
    clearup = clearup if isinstance(clearup, dict) else {}
    clearup_ok = (
        str(clearup.get('status') or '') in CLEARUP_DONE
        and str(clearup.get('release_version') or '') == str(release_version)
    )
    if not clearup_ok:
        project_failed.append('project_clearup_live_acceptance')
    failed = list(pm_failed) + list(project_failed)
    return {
        'schema': 'energie_series_32_4_live_closure_v2',
        'release_version': str(release_version),
        'status': 'GREEN' if not failed else 'RED',
        'pm_status': 'GREEN' if not pm_failed else 'RED',
        'project_close_status': 'GREEN' if not project_failed else 'RED',
        'pm_required_checks': list(PM_TECHNICAL_CHECKS),
        'project_close_required_checks': list(PROJECT_CLOSE_CHECKS) + ['project_clearup_live_acceptance'],
        'required_checks': list(REQUIRED_CHECKS) + ['project_clearup_live_acceptance'],
        'pm_failed_or_missing': pm_failed,
        'project_close_failed_or_missing': project_failed,
        'failed_or_missing': failed,
        'ngrok_excluded_until_next_roadmap_phase': True,
    }


def next_action(check_status: dict[str, str], *, clearup_done: bool, project_close_deferred: bool = False) -> str:
    if check_status.get('watcher_container_contract') != 'GREEN':
        return 'REQUEST_WATCHER_RECREATE'
    if check_status.get('native_mcp_runtime') != 'GREEN':
        return 'REQUEST_NATIVE_MCP_RELOAD'
    if project_close_deferred:
        return 'DEFER_PROJECT_CLOSE'
    if check_status.get('project_crash_recovery_set') != 'GREEN':
        return 'CREATE_PROJECT_CR'
    if check_status.get('nas_container_crash_recovery_retention') != 'GREEN':
        return 'CREATE_NAS_CR'
    if not clearup_done or check_status.get('project_structure_hygiene') != 'GREEN':
        return 'RUN_CLEARUP'
    return 'COMPLETE'
