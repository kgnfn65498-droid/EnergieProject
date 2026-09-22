#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,http.client,json,os,socket,time,zipfile
from pathlib import Path

import atomic_app_swap
import native_mcp_runtime_guard
from atomic_release_adapter import AtomicReleaseAdapter
from controller_lock import controller_lease
from control_plane_bootstrap import ensure_control_plane_current
from ha_delivery_adapter import HADelivery
from ingress_policy import IncomingItem,IngressDecision,decide_incoming
from minimal_release_preflight import verify_candidate
from release_controller import ReleaseController,ReleaseState,Status
from release_runtime_adapter import NativeRuntimeCoordinator
from state_store import StateStore

CONTROL_PLANE_CONTAINER='energie-control-plane'

def live_release_version(root:Path)->str:
    path=Path(root)/'App/VERSIE.txt'
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('live release version path unsafe')
    value=path.read_text(encoding='utf-8').strip()
    if not value:
        raise RuntimeError('live release version missing')
    return value

def should_reexec(loaded_release:str,live_release:str,state)->bool:
    return bool(
        state is not None and
        getattr(state,'status','')==Status.COMPLETE.value and
        getattr(state,'to_version','')==live_release and
        live_release and live_release!=loaded_release
    )

def reexec_current_watcher(root:Path)->None:
    watcher=Path(root)/'App/tools/release_watcher.sh'
    if watcher.is_symlink() or not watcher.is_file():
        raise RuntimeError('current release watcher missing or unsafe')
    os.execvp('sh',['sh',str(watcher)])

class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self,path='/var/run/docker.sock',timeout=5.0):
        super().__init__('localhost',timeout=timeout);self.path=path
    def connect(self):
        s=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM);s.settimeout(self.timeout);s.connect(self.path);self.sock=s

def control_plane_available()->bool:
    conn=_UnixHTTPConnection()
    try:
        conn.request('GET',f'/containers/{CONTROL_PLANE_CONTAINER}/json');r=conn.getresponse();raw=r.read()
        if r.status!=200:return False
        v=json.loads(raw.decode());state=v.get('State') if isinstance(v,dict) else {}
        if not isinstance(state,dict) or state.get('Running') is not True:return False
        health=state.get('Health') if isinstance(state.get('Health'),dict) else None
        return health is None or str(health.get('Status') or '').lower()=='healthy'
    except Exception:return False
    finally:
        try:conn.close()
        except Exception:pass

def _sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for c in iter(lambda:f.read(1024*1024),b''):h.update(c)
    return h.hexdigest()
def _integral(path:Path)->bool:
    try:
        with zipfile.ZipFile(path) as z:return z.testzip() is None
    except Exception:return False
def _regular_zips(path:Path)->list[Path]:
    if path.exists() and (path.is_symlink() or not path.is_dir()):raise RuntimeError('unsafe incoming directory')
    path.mkdir(parents=True,exist_ok=True);out=[]
    for p in path.glob('*.zip'):
        if p.is_symlink() or not p.is_file():raise RuntimeError('unsafe incoming item')
        out.append(p)
    return sorted(out,key=lambda p:p.name)
def _atomic_json(path:Path,payload:dict)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink():raise RuntimeError('unsafe controller runtime path')
    tmp=path.with_name(path.name+f'.tmp-{os.getpid()}')
    try:tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');os.replace(tmp,path)
    finally:tmp.unlink(missing_ok=True)

