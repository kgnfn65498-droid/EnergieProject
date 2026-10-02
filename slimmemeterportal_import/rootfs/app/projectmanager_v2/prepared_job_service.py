from __future__ import annotations
from system_path_contract import project_system_path

import hashlib
import json
import os
import re
import time
from pathlib import Path

REQUEST_SCHEMA='energie_prepared_job_request_v2'
AUTH_SCHEMA='energie_prepared_job_authorization_v1'
MANIFEST_SCHEMA='energie_prepared_job_manifest_v1'
RESULT_SCHEMA='energie_prepared_job_result_v2'
ACTION='prepared_job_run'
OPERATIONS={'AUDIT','TEST','BUILD'}
REQUEST_ID_RE=re.compile(r'^[0-9a-f]{32}$')
SHA256_RE=re.compile(r'^[0-9a-f]{64}$')
VERSION_RE=re.compile(r'^[0-9]+[.][0-9]+[.][0-9]+$')
LEASE_SECONDS=900
CONTROL_PLANE_ENSURE_SCHEMA='energie_control_plane_ensure_request_v1'
CONTROL_PLANE_ENSURE_RESULT_SCHEMA='energie_control_plane_ensure_result_v1'
CONTROL_PLANE_TARGET='energie-control-plane'


def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda:handle.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def _canonical(payload:dict)->bytes:
    return json.dumps(payload,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')


def _load(path:Path)->dict|None:
    if path.is_symlink() or not path.is_file():
        return None
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,UnicodeError,json.JSONDecodeError):
        return None
    return value if isinstance(value,dict) else None


