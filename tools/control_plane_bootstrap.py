from __future__ import annotations
from system_path_contract import project_system_path
import http.client,json,os,socket,time
from pathlib import Path
import control_plane_runtime_guard
from control_plane_binding_recreate import recreate_for_binding
from control_plane_source_sync import sync_control_plane_source

CONTAINER='energie-control-plane'
SOCKET='/var/run/docker.sock'

class _Conn(http.client.HTTPConnection):
    def __init__(self):super().__init__('localhost',timeout=30)
    def connect(self):
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);sock.settimeout(self.timeout);sock.connect(SOCKET);self.sock=sock

def _request(method,path,ok,payload=None):
    c=_Conn()
    try:
        body=b'';headers={}
        if payload is not None:
            body=json.dumps(payload,separators=(',',':')).encode('utf-8')
            headers={'Content-Type':'application/json','Content-Length':str(len(body))}
        c.request(method,path,body=body,headers=headers);r=c.getresponse();raw=r.read()
        if r.status not in ok:raise RuntimeError(f'control_plane_bootstrap_http_{r.status}')
        return json.loads(raw.decode()) if raw else {}
    finally:c.close()

def _atomic(path:Path,payload:dict):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise RuntimeError('unsafe bootstrap evidence path')
    tmp=path.with_name(path.name+f'.tmp-{os.getpid()}')
    try:
        tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
        os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)

def _optional_json(path:Path)->dict:
    try:
        if path.is_symlink() or not path.is_file():return {}
        value=json.loads(path.read_text(encoding='utf-8'))
    except Exception:return {}
    return value if isinstance(value,dict) else {}

def _clear_attempt(path:Path)->None:
    try:path.unlink(missing_ok=True)
    except OSError:pass

def _container_health(info)->tuple[bool,bool]:
    state=info.get('State') if isinstance(info,dict) else {}
    if not isinstance(state,dict):return False,False
    running=state.get('Running') is True
    health=state.get('Health') if isinstance(state.get('Health'),dict) else None
    healthy=running and (health is None or str(health.get('Status') or '').lower()=='healthy')
    return running,healthy

def _existing_container_info()->dict:
    info=_request('GET',f'/containers/{CONTAINER}/json',(200,))
    return info if isinstance(info,dict) else {}

def _existing_container_health()->tuple[bool,bool]:
    return _container_health(_existing_container_info())

def _arg_value(cmd,flag):
    if not isinstance(cmd,list):return ''
    try:i=cmd.index(flag)
    except ValueError:return ''
    return str(cmd[i+1]) if i+1<len(cmd) else ''

def _mapping_active(root:Path)->bool:
    legacy=(Path(root).resolve()/'Inbox/control_plane')
    return project_system_path(root,'Inbox/control_plane')!=legacy

def _binding_current(root:Path,info:dict)->bool:
    if not _mapping_active(root):return True
    config=info.get('Config') if isinstance(info,dict) else {}
    host=info.get('HostConfig') if isinstance(info,dict) else {}
    cmd=config.get('Cmd') if isinstance(config,dict) else []
    binds=host.get('Binds') if isinstance(host,dict) else []
    if _arg_value(cmd,'--runtime-root')!='/control-plane-runtime':return False
    if _arg_value(cmd,'--release-controller-root')!='/release-controller':return False
    if _arg_value(cmd,'--native-mcp-runtime-root')!='/native-mcp-runtime':return False
    required=(':/control-plane-runtime:rw',':/release-controller:ro',':/native-mcp-runtime:ro')
    return all(any(str(bind).endswith(suffix) for bind in (binds or [])) for suffix in required)