class ReleaseControllerService:
    def __init__(self,root:Path,adapter,*,stable_polls=3,ingress_stale_seconds=600):
        self.root=Path(root);self.adapter=adapter;self.controller=ReleaseController()
        self.store=StateStore(self.root/'Inbox/release_controller/current.json')
        self.stable_polls=max(2,int(stable_polls));self.ingress_stale_seconds=max(30,int(ingress_stale_seconds))
        self.samples={};self.counts={}
    def _runtime(self,payload):
        _atomic_json(self.root/'Inbox/release_controller/runtime.json',{'schema':'energie_release_controller_runtime_v1','pid':os.getpid(),'observed_at_epoch':time.time(),**payload})
    def _load_state(self):
        raw=self.store.load();return ReleaseState.from_dict(raw) if isinstance(raw,dict) else None
    def _save(self,s):
        self.store.save(s.to_dict());self._runtime({'phase':s.phase,'status':s.status,'release_id':s.release_id,'generation':s.generation,
            'to_version':s.to_version,'step':s.step,'total':s.total,'blocker':s.blocker,'required_action':s.required_action,'wait_reason':s.wait_reason})
    def _deduplicate(self,items,selected_name):
        failed=self.root/'Inbox/failed/duplicates';failed.mkdir(parents=True,exist_ok=True)
        for p in items:
            if p.name==selected_name:continue
            digest=_sha(p);dst=failed/(p.stem+'.duplicate.'+digest[:12]+'.zip');i=1
            while dst.exists():dst=failed/(p.stem+f'.duplicate.{digest[:12]}.{i}.zip');i+=1
            os.replace(p,dst)
    def _quarantine(self,p:Path,category:str,suffix:str):
        if p.is_symlink() or not p.is_file():raise RuntimeError('unsafe quarantine source')
        target_dir=self.root/'Inbox/failed'/category;target_dir.mkdir(parents=True,exist_ok=True)
        digest=_sha(p);dst=target_dir/(p.stem+f'.{suffix}.{digest[:12]}.zip');i=1
        while dst.exists():dst=target_dir/(p.stem+f'.{suffix}.{digest[:12]}.{i}.zip');i+=1
        os.replace(p,dst)
        if p.exists() or not dst.is_file():raise RuntimeError('quarantine_readback_failed')
        self.samples.pop(p.name,None);self.counts.pop(p.name,None)
        return dst
    def _reconcile_idle_processing(self):
        processing_dir=self.root/'Inbox/processing';items=_regular_zips(processing_dir)
        if not items:return None
        if len(items)>1:return IngressDecision('BLOCKED','multiple_processing_items')
        p=items[0];age=max(0.0,time.time()-p.stat().st_mtime)
        if age<self.ingress_stale_seconds:return IngressDecision('WAITING','orphan_processing_grace')
        # A legitimate claim always persists its generation before Incoming is
        # atomically moved to Processing. Without that durable owner, neither
        # publication nor installation side effects can be disproved. Keep the
        # artifact in its ownership location and fail closed; never manufacture
        # a new release attempt by moving it back to Incoming.
        return IngressDecision('BLOCKED','orphan_processing_unowned_fail_closed')
    def _incoming_decision(self):
        incoming=self.root/'Inbox/incoming';items=_regular_zips(incoming)
        if not items:return None,None
        if len(items)>1:
            models=[IncomingItem(p.name,p.stat().st_size,p.stat().st_mtime_ns,_sha(p),_integral(p)) for p in items]
            d=decide_incoming(models,{})
            if d.status=='DEDUPLICATE':self._deduplicate(items,d.selected);items=_regular_zips(incoming)
            else:return d,None
        p=items[0];sample=(p.stat().st_size,p.stat().st_mtime_ns);prev=self.samples.get(p.name)
        self.counts[p.name]=(self.counts.get(p.name,0)+1) if prev==sample else 1;self.samples[p.name]=sample
        integral=_integral(p) if self.counts[p.name]>=self.stable_polls else None
        if integral is False:
            age=max(0.0,time.time()-p.stat().st_mtime)
            if age>=self.ingress_stale_seconds:
                self._quarantine(p,'corrupt','corrupt')
                return IngressDecision('WAITING','corrupt_candidate_quarantined'),None
        previous={p.name:sample if self.counts[p.name]>=self.stable_polls else (-1,-1)}
        return decide_incoming([IncomingItem(p.name,*sample,integral=integral)],previous),p
    def _claim(self,s):
        incoming=self.root/'Inbox/incoming'/s.artifact_name;processing=self.root/'Inbox/processing'/s.artifact_name
        processing.parent.mkdir(parents=True,exist_ok=True)
        if processing.is_file():return _sha(processing)==s.artifact_sha256
        if incoming.is_file() and _sha(incoming)==s.artifact_sha256:os.replace(incoming,processing);return True
        processed=self.root/'Inbox/processed'/s.artifact_name
        if s.phase in {'INSTALLED','RUNTIME_ALIGNING','VERIFYING','ACCEPTED'}:
            return processed.is_file() and _sha(processed)==s.artifact_sha256
        return False
    def _settle_rolled_back(self,s):
        p=self.root/'Inbox/processing'/s.artifact_name
        if not p.is_file():return
        failed=self.root/'Inbox/failed/rolled_back';failed.mkdir(parents=True,exist_ok=True)
        dst=failed/(p.stem+'.rolled_back.zip');i=1
        while dst.exists():dst=failed/(p.stem+f'.rolled_back.{i}.zip');i+=1
        os.replace(p,dst)
    def cycle(self):
        state=self._load_state()
        if state and state.status not in {Status.COMPLETE.value,Status.ROLLED_BACK.value}:
            if not self._claim(state):
                state.status=Status.BLOCKED.value;state.blocker='owned_artifact_missing_or_mismatched'
                state.required_action='restore the exact owned artifact only';self._save(state);return state
            self.controller.cycle(state,self.adapter);self._save(state);return state
        if state and state.status==Status.COMPLETE.value:
            marker=self.root/'Inbox/ha_publication_required.json'
            if marker.exists():
                settle=getattr(self.adapter,'reconcile_completed_delivery',None)
                if not callable(settle):
                    self._runtime({'status':'BLOCKED','phase':'COMPLETE','reason':'completed_delivery_settlement_capability_missing'})
                    return state
                out=settle(state)
                if out.status!='GREEN':
                    self._runtime({'status':out.status,'phase':'COMPLETE','reason':out.reason,'release_id':state.release_id,'generation':state.generation})
                    return state
        if state and state.status==Status.ROLLED_BACK.value:self._settle_rolled_back(state)
        recovery=self._reconcile_idle_processing()
        if recovery is not None:
            self._runtime({'status':recovery.status,'phase':'DETECTED','reason':recovery.reason})
            return state
        decision,candidate=self._incoming_decision()
        if decision is None:self._runtime({'status':'IDLE','phase':'IDLE'});return state
        if decision.status!='READY':
            self._runtime({'status':decision.status,'phase':'DETECTED','reason':decision.reason});return state
        pre=verify_candidate(self.root,candidate)
        if not pre.get('ready'):
            blockers=list(pre.get('blockers') or [])
            age=max(0.0,time.time()-candidate.stat().st_mtime) if candidate and candidate.is_file() else 0.0
            quarantineable=set(blockers).issubset({'candidate_integrity_invalid','candidate_version_not_newer'}) and bool(blockers)
            if quarantineable and age>=self.ingress_stale_seconds:
                self._quarantine(candidate,'rejected','preflight-rejected')
                self._runtime({'status':'WAITING','phase':'DETECTED','reason':'rejected_candidate_quarantined','blockers':blockers})
                return state
            self._runtime({'status':'BLOCKED','phase':'DETECTED','reason':','.join(blockers)});return state
        s=self.controller.new_state(from_version=pre['current_version'],to_version=pre['candidate_version'],
            artifact_sha256=pre['artifact_sha256'],artifact_name=candidate.name)
        # DETECTED is observational only. The first durable lifecycle write is
        # VERIFIED, so a crash before this point simply re-detects the same ZIP.
        self.controller.mark_verified(s,['artifact_integrity_green','candidate_version_newer']);self._save(s)
        if not self._claim(s):
            s.status=Status.BLOCKED.value;s.blocker='claim_failed';s.required_action='inspect exact incoming/processing artifact';self._save(s);return s
        self.controller.cycle(s,self.adapter);self._save(s);return s

