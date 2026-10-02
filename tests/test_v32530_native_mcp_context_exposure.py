from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOTFIX = ROOT / "tools/native_mcp_runtime_contract_hotfix.py"


def _source():
    return HOTFIX.read_text(encoding="utf-8")


def test_release_hotfix_carries_server_bound_resume_context_v2():
    source = _source()
    assert 'RESUME_CONTEXT_MARKER = "# PM_RESUME_CONTEXT_TOOL_VERSION=2026-09-30.v2"' in source
    assert 'return _api().resume_context(consumer="chatgpt_mcp")' in source
    assert 'ProjectmanagerAPI(RUNTIME_ROOT, project_root=_RESUME_PROJECT_ROOT)' in source


def test_release_hotfix_upgrades_previous_resume_context_contract():
    source = _source()
    assert 'RESUME_CONTEXT_PREVIOUS_MARKER = "# PM_RESUME_CONTEXT_TOOL_VERSION=2026-09-27.v1"' in source
    assert "resume_context_tool_upgraded_v2" in source


def test_release_hotfix_keeps_caller_hash_receipt_out_of_native_mcp_surface():
    source = _source()
    block = source[source.index("RESUME_CONTEXT_BLOCK ="):source.index("PM_RUNTIME_ROOT_MARKER")]
    assert "projectmanager_delivery_receipt" not in block
    assert "final_input_sha256" not in block
