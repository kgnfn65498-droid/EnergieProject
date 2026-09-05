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

def test_nas_cr_service_uses_package_correct_imports():
    s=(APP/'projectmanager_v2/nas_container_cr_service.py').read_text()
    assert 'from .docker_engine_tls_client import DockerEngineTlsClient' in s
    assert 'from .nas_docker_tls import DockerTlsConfig' in s
