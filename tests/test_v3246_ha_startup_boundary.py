from __future__ import annotations
import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/'slimmemeterportal_import/rootfs/app'

def test_core_pm_web_import_does_not_require_optional_docker_modules():
    code=r'''import builtins,sys
sys.path.insert(0,%r)
real=builtins.__import__
def blocked(name,*a,**k):
    if name.endswith('docker_engine_tls_client') or name.endswith('nas_docker_tls'): raise ImportError('blocked')
    return real(name,*a,**k)
builtins.__import__=blocked
import projectmanager_v2.projectmanager_web
print('OK')''' % str(APP)
    r=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert r.returncode==0,r.stderr
    assert 'OK' in r.stdout

def test_lazy_compatibility_surface_remains_available():
    code=r'''import builtins,sys
sys.path.insert(0,%r)
real=builtins.__import__
def blocked(name,*a,**k):
    if name.endswith('docker_engine_tls_client') or name.endswith('nas_docker_tls'): raise ImportError('blocked')
    return real(name,*a,**k)
builtins.__import__=blocked
import projectmanager_v2.projectmanager_web as web
assert hasattr(web,'DockerTlsConfig') and hasattr(web,'DockerEngineTlsClient')''' % str(APP)
    r=subprocess.run([sys.executable,'-c',code],capture_output=True,text=True)
    assert r.returncode==0,r.stderr

def test_nas_cr_service_startup_has_no_active_tls_import_dependency():
    s=(APP/'projectmanager_v2/nas_container_cr_service.py').read_text()
    assert 'docker_engine_tls_client' not in s
    assert 'nas_docker_tls' not in s
    assert "'Inbox' / 'nas_container_cr_local'" in s
    assert 'energie_nas_container_cr_local_request_v1' in s
