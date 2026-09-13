import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)


def test_32450_stale_native_mcp_guard_refresh_task_is_superseded_by_newer_runtime():
    from state_reconciliation import StateReconciler

    task = {
        'id': 'task-32448-guard',
        'status': 'ACTIVE',
        'title': '32.4.48 Native MCP guard refresh',
        'goal': 'Schakel tijdelijk naar MAINTENANCE zodat de watcher de reeds succesvol herladen Native-MCP runtime fingerprint opnieuw valideert en de 32.4.48 live-acceptance kan sluiten.',
        'mode': 'MAINTENANCE',
        'step': 1,
        'steps_total': 1,
    }
    runtime = {
        'release': {'version': '32.4.49', 'source': '/project/App/VERSIE.txt'},
        'release_chain': {
            'atomic_swap': {
                'state': 'LIVE_ACCEPTANCE',
                'source': '/project/Inbox/atomic_app_swap_state.json',
                'raw': {'state': 'LIVE_ACCEPTANCE', 'to_version': '32.4.49'},
            }
        },
    }
    reconciler = StateReconciler(None, None, None, None, None)

    result = reconciler._evaluate_task(task, runtime=runtime, release_validation={})

    assert result['disposition'] == 'SUPERSEDED'
    assert result['changed'] is True
    assert '32.4.49' in result['reason']


def test_32450_native_mcp_guard_refreshes_in_main_loop_even_outside_maintenance_mode():
    source = (ROOT / 'tools/release_watcher.sh').read_text(encoding='utf-8')
    loop = source.split('while :; do', 1)[1]
    maintenance = loop.index('if mode_allows maintenance_requests; then')
    release_gate = loop.index('if mode_allows release_ingress && atomic_swap_allows_release_ingress; then')
    guard_call = loop.index('process_native_mcp_runtime_guard || true')

    assert guard_call < maintenance
    assert guard_call < release_gate


def test_32450_control_plane_uses_canonical_project_root_only():
    compose = (ROOT / 'tools/control_plane/docker-compose.containerstation.yml').read_text(encoding='utf-8')
    bootstrap = (ROOT / 'tools/control_plane/qnap_control_plane_bootstrap.py').read_text(encoding='utf-8')

    assert 'CACHEDEV1' not in compose
    assert 'CACHEDEV1' not in bootstrap
    assert '/share/Energie_NAS/EnergieProject' in compose
    assert 'QNAP_PHYSICAL_PROJECT_ROOT = "/share/Energie_NAS/EnergieProject"' in bootstrap