def ensure_control_plane_current(root:Path|str,*,timeout_seconds=90.0)->dict:
    root=Path(root)
    sync=sync_control_plane_source(root)
    first=control_plane_runtime_guard.probe(root,stale_seconds=30)
    container_info=_existing_container_info();running,healthy=_container_health(container_info)
    if not running:
        raise RuntimeError('existing control-plane container is not running')

    expected=str(first.get('expected_fingerprint') or '').lower()
    loaded=str(first.get('loaded_fingerprint') or '').lower()
    if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
        raise RuntimeError('control-plane expected fingerprint invalid')

    attempt_path=project_system_path(root, 'Inbox/release_controller/control_plane_restart_attempt.json')
    stale_but_exact=(
        first.get('ready') is not True
        and first.get('reason')=='runtime_heartbeat_stale'
        and healthy
        and loaded==expected
    )
    restarted=False;recreated=False
    direct_runtime_probe=False
    binding_current=_binding_current(root,container_info)

    if not binding_current:
        final,recreated=recreate_for_binding(
            root=root,info=container_info,expected=expected,attempt_path=attempt_path,timeout_seconds=timeout_seconds,
            request=_request,optional_json=_optional_json,atomic=_atomic,clear_attempt=_clear_attempt,
            probe=control_plane_runtime_guard.probe,existing_info=_existing_container_info,
            container_health=_container_health,binding_current=_binding_current,
        )
        healthy=True
    elif first.get('ready') is True and healthy:
        final=first
        _clear_attempt(attempt_path)
    elif stale_but_exact:
        # Heartbeat age is observability only. Docker health plus exact loaded
        # fingerprint is the on-demand actuator proof; do not restart for age.
        final=first
        direct_runtime_probe=True
        _clear_attempt(attempt_path)
    else:
        previous=_optional_json(attempt_path)
        if (
            str(previous.get('expected_fingerprint') or '').lower()==expected
            and previous.get('retry_allowed') is False
        ):
            raise RuntimeError('control-plane bounded restart already attempted for expected fingerprint')

        attempt={
            'schema':'energie_control_plane_restart_attempt_v1',
            'expected_fingerprint':expected,
            'loaded_fingerprint_before':loaded or None,
            'reason_before':first.get('reason'),
            'status':'ATTEMPTING',
            'restart_performed':False,
            'retry_allowed':False,
            'started_at_epoch':time.time(),
        }
        _atomic(attempt_path,attempt)
        try:
            _request('POST',f'/containers/{CONTAINER}/restart?t=30',(204,))
        except Exception as exc:
            failed={**attempt,'status':'RED','side_effect_state':'RESTART_OUTCOME_UNKNOWN',
                    'error':f'{type(exc).__name__}:{exc}'}
            _atomic(attempt_path,failed)
            raise RuntimeError('control-plane bounded restart outcome unknown') from exc

        restarted=True
        attempt={**attempt,'restart_performed':True,'side_effect_state':'RESTART_RETURNED'}
        _atomic(attempt_path,attempt)
        deadline=time.monotonic()+max(1.0,float(timeout_seconds));final={}
        final_healthy=False
        while time.monotonic()<deadline:
            final=control_plane_runtime_guard.probe(root,stale_seconds=30)
            try:final_running,final_healthy=_existing_container_health()
            except Exception:final_running,final_healthy=False,False
            if final_running and final_healthy and final.get('ready') is True:break
            time.sleep(0.5)
        if final.get('ready') is not True or not final_healthy:
            failed={**attempt,'status':'RED','side_effect_state':'RESTART_PERFORMED_UNPROVEN',
                    'final_reason':final.get('reason')}
            _atomic(attempt_path,failed)
            raise RuntimeError('control-plane runtime did not prove synced fingerprint and health')
        _clear_attempt(attempt_path)

    result={'schema':'energie_release_controller_control_plane_bootstrap_v1','status':'GREEN',
            'source_sync_changed':sync.get('changed') or [],'restart_performed':restarted,'recreate_performed':recreated,
            'binding_current':True,'direct_runtime_probe':direct_runtime_probe,
            'expected_fingerprint':final.get('expected_fingerprint'),'loaded_fingerprint':final.get('loaded_fingerprint')}
    _atomic(project_system_path(root, 'Inbox/release_controller/control_plane_bootstrap.json'),result)
    return result
