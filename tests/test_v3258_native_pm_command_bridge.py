from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'

def test_release_runtime_adapter_prepares_native_command_bridge_before_probe():
    src=(TOOLS/'release_runtime_adapter.py').read_text()
    assert 'native_mcp_runtime_contract_hotfix.apply(self.root)' in src
    assert src.index('native_mcp_runtime_contract_hotfix.apply(self.root)') < src.index('guard=self.guard.probe(self.root)')

def test_complete_release_reconciles_native_runtime_before_post_live_green():
    src=(TOOLS/'release_controller_service.py').read_text()
    assert "native_settle=getattr(self.adapter,'reconcile_completed_native_runtime',None)" in src
    assert src.index('native_settle=getattr') < src.index('post_live_required=')

def test_hotfix_contains_generic_command_forwarding_contract():
    src=(TOOLS/'native_mcp_runtime_contract_hotfix.py').read_text()
    for token in ('PM_COMMAND_FORWARDING_VERSION=2026-09-25.v1', "'classification_hint'", "'artifact_path'", "'release_version'", "'source_channel'"):
        assert token in src
    assert 'command_forwarding_current' in src

def test_clearup_routes_present_and_type1_targets_3258():
    cp=(ROOT/'slimmemeterportal_import/rootfs/app/projectmanager_v2/command_processor.py').read_text()
    for hint in ('clearup_apply','clearup_type2_prepare','clearup_type2_export_info','clearup_type2_export_chunk','clearup_type2_migrate','clearup_type2_validate','clearup_type2_finalize','clearup_type2_restore'):
        assert hint in cp
    chat=(ROOT/'slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_chat_service.py').read_text()
    executor=(TOOLS/'project_clearup_move_executor.py').read_text()
    assert 'requires active 32.5.7+' in chat
    assert 'TYPE1 delete vereist release 32.5.7+' in executor

def test_concrete_type2_inventory_002_through_012_exists():
    planroot=TOOLS/'clearup_type2_plans'
    for n in range(2,13):
        p=planroot/f'ClearUp_{n:03d}.json'
        assert p.is_file(), p
        data=json.loads(p.read_text())
        assert data['clearup_id']==f'ClearUp_{n:03d}'
        assert data['classification']=='TYPE2'
        assert data['status']=='READY'
        assert data.get('items')

def test_hotfix_functionally_rewrites_old_native_submit_bridge(tmp_path):
    import importlib.util, py_compile
    spec=importlib.util.spec_from_file_location('nmcp_hotfix_3258',TOOLS/'native_mcp_runtime_contract_hotfix.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    (tmp_path/'App').mkdir(); (tmp_path/'App/VERSIE.txt').write_text('32.5.8\n')
    native=tmp_path/'Infra/Docker/native-mcp'; native.mkdir(parents=True)
    (native/'server.py').write_text(
        "from registry import mcp\nimport tools_projectmanager  # noqa: F401\nif __name__ == \"__main__\":\n    pass\n"
    )
    old='''from pathlib import Path\nimport os\nfrom typing import Any\nfrom uuid import uuid4\nsource_channel = source_ref = occurred_at = classification_hint = ''\nartifact_path = artifact_sha256 = release_version = verification_report = ''\ndef projectmanager_submit_command(intent: str, text: str='', title: str='', goal: str='', steps_total: int=1, priority: int=2, next_action: str='', artifact_path: str='', artifact_sha256: str='', release_version: str='', verification_report: str='', source_channel: str='', source_ref: str='', occurred_at: str='', classification_hint: str=''):\n    payload = {\n        'intent': intent, 'text': text, 'title': title, 'goal': goal,\n        'steps_total': steps_total, 'priority': priority, 'next_action': next_action,\n    }\n    if intent == 'conversation_intake':\n        payload.update({'source_channel': source_channel, 'source_ref': source_ref, 'occurred_at': occurred_at, 'classification_hint': classification_hint})\n    if intent == 'production_deploy':\n        payload.update({'artifact_path': artifact_path, 'artifact_sha256': artifact_sha256, 'release_version': release_version, 'verification_report': verification_report})\n    return _write_command(payload)\n\n# Remote decision resolution, direct deploy/purchase/payment and arbitrary\n# RuntimeV2 writes are deliberately absent. Protected approval stays local HA.\n'''
    (native/'tools_projectmanager.py').write_text(old)
    result=mod.apply(tmp_path)
    patched=(native/'tools_projectmanager.py').read_text()
    assert result['status']=='GREEN' and result['command_forwarding_current'] is True
    assert '# PM_COMMAND_FORWARDING_VERSION=2026-09-25.v1' in patched
    assert "if intent == 'conversation_intake':" not in patched
    assert "'classification_hint': str(classification_hint or '')[:100]" in patched
    assert "'artifact_path': str(artifact_path or '')[:4000]" in patched
    py_compile.compile(str(native/'tools_projectmanager.py'),doraise=True)
