import base64
import hashlib
import importlib.util
import json
import os
import sys
import types
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOTFIX = ROOT / 'tools/native_mcp_runtime_contract_hotfix.py'


def _module_source():
    spec = importlib.util.spec_from_file_location('hotfix_32512', HOTFIX)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.CLEARUP_EXPORT_MODULE


def _load_export_module(tmp_path, monkeypatch):
    project = tmp_path / 'project'; project.mkdir()
    system = tmp_path / 'system'; (system / 'Projectmanager/ClearUp/Exports').mkdir(parents=True)
    reg = types.ModuleType('registry')
    class MCP:
        def tool(self, annotations=None):
            return lambda f: f
    reg.mcp = MCP(); reg.READ_ONLY_ANNOTATIONS = {}; reg.WRITE_ANNOTATIONS = {}
    sys.modules['registry'] = reg
    monkeypatch.setenv('ENERGIE_PROJECT_ROOT', str(project))
    monkeypatch.setenv('ENERGIE_SYSTEM_ROOT', str(system))
    mod = types.ModuleType('tools_clearup_export_32512')
    exec(compile(_module_source(), 'tools_clearup_export.py', 'exec'), mod.__dict__)
    return mod, project, system


def _make_type2_zip(system: Path, cid='ClearUp_002'):
    payloads = {
        'Inbox/projectmanager_v2/RuntimeV2/a.txt': b'alpha',
        'Inbox/projectmanager_v2/RuntimeV2/sub/b.bin': b'\x00\x01beta',
    }
    rows = [{'path':'Inbox/projectmanager_v2/RuntimeV2','type':'directory'}]
    for rel, data in payloads.items():
        rows.append({'path': rel, 'type':'file', 'size':len(data), 'sha256':hashlib.sha256(data).hexdigest()})
    manifest = {
        'schema':'energie_clearup_type2_recovery_v1', 'classification':'TYPE2',
        'clearup_id':cid, 'plan_sha256':'a'*64, 'created_at':'2026-09-25T00:00:00+00:00',
        'items':[{'source':'Inbox/projectmanager_v2/RuntimeV2','destination':'Data/03_Systeem/Projectmanager/RuntimeV2','source_rows':rows,'reason':'test','path_key':'pm_runtime'}],
        'deletion_performed':False,
    }
    out = system / 'Projectmanager/ClearUp/Exports' / f'{cid}_Type2_recovery.zip'
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('TYPE2_MANIFEST.json', json.dumps(manifest))
        for rel, data in payloads.items():
            z.writestr('original/' + rel, data)
    return out, manifest


def test_direct_type2_export_info_and_chunk_reconstruct_exact_zip(tmp_path, monkeypatch):
    mod, project, system = _load_export_module(tmp_path, monkeypatch)
    out, manifest = _make_type2_zip(system)
    before = hashlib.sha256(out.read_bytes()).hexdigest()
    info = mod.clearup_type2_recovery_export_info('ClearUp_002')
    assert info['status'] == 'GREEN'
    assert info['sha256'] == before
    assert info['plan_sha256'] == 'a'*64
    assert info['deletion_performed'] is False
    chunks=[]; off=0
    while True:
        c = mod.clearup_type2_recovery_export_chunk('ClearUp_002', off, 7)
        chunks.append(base64.b64decode(c['base64']))
        assert c['sha256'] == before
        off = c['next_offset']
        if c['eof']:
            break
    rebuilt = b''.join(chunks)
    assert rebuilt == out.read_bytes()
    assert hashlib.sha256(rebuilt).hexdigest() == before
    assert hashlib.sha256(out.read_bytes()).hexdigest() == before


def test_direct_type2_export_rejects_unsupported_and_corrupt_payload(tmp_path, monkeypatch):
    mod, project, system = _load_export_module(tmp_path, monkeypatch)
    try:
        mod.clearup_type2_recovery_export_info('ClearUp_013')
    except ValueError as exc:
        assert 'unsupported' in str(exc)
    else:
        raise AssertionError('unsupported Type2 id accepted')
    out, manifest = _make_type2_zip(system)
    with zipfile.ZipFile(out, 'a') as z:
        z.writestr('original/Inbox/projectmanager_v2/RuntimeV2/a.txt', b'wrong')
    try:
        mod.clearup_type2_recovery_export_info('ClearUp_002')
    except ValueError as exc:
        assert 'mismatch' in str(exc) or 'verification' in str(exc) or 'incomplete' in str(exc)
    else:
        raise AssertionError('corrupt Type2 recovery payload accepted')


def test_type1_export_contract_retained():
    src = _module_source()
    assert 'def clearup_prepare_recovery_export' in src
    assert 'def clearup_recovery_export_chunk' in src
    assert 'def clearup_type2_recovery_export_chunk' in src
    assert 'TYPE2_CHAT_EXPORT_VERSION=2026-09-25.v1' in src
