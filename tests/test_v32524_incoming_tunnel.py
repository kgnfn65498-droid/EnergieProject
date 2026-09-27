from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'tools/release_32524_incoming_tunnel.sh'
CP_SRC = ROOT / 'tools/control_plane'
FP = 'bba109cac86821cdbb91be11fa4a06a411aee2a9a7b09174dc7ebc393cd60e0e'
STALE_FP = '0dc5d7d08afedd2538b667cf973b8ff21839bde3456b2aae2b3179d3faccd325'


def _w(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _fixture(tmp_path: Path):
    root = tmp_path / 'project'
    _w(root/'App/VERSIE.txt', '32.5.23\n')
    (root/'Inbox/incoming').mkdir(parents=True)
    (root/'Inbox/processing').mkdir(parents=True)
    cp = root/'Data/03_Systeem/Projectmanager/ControlPlane'
    cp.mkdir(parents=True)
    for name in ('control_plane.py','control_plane_release_bridge.py','release_scoped_auth.py'):
        shutil.copy2(CP_SRC/name, cp/name)
    shutil.copy2(ROOT/'tests/fixtures/pre32524/qnap_control_plane_bootstrap_current.py', cp/'qnap_control_plane_bootstrap.py')
    carrier = root/'Data/03_Systeem/Projectmanager/Maintenance/RecoveryCarrier32_5_24/qnap_control_plane_bootstrap.py'
    carrier.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(CP_SRC/'qnap_control_plane_bootstrap.py', carrier)
    rc = root/'Data/03_Systeem/Projectmanager/ReleaseController'
    _w(rc/'control_plane_restart_attempt.json', json.dumps({
        'backup_container':'energie-control-plane-type2-legacy-'+STALE_FP[:12],
        'expected_fingerprint':STALE_FP,'retry_allowed':False,'status':'ATTEMPTING'
    }, indent=2))
    _w(rc/'runtime.json', json.dumps({'status':'BLOCKED','phase':'COMPLETE','reason':'control_plane_prepare_failed:RuntimeError'}, indent=2))
    _w(rc/'current.json', json.dumps({'to_version':'32.5.23','status':'COMPLETE','phase':'COMPLETE'}, indent=2))
    tunnel = root/'Data/03_Systeem/Projectmanager/Maintenance/release_32_5_24_tunnel.sh'
    tunnel.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCRIPT, tunnel)
    tunnel.chmod(0o755)

    fakebin = tmp_path/'bin'; fakebin.mkdir()
    state = tmp_path/'docker_state.json'
    state.write_text(json.dumps({'energie-release-watcher':True,'energie-control-plane':True}), encoding='utf-8')
    docker = fakebin/'docker'
    docker.write_text(r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
state_path=Path(os.environ['FAKE_DOCKER_STATE']); root=Path(os.environ['FAKE_ROOT'])
def load(): return json.loads(state_path.read_text())
def save(s): state_path.write_text(json.dumps(s))
a=sys.argv[1:]; s=load()
if a[:2]==['image','inspect']: sys.exit(0)
if a and a[0]=='inspect':
    if '-f' in a:
        name=a[-1]
        if name not in s: sys.exit(1)
        fmt=a[a.index('-f')+1]
        if 'Running' in fmt: print('true' if s[name] else 'false')
        elif 'Health' in fmt: print('healthy' if s[name] else 'none')
        sys.exit(0)
    sys.exit(0 if a[-1] in s else 1)
if a and a[0]=='stop':
    name=a[-1]
    if name not in s: sys.exit(1)
    if name=='energie-release-watcher' and os.environ.get('FAKE_RESYNC_ON_WATCHER_STOP')=='1':
        src=Path(os.environ['FAKE_OLD_QNAP_SOURCE'])
        dst=root/'Data/03_Systeem/Projectmanager/ControlPlane/qnap_control_plane_bootstrap.py'
        dst.write_bytes(src.read_bytes())
    s[name]=False; save(s); sys.exit(0)
if a and a[0]=='rename':
    old,new=a[-2],a[-1]
    if old not in s or new in s: sys.exit(1)
    s[new]=s.pop(old); save(s); sys.exit(0)
if a and a[0]=='create':
    if os.environ.get('FAKE_FAIL_CREATE')=='1': sys.exit(1)
    name=a[a.index('--name')+1]
    if name in s: sys.exit(1)
    s[name]=False; save(s); sys.exit(0)
if a and a[0]=='start':
    name=a[-1]
    if name not in s: sys.exit(1)
    s[name]=True; save(s)
    if name=='energie-control-plane':
        p=root/'Data/03_Systeem/Projectmanager/ControlPlane/Runtime/runtime.json'; p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(json.dumps({'loaded_fingerprint':'bba109cac86821cdbb91be11fa4a06a411aee2a9a7b09174dc7ebc393cd60e0e'}))
    if name=='energie-release-watcher':
        p=root/'Data/03_Systeem/Projectmanager/ReleaseController/runtime.json'
        p.write_text(json.dumps({'status':'IDLE','phase':'IDLE'}))
    sys.exit(0)
if a and a[0]=='rm':
    name=a[-1]; s.pop(name,None); save(s); sys.exit(0)
sys.exit(2)
''', encoding='utf-8')
    docker.chmod(0o755)
    env=os.environ.copy(); env['PATH']=str(fakebin)+os.pathsep+env['PATH']; env['FAKE_DOCKER_STATE']=str(state); env['FAKE_ROOT']=str(root); env['FAKE_OLD_QNAP_SOURCE']=str(ROOT/'tests/fixtures/pre32524/qnap_control_plane_bootstrap_current.py')
    return root,tunnel,state,env


def test_32524_tunnel_shell_syntax_green():
    subprocess.run(['sh','-n',str(SCRIPT)], check=True)


def test_32524_tunnel_check_only_is_read_only(tmp_path):
    root,tunnel,state,env=_fixture(tmp_path)
    before=(root/'Data/03_Systeem/Projectmanager/ControlPlane/qnap_control_plane_bootstrap.py').read_bytes()
    out=subprocess.run(['sh',str(tunnel),'--check-only'], env=env, text=True, capture_output=True, check=True)
    assert 'RELEASE_32524_TUNNEL_CHECK_ONLY_GREEN' in out.stdout
    assert (root/'Data/03_Systeem/Projectmanager/ControlPlane/qnap_control_plane_bootstrap.py').read_bytes()==before
    assert json.loads(state.read_text())=={'energie-release-watcher':True,'energie-control-plane':True}


def test_32524_tunnel_repairs_runtime_then_leaves_incoming_empty(tmp_path):
    root,tunnel,state,env=_fixture(tmp_path)
    out=subprocess.run(['sh',str(tunnel)], env=env, text=True, capture_output=True, check=True, timeout=20)
    assert 'RELEASE_32524_TUNNEL_GREEN' in out.stdout
    assert not list((root/'Inbox/incoming').glob('*.zip'))
    assert not list((root/'Inbox/processing').glob('*.zip'))
    runtime=json.loads((root/'Data/03_Systeem/Projectmanager/ReleaseController/runtime.json').read_text())
    assert runtime=={'status':'IDLE','phase':'IDLE'}
    cp_runtime=json.loads((root/'Data/03_Systeem/Projectmanager/ControlPlane/Runtime/runtime.json').read_text())
    assert cp_runtime['loaded_fingerprint']==FP
    assert (root/'Data/03_Systeem/Projectmanager/ControlPlane/qnap_control_plane_bootstrap.py').read_bytes()==(CP_SRC/'qnap_control_plane_bootstrap.py').read_bytes()
    docker=json.loads(state.read_text())
    assert docker['energie-release-watcher'] is True
    assert docker['energie-control-plane'] is True
    assert any(k.startswith('energie-control-plane-pre32524-') for k in docker)


def test_32524_tunnel_rolls_back_if_new_control_plane_create_fails(tmp_path):
    root,tunnel,state,env=_fixture(tmp_path); env['FAKE_FAIL_CREATE']='1'
    original=(root/'Data/03_Systeem/Projectmanager/ControlPlane/qnap_control_plane_bootstrap.py').read_bytes()
    out=subprocess.run(['sh',str(tunnel)], env=env, text=True, capture_output=True)
    assert out.returncode != 0
    assert 'control_plane_create_failed' in out.stderr
    assert (root/'Data/03_Systeem/Projectmanager/ControlPlane/qnap_control_plane_bootstrap.py').read_bytes()==original
    docker=json.loads(state.read_text())
    assert docker['energie-release-watcher'] is True
    assert docker['energie-control-plane'] is True
    attempt=json.loads((root/'Data/03_Systeem/Projectmanager/ReleaseController/control_plane_restart_attempt.json').read_text())
    assert attempt['status']=='ATTEMPTING'


def test_32524_tunnel_quiesces_release_writer_before_carrier_install(tmp_path):
    root,tunnel,state,env=_fixture(tmp_path)
    env['FAKE_RESYNC_ON_WATCHER_STOP']='1'
    out=subprocess.run(['sh',str(tunnel)], env=env, text=True, capture_output=True, check=True, timeout=25)
    assert 'RELEASE_32524_TUNNEL_GREEN' in out.stdout
    assert (root/'Data/03_Systeem/Projectmanager/ControlPlane/qnap_control_plane_bootstrap.py').read_bytes()==(CP_SRC/'qnap_control_plane_bootstrap.py').read_bytes()
