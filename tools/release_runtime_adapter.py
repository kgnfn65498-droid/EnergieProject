from __future__ import annotations
import hashlib,json,os
from pathlib import Path
from release_controller import Outcome,ReleaseState

MCP_CONTAINER='energie-filesystem-mcp'
CONTROL_PLANE_CONTAINER='energie-control-plane'
REQUEST_REL=Path('Inbox/control_plane/requests/native_mcp_reload.json')
RESULT_REL=Path('Inbox/control_plane/results/native_mcp_reload.json')

def _json(path:Path)->dict:
    try:v=json.loads(path.read_text(encoding='utf-8'))
    except Exception:return {}
    return v if isinstance(v,dict) else {}
def _atomic(path:Path,payload:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise RuntimeError('unsafe native request path')
    tmp=path.with_name(path.name+f'.tmp-{os.getpid()}')
    try:tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)
def _rid(s:ReleaseState,expected:str)->str:
    return hashlib.sha256(f'{s.release_id}|{s.generation}|{s.artifact_sha256}|{expected}'.encode()).hexdigest()[:32]

class NativeRuntimeCoordinator:
    def __init__(self,root:Path,guard_module,control_plane_probe,control_plane_prepare=None):
        self.root=Path(root);self.guard=guard_module;self.control_plane_probe=control_plane_probe
        self.control_plane_prepare=control_plane_prepare
    def align(self,s:ReleaseState)->Outcome:
        guard=self.guard.probe(self.root)
        if guard.get('ready') is True:
            # A fenced request may outlive the restart/readback cycle when the
            # runtime becomes current before the Control Plane removes it.
            # Clean up only the exact request for this release/generation.
            expected=str(guard.get('expected_fingerprint') or '').lower()
            if len(expected)==64 and all(c in '0123456789abcdef' for c in expected):
                rid=_rid(s,expected);request_path=self.root/REQUEST_REL;current=_json(request_path)
                same_request=(
                    current.get('request_id')==rid and current.get('release_id')==s.release_id
                    and current.get('generation')==s.generation
                    and current.get('artifact_sha256')==s.artifact_sha256
                    and current.get('release_version')==s.to_version
                    and str(current.get('expected_fingerprint') or '').lower()==expected
                )
                if same_request:
                    try:request_path.unlink()
                    except FileNotFoundError:pass
            return Outcome.green('native_mcp_current')
        if self.control_plane_prepare is not None:
            try:self.control_plane_prepare()
            except Exception as exc:
                return Outcome.blocked(
                    'control_plane_prepare_failed:'+type(exc).__name__,
                    'restore existing control-plane capability; do not create a second release or recreate chain',
                )
        if not self.control_plane_probe():
            return Outcome.blocked('control_plane_unavailable','restore existing control-plane capability')
        expected=str(guard.get('expected_fingerprint') or '').lower()
        if len(expected)!=64 or any(c not in '0123456789abcdef' for c in expected):
            return Outcome.blocked('native_expected_fingerprint_invalid')
        rid=_rid(s,expected);result=_json(self.root/RESULT_REL)
        same_fence=(
            result.get('request_id')==rid and result.get('release_id')==s.release_id
            and result.get('generation')==s.generation
            and result.get('artifact_sha256')==s.artifact_sha256
            and result.get('release_version')==s.to_version
        )
        exact=(same_fence and result.get('status')=='GREEN' and result.get('ok') is True
            and str(result.get('runtime_fingerprint') or '').lower()==expected)
        if exact:
            if self.guard.probe(self.root).get('ready') is True:
                request_path=self.root/REQUEST_REL
                current=_json(request_path)
                if current.get('request_id')==rid:
                    try:request_path.unlink()
                    except FileNotFoundError:pass
                return Outcome.green('native_mcp_reload_proven','native_mcp_current')
            return Outcome.blocked('native_mcp_reload_result_without_guard_match')
        if same_fence and result.get('retry_allowed') is False:
            if result.get('status')=='RED':
                return Outcome.blocked(
                    'native_mcp_reload_unproven',
                    'await exact runtime readback or inspect the single fenced attempt; do not restart',
                )
            if result.get('status')=='ATTEMPTING':
                return Outcome.waiting('native_mcp_reload_readback_pending','native_mcp_restart_fenced')
        request={'schema':'energie_control_plane_release_request_v1','authorization':'release_controller',
            'action':'native_mcp_reload','container':MCP_CONTAINER,'request_id':rid,'release_id':s.release_id,
            'generation':s.generation,'release_version':s.to_version,'artifact_sha256':s.artifact_sha256,
            'expected_fingerprint':expected}
        current=_json(self.root/REQUEST_REL)
        if current and current!=request:
            # One request file, one generation. Never overwrite a different live request.
            return Outcome.blocked('native_mcp_request_conflict','inspect existing single control-plane request')
        if not current:_atomic(self.root/REQUEST_REL,request)
        return Outcome.waiting('native_mcp_reload_pending','native_mcp_reload_requested')
