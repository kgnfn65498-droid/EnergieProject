from __future__ import annotations

from typing import Any

REQUIRED_CHECKS = (
    'watcher_container_contract',
    'native_mcp_runtime',
    'project_crash_recovery_set',
    'nas_container_crash_recovery_retention',
    'project_structure_hygiene',
)
CLEARUP_DONE = {'completed', 'already_completed', 'no_action'}


def _map(checks: list[dict[str, Any]]) -> dict[str, str]:
    return {str(item.get('name')): str(item.get('status')) for item in checks if isinstance(item, dict)}


def evaluate(checks: list[dict[str, Any]], *, clearup: dict[str, Any] | None, release_version: str) -> dict[str, Any]:
    by_name = _map(checks)
    missing_or_red = [name for name in REQUIRED_CHECKS if by_name.get(name) != 'GREEN']
    clearup = clearup if isinstance(clearup, dict) else {}
    clearup_ok = (
        str(clearup.get('status') or '') in CLEARUP_DONE
        and str(clearup.get('release_version') or '') == str(release_version)
    )
    if not clearup_ok:
        missing_or_red.append('project_clearup_live_acceptance')
    return {
        'schema': 'energie_series_32_4_live_closure_v1',
        'release_version': str(release_version),
        'status': 'GREEN' if not missing_or_red else 'RED',
        'required_checks': list(REQUIRED_CHECKS) + ['project_clearup_live_acceptance'],
        'failed_or_missing': missing_or_red,
        'ngrok_excluded_until_next_roadmap_phase': True,
    }


def next_action(check_status: dict[str, str], *, clearup_done: bool) -> str:
    if check_status.get('watcher_container_contract') != 'GREEN':
        return 'BLOCKED_WATCHER_RECREATE'
    if check_status.get('native_mcp_runtime') != 'GREEN':
        return 'REQUEST_NATIVE_MCP_RELOAD'
    if check_status.get('project_crash_recovery_set') != 'GREEN':
        return 'CREATE_PROJECT_CR'
    if check_status.get('nas_container_crash_recovery_retention') != 'GREEN':
        return 'CREATE_NAS_CR'
    if not clearup_done or check_status.get('project_structure_hygiene') != 'GREEN':
        return 'RUN_CLEARUP'
    return 'COMPLETE'
