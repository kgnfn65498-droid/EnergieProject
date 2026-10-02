import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

MODULE_PATH = TOOLS / "native_mcp_runtime_contract_hotfix.py"
spec = importlib.util.spec_from_file_location("native_mcp_runtime_contract_hotfix_v32530_test", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _legacy_tools():
    return """# prelude
# PM_RESUME_CONTEXT_TOOL_VERSION=2026-09-27.v1
@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def projectmanager_resume_context():
    return {"schema": "legacy"}


def _api() -> ProjectmanagerAPI:
    return ProjectmanagerAPI(RUNTIME_ROOT)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def projectmanager_status():
    return _api().status()
"""


def test_resume_context_hotfix_upgrades_v1_to_server_bound_v2():
    upgraded, changed, reason = module._ensure_resume_context_tool(_legacy_tools())
    assert changed is True
    assert reason == "resume_context_tool_upgraded_v2"
    assert module.RESUME_CONTEXT_MARKER in upgraded
    assert module.RESUME_CONTEXT_PREVIOUS_MARKER not in upgraded
    assert upgraded.count("def _api() -> ProjectmanagerAPI:") == 1
    assert 'project_root=_RESUME_PROJECT_ROOT' in upgraded
    assert 'return _api().resume_context(consumer="chatgpt_mcp")' in upgraded


def test_resume_context_hotfix_v2_is_idempotent():
    upgraded, _, _ = module._ensure_resume_context_tool(_legacy_tools())
    second, changed, reason = module._ensure_resume_context_tool(upgraded)
    assert second == upgraded
    assert changed is False
    assert reason == "resume_context_tool_current"
