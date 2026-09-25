from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_legacy_install_adoption_is_not_in_active_release_controller():
    service=(ROOT/'tools/release_controller_service.py').read_text(encoding='utf-8')
    assert 'legacy_install_adoption' not in service
    assert 'adopt_exact_pre57_install' not in service


def test_manual_native_reload_remains_protected_and_release_controller_owned():
    manager=(ROOT/'slimmemeterportal_import/rootfs/app/projectmanager_v2/manager_core.py').read_text(encoding='utf-8')
    executor=(ROOT/'slimmemeterportal_import/rootfs/app/projectmanager_v2/protected_action_executor.py').read_text(encoding='utf-8')
    assert "'native_mcp_reload'" in manager and 'PROTECTED_ACTIONS' in manager
    assert 'Peter PRODUCTION_RESTART approval missing' in executor
    assert 'release_controller_owns_native_mcp_reload' in executor


def test_retired_legacy_pending_reload_never_blocks_current_fenced_route():
    executor=(ROOT/'slimmemeterportal_import/rootfs/app/projectmanager_v2/protected_action_executor.py').read_text(encoding='utf-8')
    assert "live_tuple < (32, 5, 9)" in executor
    assert 'From 32.5.9 onward retired pre-control-plane state is evidence only' in executor


def test_dangerous_legacy_code_is_explicitly_marked_and_permission_gated():
    policy=(ROOT/'DANGEROUS_LEGACY_CODE.md').read_text(encoding='utf-8')
    for name in ('tools/legacy_install_adoption.py','tools/native_mcp_reload_executor.py','tools/cr_standard_native_mcp_hotfix.py'):
        assert name in policy
    assert 'requires a new explicit Peter approval' in policy