def build_adapter(root:Path):
    native=NativeRuntimeCoordinator(
        root,
        native_mcp_runtime_guard,
        control_plane_available,
        control_plane_prepare=lambda: ensure_control_plane_current(root),
    )
    delivery=HADelivery(root)
    return AtomicReleaseAdapter(root,atomic_app_swap,native,delivery)

def main()->int:
    p=argparse.ArgumentParser(description='Energie 32.4.60 single-owner release controller')
    p.add_argument('--root',required=True);p.add_argument('--interval',type=float,default=5.0);p.add_argument('--stable-polls',type=int,default=3)
    p.add_argument('--ingress-stale-seconds',type=int,default=600)
    args=p.parse_args();root=Path(args.root)
    with controller_lease(root):
        service=ReleaseControllerService(root,build_adapter(root),stable_polls=args.stable_polls,ingress_stale_seconds=args.ingress_stale_seconds)
        loaded_release=live_release_version(root)
        while True:
            try:
                state=service.cycle()
                current_release=live_release_version(root)
                if should_reexec(loaded_release,current_release,state):
                    service._runtime({'status':'REEXEC','phase':'COMPLETE','release_id':state.release_id,
                                      'generation':state.generation,'to_version':state.to_version,
                                      'reason':'load controller code from accepted current release'})
                    reexec_current_watcher(root)
            except Exception as exc:
                service._runtime({'status':'BLOCKED','phase':'SERVICE','reason':f'{type(exc).__name__}:{exc}'})
            time.sleep(max(1.0,args.interval))
    return 0
if __name__=='__main__':raise SystemExit(main())