def _write_immutable(path:Path,payload:dict,*,mode:int=0o644)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():
        raise RuntimeError('prepared_job_path_symlink')
    if path.exists():
        if _load(path)!=payload:
            raise RuntimeError('prepared_job_existing_identity_conflict')
        return
    raw=(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode('utf-8')
    fd=os.open(str(path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
    try:
        with os.fdopen(fd,'wb') as handle:
            handle.write(raw);handle.flush();os.fsync(handle.fileno())
        os.chmod(path,mode)
    except Exception:
        try:path.unlink()
        except OSError:pass
        raise


def _authorization_sha(payload:dict)->str:
    identity=dict(payload)
    identity.pop('authorization_sha256',None)
    return hashlib.sha256(_canonical(identity)).hexdigest()


class ConfiguredPreparedJobService:
    """Typed PM->ControlPlane bridge using only the existing MCP command schema."""

    def __init__(self,project_root:Path|str):
        self.project_root=Path(project_root).resolve()
        self.jobs=self.project_root/'Data/03_Systeem/Projectmanager/Staging/PreparedJobs'
        self.artifacts=self.project_root/'Data/03_Systeem/Projectmanager/ReleaseArtifacts'

    def _runtime_path(self,group:str,request_id:str)->Path:
        return project_system_path(
            self.project_root,
            f'Inbox/control_plane/{group}/prepared_job_run.{request_id}.json',
        )

    def _ensure_path(self,group:str,request_id:str)->Path:
        return project_system_path(
            self.project_root,
            f'Inbox/control_plane/{group}/control_plane_ensure.{request_id}.json',
        )

    def _ensure_control_plane(self,request_id:str)->bool:
        result_path=self._ensure_path('results',request_id)
        result=_load(result_path)
        if result is not None:
            if (
                result.get('schema')!=CONTROL_PLANE_ENSURE_RESULT_SCHEMA
                or result.get('request_id')!=request_id
                or result.get('target')!=CONTROL_PLANE_TARGET
                or result.get('production_modified') is not False
            ):
                raise RuntimeError('control-plane ensure result identity/safety mismatch')
            if result.get('status')=='GREEN' and result.get('ok') is True:
                return True
            if result.get('status')=='RED':
                raise RuntimeError('control-plane ensure failed:'+str(result.get('error') or 'unknown'))
        request={
            'schema':CONTROL_PLANE_ENSURE_SCHEMA,
            'request_id':request_id,
            'action':'ensure_running',
            'target':CONTROL_PLANE_TARGET,
        }
        _write_immutable(self._ensure_path('requests',request_id),request,mode=0o644)
        return False

    def _live_release(self)->str:
        path=self.project_root/'App/VERSIE.txt'
        if path.is_symlink() or not path.is_file():
            raise RuntimeError('prepared_job_live_release_missing')
        value=path.read_text(encoding='utf-8').strip()
        if VERSION_RE.fullmatch(value) is None:
            raise RuntimeError('prepared_job_live_release_invalid')
        return value

    @staticmethod
    def _result_exact(result:dict,request:dict)->bool:
        return bool(
            result.get('schema')==RESULT_SCHEMA
            and result.get('action')==ACTION
            and all(result.get(key)==request[key] for key in (
                'request_id','task_id','operation','target_release','predecessor_release',
                'predecessor_sha256','runner_sha256','manifest_sha256','authorization_sha256'
            ))
            and result.get('network_mode')=='none'
            and result.get('project_mount')=='read_only'
            and result.get('production_modified') is False
            and result.get('container_removed') is True
        )

    @staticmethod
    def _validate_authorization(value:dict,expected:dict,*,claimed:bool)->str:
        if value.get('schema')!=AUTH_SCHEMA or value.get('status')!='AUTHORIZED' or value.get('issued_by')!='projectmanager':
            raise RuntimeError('prepared_job authorization invalid')
        for key,wanted in expected.items():
            if value.get(key)!=wanted:
                raise RuntimeError('prepared_job authorization binding mismatch:'+key)
        digest=_authorization_sha(value)
        if value.get('authorization_sha256')!=digest:
            raise RuntimeError('prepared_job authorization SHA mismatch')
        if not claimed and float(value.get('expires_at_epoch') or 0)<=time.time():
            raise RuntimeError('prepared_job authorization expired')
        return digest

    def run(self,*,task:dict,artifact_path:str,artifact_sha256:str,target_release:str,operation:str)->dict:
        task=task if isinstance(task,dict) else {}
        task_id=str(task.get('id') or '').strip()
        if not task_id or task.get('mode')!='DEVELOPMENT' or task.get('status')!='ACTIVE':
            raise RuntimeError('prepared_job active DEVELOPMENT task required')

        operation=str(operation or '').strip().upper()
        if operation not in OPERATIONS:
            raise RuntimeError('prepared_job operation invalid')
        target_release=str(target_release or '').strip()
        if VERSION_RE.fullmatch(target_release) is None:
            raise RuntimeError('prepared_job target release invalid')
        runner_sha=str(artifact_sha256 or '').strip().lower()
        if SHA256_RE.fullmatch(runner_sha) is None:
            raise RuntimeError('prepared_job runner SHA invalid')

        relative=Path(str(artifact_path or '').replace('\\','/'))
        if relative.is_absolute() or '..' in relative.parts or relative.name!='runner.py':
            raise RuntimeError('prepared_job runner path invalid')
        runner=(self.project_root/relative).resolve()
        jobs_root=self.jobs.resolve()
        if runner.parent.parent!=jobs_root or REQUEST_ID_RE.fullmatch(runner.parent.name) is None:
            raise RuntimeError('prepared_job runner path outside bounded job root')
        request_id=runner.parent.name
        if runner.is_symlink() or not runner.is_file() or _sha(runner)!=runner_sha:
            raise RuntimeError('prepared_job runner identity mismatch')

        predecessor_release=self._live_release()
        predecessor=self.artifacts/f'EnergieProject_v{predecessor_release}.zip'
        if predecessor.is_symlink() or not predecessor.is_file():
            raise RuntimeError('prepared_job predecessor artifact missing/unsafe')
        predecessor_sha=_sha(predecessor)

        manifest_path=runner.parent/'job_manifest.json'
        manifest=_load(manifest_path)
        expected_manifest={
            'schema':MANIFEST_SCHEMA,
            'request_id':request_id,
            'task_id':task_id,
            'operation':operation,
            'target_release':target_release,
            'predecessor_release':predecessor_release,
            'predecessor_sha256':predecessor_sha,
            'runner_sha256':runner_sha,
        }
        if manifest!=expected_manifest:
            raise RuntimeError('prepared_job manifest identity mismatch')
        manifest_sha=_sha(manifest_path)

        if not self._ensure_control_plane(request_id):
            return {
                'status':'PENDING','ok':None,'executed':False,
                'awaiting_control_plane':True,'awaiting_executor':False,
                'request_id':request_id,'task_id':task_id,'operation':operation,
                'target_release':target_release,'predecessor_release':predecessor_release,
                'predecessor_sha256':predecessor_sha,'runner_sha256':runner_sha,
                'manifest_sha256':manifest_sha,
            }

        bindings=dict(expected_manifest)
        bindings.pop('schema',None)
        bindings['manifest_sha256']=manifest_sha
        claim_path=self._runtime_path('claims',request_id)
        auth_path=self._runtime_path('authorizations',request_id)
        claim=_load(claim_path)
        auth=_load(auth_path)
        if claim is not None:
            auth_sha=self._validate_authorization(claim,bindings,claimed=True)
        elif auth is not None:
            auth_sha=self._validate_authorization(auth,bindings,claimed=False)
        else:
            issued=time.time()
            auth={
                **bindings,
                'schema':AUTH_SCHEMA,
                'status':'AUTHORIZED',
                'issued_by':'projectmanager',
                'issued_at_epoch':issued,
                'expires_at_epoch':issued+LEASE_SECONDS,
            }
            auth_sha=_authorization_sha(auth)
            auth['authorization_sha256']=auth_sha
            _write_immutable(auth_path,auth,mode=0o644)

        request={
            **expected_manifest,
            'schema':REQUEST_SCHEMA,
            'action':ACTION,
            'manifest_sha256':manifest_sha,
            'authorization_sha256':auth_sha,
        }
        result_path=self._runtime_path('results',request_id)
        result=_load(result_path)
        if result is not None:
            if not self._result_exact(result,request):
                raise RuntimeError('prepared_job result identity/safety mismatch')
            return dict(result)

        _write_immutable(self._runtime_path('requests',request_id),request,mode=0o644)
        return {
            'status':'PENDING','ok':None,'executed':False,'awaiting_executor':True,
            'request_id':request_id,'task_id':task_id,'operation':operation,
            'target_release':target_release,'predecessor_release':predecessor_release,
            'predecessor_sha256':predecessor_sha,'runner_sha256':runner_sha,
            'manifest_sha256':manifest_sha,'authorization_sha256':auth_sha,
        }
