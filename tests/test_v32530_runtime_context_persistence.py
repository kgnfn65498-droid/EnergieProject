from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2/manager_service.py"


def test_runtime_development_context_persists_context_package_semantics():
    source = MANAGER.read_text(encoding="utf-8")
    assert "'schema': 'energie_pmv2_runtime_development_context_v3'" in source
    assert "'context_package': development_context.get('context_package') or {}" in source
    assert "'inventory_complete': development_context.get('inventory_complete') is True" in source
    assert "'mandatory_context_complete': development_context.get('mandatory_context_complete') is True" in source
    assert "'delivery_recorded': False" in source
    assert "'behavior_evaluation_passed': False" in source
