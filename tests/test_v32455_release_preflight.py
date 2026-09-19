from __future__ import annotations

import hashlib
import importlib.util
import sys
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT/'tests/fixtures/pre57/release_preflight.py'
EMBED_GUARD = ROOT/'tools/embedded_pm_runtime_guard.py'


def _load(path: Path, name: str):
    # Historical pre-57 fixtures must resolve their sibling guard modules,
    # independent of modules already imported by the 32.4.57 runtime tests.
    fixture_dir = str(path.parent)
    saved_path = list(sys.path)
    saved_modules = {
        key: sys.modules.get(key)
        for key in ("control_plane_runtime_guard", "embedded_pm_runtime_guard")
    }
    try:
        sys.path.insert(0, fixture_dir)
        for key in saved_modules:
            sys.modules.pop(key, None)
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path[:] = saved_path
        for key, value in saved_modules.items():
            if value is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = value


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf-8')


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _manifest_files(files: dict[str, bytes]) -> tuple[str, dict]:
    manifest = ''.join(f"{_sha(data)}  {name}\n" for name, data in sorted(files.items()))
    sums = {'files': [{'path': name, 'sha256': _sha(data)} for name, data in sorted(files.items())]}
    return manifest, sums


def _candidate(path: Path, version='32.4.55', *, corrupt_manifest=False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {'VERSIE.txt': (version+'\n').encode(), 'README.md': b'candidate\n'}
    manifest, sums = _manifest_files(payload)
    if corrupt_manifest:
        manifest = '0'*64 + '  VERSIE.txt\n' + manifest.split('\n', 1)[1]
    with zipfile.ZipFile(path,'w') as zf:
        for name, data in payload.items():
            zf.writestr(name, data)
        zf.writestr('MANIFEST.sha256', manifest)
        zf.writestr('SHA256SUMS.json', json.dumps(sums, sort_keys=True))


def _write_current_app(root: Path) -> None:
    app = root/'App'
    pm = app/'slimmemeterportal_import/rootfs/app/projectmanager_v2'
    pm.mkdir(parents=True)
    files = {
        'VERSIE.txt': b'32.4.54\n',
        'README.md': b'current\n',
        'slimmemeterportal_import/rootfs/app/projectmanager_v2/probe.py': b'VALUE = 54\n',
    }
    for rel, data in files.items():
        target = app/rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    manifest, sums = _manifest_files(files)
    (app/'MANIFEST.sha256').write_text(manifest, encoding='utf-8')
    (app/'SHA256SUMS.json').write_text(json.dumps(sums, sort_keys=True), encoding='utf-8')


def _cp_fp(cpdir: Path) -> str:
    h=hashlib.sha256()
    for name in ('control_plane.py','qnap_control_plane_bootstrap.py'):
        h.update(name.encode()+b'\0'); h.update((cpdir/name).read_bytes())
    return h.hexdigest()


def _green_root(tmp_path: Path):
    root=tmp_path
    _write_current_app(root)
    for rel in ('Inbox/incoming','Inbox/processing','Data/03_Systeem/Projectmanager/CommandIngress'):
        (root/rel).mkdir(parents=True, exist_ok=True)
    candidate=root/'Inbox/incoming/EnergieProject_v32.4.55.zip'; _candidate(candidate)
    _write(root/'Inbox/operating_mode/operating_mode_state.json', {
        'base_mode':'DEVELOPMENT','effective_mode':'DEVELOPMENT','reconciliation_status':'ok','drift':[]
    })
    _write(root/'Inbox/operating_mode/release_validation_hold.json', {
        'active':False,'release_version':'32.4.54','validation_status':'ok','reconcile_status':'ok'
    })
    _write(root/'Inbox/atomic_app_swap_state.json', {
        'state':'ACCEPTED','from_version':'32.4.53','to_version':'32.4.54'
    })
    _write(root/'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json', {
        'lifecycle_state':'COMPLETE','phase':'COMPLETE','phase_status':'GREEN','to_release':'32.4.54',
        'generation_id':'old-complete','revision':100,'current_ticket':None
    })
    _write(root/'Inbox/projectmanager_v2/RuntimeV2/state/tasks.json', {'schema':1,'tasks':[]})
    generation='pm-final'
    updated=datetime.now(timezone.utc).isoformat()
    _write(root/'Inbox/projectmanager_v2/RuntimeV2/status/current.json', {
        'updated_at':updated,'cycle_generation':generation,
        'provenance':{'generation':generation,'phase':'FINAL'},
        'release':{'version':'32.4.54','active_verified':True},
        'self_audit':{'status':'GREEN','cycle_generation':generation,'provenance':{'generation':generation,'phase':'FINAL'}},
        'health':{'status':'GREEN','checks':[
            {'name':'watcher_container_contract','status':'GREEN'},
            {'name':'native_mcp_runtime','status':'GREEN'},
            {'name':'projectmanager_driver_liveness','status':'GREEN'},
            {'name':'release_watcher','status':'GREEN'},
            {'name':'command_ingress_consumer','status':'GREEN'},
        ]},
    })
    _write(root/'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json', {
        'status':'GREEN','status_updated_at':updated,'cycle_generation':generation,
        'provenance':{'generation':generation,'phase':'FINAL'},'missing':[],'invalid':[],'warnings':[]
    })
    _write(root/'Inbox/native_mcp_runtime/runtime_guard.json', {
        'status':'GREEN','ready':True,'expected_fingerprint':'a'*64,'runtime_fingerprint':'a'*64
    })
    _write(root/'Inbox/watcher_container_contract.json', {'status':'GREEN','ready':True,'contract_version':3})
    _write(root/'Inbox/projectmanager_v2/RuntimeV2/commands/ingress_receipts.json', {'schema':1,'items':{}})
    _write(root/'Inbox/projectmanager_v2/RuntimeV2/commands/queue.json', {'schema':1,'items':[]})
    cpdir=root/'Data/03_Systeem/Projectmanager/ControlPlane'; cpdir.mkdir(parents=True)
    (cpdir/'control_plane.py').write_text('cp'); (cpdir/'qnap_control_plane_bootstrap.py').write_text('boot')
    _write(root/'Inbox/control_plane/runtime.json', {
        'schema':'energie_control_plane_runtime_v1','loaded_fingerprint':_cp_fp(cpdir),
        'heartbeat_at_epoch':time.time(),'pid':123
    })
    embed=_load(EMBED_GUARD,'preflight_embed_setup')
    efp=embed.expected_fingerprint(root)
    _write(root/'Inbox/projectmanager_v2/RuntimeV2/embedded_runtime/current.json', {
        'schema':'energie_embedded_pm_runtime_v1','status':'GREEN','loaded_runtime_fingerprint':efp,
        'runtime_release_version':'32.4.54','cycle_generation':generation,
        'provenance':{'generation':generation,'phase':'FINAL'},'observed_at_epoch':time.time(),
    })
    return root,candidate


def test_preflight_green_proves_exact_current_and_candidate_hashes(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_green')
    root,candidate=_green_root(tmp_path)
    result=mod.probe(root,candidate,now=time.time())
    assert result['status']=='GREEN'
    assert result['ready'] is True
    assert result['current_version']=='32.4.54'
    assert result['candidate_version']=='32.4.55'
    assert result['candidate_sha256']==hashlib.sha256(candidate.read_bytes()).hexdigest()
    assert len(result['current_manifest_sha256'])==64
    assert len(result['candidate_manifest_sha256'])==64
    assert result['current_source_integrity']=='GREEN'
    assert result['candidate_integrity']=='GREEN'


def test_preflight_from_32_4_54_does_not_require_55_only_command_ingress_health_check(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_legacy54_health')
    root,candidate=_green_root(tmp_path)
    status_path=root/'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
    status=json.loads(status_path.read_text())
    status['health']['checks']=[
        item for item in status['health']['checks']
        if item.get('name') != 'command_ingress_consumer'
    ]
    _write(status_path,status)
    result=mod.probe(root,candidate,now=time.time())
    assert result['status']=='GREEN', result
    assert result['ready'] is True
    assert 'command_ingress_consumer_not_green' not in result['blockers']


def test_preflight_blocks_nonterminal_previous_transition(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_transition')
    root,candidate=_green_root(tmp_path)
    path=root/'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json'
    state=json.loads(path.read_text()); state.update(lifecycle_state='BLOCKED',phase='NAS_CR',phase_status='RED')
    _write(path,state)
    result=mod.probe(root,candidate,now=time.time())
    assert result['status']=='BLOCKED'
    assert 'previous_transition_not_terminal' in result['blockers']


def test_preflight_blocks_unconsumed_command_ingress_even_when_pm_heartbeat_is_green(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_ingress')
    root,candidate=_green_root(tmp_path)
    _write(root/'Data/03_Systeem/Projectmanager/CommandIngress/pending.json', {
        'schema':'energie_pmv2_command_ingress_v1','id':'pending','command':{'intent':'status'}
    })
    result=mod.probe(root,candidate,now=time.time())
    assert result['status']=='BLOCKED'
    assert 'command_ingress_unconsumed' in result['blockers']


def test_preflight_blocks_stale_loaded_control_plane(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_cp')
    root,candidate=_green_root(tmp_path)
    marker=root/'Inbox/control_plane/runtime.json'; payload=json.loads(marker.read_text()); payload['loaded_fingerprint']='0'*64; _write(marker,payload)
    result=mod.probe(root,candidate,now=time.time())
    assert result['status']=='BLOCKED'
    assert 'control_plane_runtime_not_green' in result['blockers']


def test_preflight_blocks_nonfinal_pm_or_mode_drift(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_pm')
    root,candidate=_green_root(tmp_path)
    status_path=root/'Inbox/projectmanager_v2/RuntimeV2/status/current.json'; status=json.loads(status_path.read_text()); status['provenance']['phase']='BUILDING'; _write(status_path,status)
    mode_path=root/'Inbox/operating_mode/operating_mode_state.json'; mode=json.loads(mode_path.read_text()); mode['drift']=['unexpected']; _write(mode_path,mode)
    result=mod.probe(root,candidate,now=time.time())
    assert result['status']=='BLOCKED'
    assert 'projectmanager_final_snapshot_invalid' in result['blockers']
    assert 'operating_mode_not_clean_development' in result['blockers']


def test_preflight_blocks_stale_embedded_pm_loaded_code(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_embedded')
    root,candidate=_green_root(tmp_path)
    marker=root/'Inbox/projectmanager_v2/RuntimeV2/embedded_runtime/current.json'
    payload=json.loads(marker.read_text()); payload['loaded_runtime_fingerprint']='0'*64; _write(marker,payload)
    result=mod.probe(root,candidate,now=time.time())
    assert 'embedded_pm_runtime_not_green' in result['blockers']


def test_preflight_blocks_stale_watcher_health_even_if_container_contract_is_green(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_watcher')
    root,candidate=_green_root(tmp_path)
    status_path=root/'Inbox/projectmanager_v2/RuntimeV2/status/current.json'; status=json.loads(status_path.read_text())
    for check in status['health']['checks']:
        if check['name']=='release_watcher': check['status']='RED'
    _write(status_path,status)
    result=mod.probe(root,candidate,now=time.time())
    assert 'watcher_runtime_not_green' in result['blockers']


def test_preflight_blocks_stale_release_owned_active_task(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_task')
    root,candidate=_green_root(tmp_path)
    _write(root/'Inbox/projectmanager_v2/RuntimeV2/state/tasks.json', {'schema':1,'tasks':[{
        'id':'old','status':'ACTIVE','title':'32.4.53 old build','release_owner':None,
        'build_metadata':{'release_version':'32.4.53'},
    }]})
    result=mod.probe(root,candidate,now=time.time())
    assert 'stale_release_owned_task' in result['blockers']


def test_preflight_blocks_stale_pm_snapshot_even_if_final_fields_look_green(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_pm_stale')
    root,candidate=_green_root(tmp_path)
    old='2026-01-01T00:00:00+00:00'
    for rel in ('status/current.json','self_audit/current.json'):
        path=root/'Inbox/projectmanager_v2/RuntimeV2'/rel; payload=json.loads(path.read_text())
        if rel.startswith('status'): payload['updated_at']=old
        else: payload['status_updated_at']=old
        _write(path,payload)
    result=mod.probe(root,candidate,now=time.time())
    assert 'projectmanager_final_snapshot_invalid' in result['blockers']


def test_preflight_blocks_candidate_with_invalid_manifest(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_bad_candidate')
    root,candidate=_green_root(tmp_path)
    _candidate(candidate, corrupt_manifest=True)
    result=mod.probe(root,candidate,now=time.time())
    assert 'candidate_integrity_invalid' in result['blockers']


def test_preflight_blocks_current_source_manifest_mismatch(tmp_path: Path):
    mod=_load(PREFLIGHT,'preflight55_bad_source')
    root,candidate=_green_root(tmp_path)
    (root/'App/README.md').write_text('tampered\n')
    result=mod.probe(root,candidate,now=time.time())
    assert 'current_source_integrity_invalid' in result['blockers']
