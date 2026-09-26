from __future__ import annotations

import ast
import hashlib
import json
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOTFIX = ROOT / 'tools/native_mcp_runtime_contract_hotfix.py'


def _clearup_export_source() -> str:
    tree = ast.parse(HOTFIX.read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == 'CLEARUP_EXPORT_MODULE':
                    value = ast.literal_eval(node.value)
                    assert isinstance(value, str)
                    return value
    raise AssertionError('CLEARUP_EXPORT_MODULE missing')


def _module_from_source(tmp_path: Path):
    project = tmp_path / 'project'; system = tmp_path / 'system'
    project.mkdir(); system.mkdir()
    registry = types.ModuleType('registry')
    class DummyMcp:
        def tool(self, **_kwargs):
            return lambda fn: fn
    registry.mcp = DummyMcp(); registry.READ_ONLY_ANNOTATIONS = {}; registry.WRITE_ANNOTATIONS = {}
    ns = {'__name__':'native_clearup_export_32520'}
    import sys, os
    sys.modules['registry'] = registry
    old_project = os.environ.get('ENERGIE_PROJECT_ROOT'); old_system = os.environ.get('ENERGIE_SYSTEM_ROOT')
    os.environ['ENERGIE_PROJECT_ROOT']=str(project); os.environ['ENERGIE_SYSTEM_ROOT']=str(system)
    try:
        exec(compile(_clearup_export_source(), '<clearup-export>', 'exec'), ns)
    finally:
        if old_project is None: os.environ.pop('ENERGIE_PROJECT_ROOT',None)
        else: os.environ['ENERGIE_PROJECT_ROOT']=old_project
        if old_system is None: os.environ.pop('ENERGIE_SYSTEM_ROOT',None)
        else: os.environ['ENERGIE_SYSTEM_ROOT']=old_system
    return ns, system


def _write_type2_zip(path: Path, *, size: int, data: bytes) -> None:
    rel = 'Inbox/zero-byte.lock'
    manifest = {
        'schema':'energie_clearup_type2_recovery_v1','classification':'TYPE2','clearup_id':'ClearUp_012',
        'plan_sha256':'a'*64,'deletion_performed':False,
        'items':[{'source_rows':[{'path':rel,'type':'file','size':size,'sha256':hashlib.sha256(data).hexdigest()}]}],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('TYPE2_MANIFEST.json',json.dumps(manifest))
        z.writestr('original/'+rel,data)


def test_native_mcp_accepts_zero_byte_type2_payload(tmp_path):
    ns, system = _module_from_source(tmp_path)
    out = system/'Projectmanager/ClearUp/Exports/ClearUp_012_Type2_recovery.zip'
    _write_type2_zip(out,size=0,data=b'')
    info = ns['clearup_type2_recovery_export_info']('ClearUp_012')
    assert info['status'] == 'GREEN'
    assert info['sha256'] == hashlib.sha256(out.read_bytes()).hexdigest()


def test_native_mcp_still_rejects_real_size_mismatch(tmp_path):
    ns, system = _module_from_source(tmp_path)
    out = system/'Projectmanager/ClearUp/Exports/ClearUp_012_Type2_recovery.zip'
    _write_type2_zip(out,size=1,data=b'')
    try:
        ns['clearup_type2_recovery_export_info']('ClearUp_012')
    except ValueError as exc:
        assert 'size mismatch' in str(exc)
    else:
        raise AssertionError('real payload size mismatch must fail closed')


def test_runtime_hotfix_source_of_truth_contains_zero_byte_fix():
    source = _clearup_export_source()
    assert 'int(row.get("size") or -1)' not in source
    assert 'int(row.get("size") if row.get("size") is not None else -1)' in source


def test_current_release_identity():
    assert (ROOT/'VERSIE.txt').read_text().strip() == '32.5.21'
    assert (ROOT/'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt').read_text().strip() == '2.0.0-rc54'
