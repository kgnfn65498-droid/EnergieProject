from __future__ import annotations
import ast, importlib.util, json, sys, types, zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HOTFIX=ROOT/'tools/native_mcp_runtime_contract_hotfix.py'

def _extract_module():
    ns={}; exec(compile(HOTFIX.read_text(),str(HOTFIX),'exec'),ns); return ns['CLEARUP_EXPORT_MODULE']

def test_export_module_is_allowlisted_chunked_and_non_destructive(tmp_path, monkeypatch):
    project=tmp_path/'project'; system=tmp_path/'system'; project.mkdir(); system.mkdir()
    roots=[
      'Inbox/.bridge_patch_stage_20260914T171141Z',
      'Inbox/live_bridge_backup_20260914T171141Z',
      'Inbox/live_bridge_backup_queue_schema_20260914T172223Z',
      'Inbox/.release-transition.operation.lock.backup_20260914T1812Z']
    for rel in roots:
        p=project/rel
        if rel.endswith('Z') and 'backup_20260914T1812Z' in rel: p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b'')
        else: p.mkdir(parents=True,exist_ok=True); (p/'payload.txt').write_text(rel)
    reg=types.ModuleType('registry')
    class M:
        def tool(self,annotations=None): return lambda f:f
    reg.mcp=M(); reg.READ_ONLY_ANNOTATIONS={}; reg.WRITE_ANNOTATIONS={}; sys.modules['registry']=reg
    monkeypatch.setenv('ENERGIE_PROJECT_ROOT',str(project)); monkeypatch.setenv('ENERGIE_SYSTEM_ROOT',str(system))
    mod=types.ModuleType('tools_clearup_export_test'); exec(compile(_extract_module(),'tools_clearup_export.py','exec'),mod.__dict__)
    before={r:(project/r).exists() for r in roots}
    result=mod.clearup_prepare_recovery_export('ClearUp_001')
    assert result['status']=='GREEN' and result['deletion_performed'] is False
    assert all((project/r).exists() for r in roots) and before=={r:True for r in roots}
    info=mod.clearup_recovery_export_info('ClearUp_001'); assert info['sha256']==result['sha256']
    out=system/'Projectmanager/ClearUp/Exports'/result['artifact']
    with zipfile.ZipFile(out) as z:
        manifest=json.loads(z.read('CLEARUP_MANIFEST.json')); assert manifest['roots']==roots
        assert set(r for r in roots if (project/r).is_file()).issubset(set(z.namelist()))
    chunks=[]; offset=0
    while True:
        c=mod.clearup_recovery_export_chunk('ClearUp_001',offset,1024); chunks.append(c); offset=c['next_offset']
        assert c['artifact_sha256']==result['sha256']
        if c['eof']: break
    import base64,hashlib
    data=b''.join(base64.b64decode(c['base64']) for c in chunks)
    assert hashlib.sha256(data).hexdigest()==result['sha256'] and data==out.read_bytes()

def test_runtime_fingerprint_and_server_import_are_patched():
    text=HOTFIX.read_text()
    assert '"tools_clearup_export.py"' in text
    assert 'import tools_clearup_export  # noqa: F401' in text
