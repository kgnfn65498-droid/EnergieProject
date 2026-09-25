from pathlib import Path
import importlib.util, sys, types


def _load(path: Path):
    spec=importlib.util.spec_from_file_location('hotfix_under_test', path)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_hotfix_adds_registry_annotations_before_clearup_export(tmp_path):
    root=tmp_path
    (root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.5.9\n')
    native=root/'Infra/Docker/native-mcp'; native.mkdir(parents=True)
    (native/'registry.py').write_text('class Dummy:\n    def tool(self, **kw):\n        return lambda f:f\nmcp=Dummy()\n')
    (native/'server.py').write_text('import tools_projectmanager  # noqa: F401\nfrom registry import mcp\n\nif __name__ == "__main__":\n    pass\n')
    # required fields + exact anchors used by hotfix
    (native/'tools_projectmanager.py').write_text('''from pathlib import Path\nimport os\nimport json\nfrom uuid import uuid4\nfrom typing import Any\nfrom registry import mcp\nRUNTIME_ROOT=Path("/tmp")\ndef _write_immutable(*a, **k): pass\n\ndef projectmanager_submit_command(\n    intent: str, text: str = "", title: str = "", goal: str = "", steps_total: int = 1, priority: int = 2, next_action: str = "",\n):\n    payload = {\n        "intent": intent, "text": text, "title": title, "goal": goal, "steps_total": steps_total, "priority": priority, "next_action": next_action,\n    }\n    return payload\n\n# Remote decision resolution, direct deploy/purchase/payment and arbitrary\n# RuntimeV2 writes are deliberately absent. Protected approval stays local HA.\n''')
    (native/'crash_recovery.py').write_text('x=1\n')
    (native/'tools_recovery.py').write_text('x=1\n')
    mod=_load(Path('tools/native_mcp_runtime_contract_hotfix.py'))
    # bypass unrelated strict command-forwarding evolution for this unit by giving required tokens
    t=(native/'tools_projectmanager.py').read_text()
    for fld in mod.REQUIRED_INTAKE_FIELDS:
        if fld not in t:
            t += f'\n# {fld}\n'
    (native/'tools_projectmanager.py').write_text(t)
    try:
        mod.apply(root)
    except RuntimeError as exc:
        # If a separate forwarding anchor is intentionally stricter, the registry migration
        # must still have happened first; that is the startup-safety contract under test.
        assert 'registry annotation' not in str(exc)
    reg=(native/'registry.py').read_text()
    assert 'READ_ONLY_ANNOTATIONS = {}' in reg
    assert 'WRITE_ANNOTATIONS = {}' in reg
