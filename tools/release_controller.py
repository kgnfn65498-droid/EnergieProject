from __future__ import annotations
from dataclasses import dataclass,asdict
from enum import Enum
from typing import Any,Protocol
import secrets,time

class Phase(str,Enum):
    DETECTED='DETECTED';VERIFIED='VERIFIED';INSTALLING='INSTALLING';INSTALLED='INSTALLED'
    RUNTIME_ALIGNING='RUNTIME_ALIGNING';VERIFYING='VERIFYING';ACCEPTED='ACCEPTED';COMPLETE='COMPLETE'
class Status(str,Enum):
    ACTIVE='ACTIVE';WAITING='WAITING';BLOCKED='BLOCKED';COMPLETE='COMPLETE';ROLLED_BACK='ROLLED_BACK'
_STEP={p:i+1 for i,p in enumerate(Phase)}

@dataclass
class Outcome:
    status:str;evidence:list[str];reason:str='';required_action:str='';rollback:bool=False
    @classmethod
    def green(cls,*e):return cls('GREEN',list(e))
    @classmethod
    def waiting(cls,reason,*e):return cls('WAITING',list(e),reason=reason)
    @classmethod
    def blocked(cls,reason,required_action='',*,rollback=False):return cls('BLOCKED',[],reason=reason,required_action=required_action,rollback=rollback)
    @classmethod
    def rolled_back(cls,reason,*e):return cls('ROLLED_BACK',list(e),reason=reason)

@dataclass
class ReleaseState:
    release_id:str;generation:str;from_version:str;to_version:str;artifact_sha256:str;artifact_name:str
    phase:str;status:str;step:int;total:int=8;blocker:str='';required_action:str='';wait_reason:str=''
    started_at_epoch:float=0.0;phase_started_at_epoch:float=0.0;updated_at_epoch:float=0.0;evidence:list[str]|None=None
    def to_dict(self)->dict[str,Any]:
        d=asdict(self);d['evidence']=list(self.evidence or []);return d
    @classmethod
    def from_dict(cls,d):return cls(**{**d,'evidence':list(d.get('evidence') or [])})

class Adapter(Protocol):
    def install(self,s:ReleaseState)->Outcome:...
    def runtime_align(self,s:ReleaseState)->Outcome:...
    def verify_live(self,s:ReleaseState)->Outcome:...
    def atomic_accept(self,s:ReleaseState)->Outcome:...
    def delivery(self,s:ReleaseState)->Outcome:...
    def rollback(self,s:ReleaseState,reason:str)->Outcome:...

class ReleaseController:
    def new_state(self,*,from_version,to_version,artifact_sha256,artifact_name):
        now=time.time()
        return ReleaseState(f'{to_version}:{artifact_sha256[:12]}',secrets.token_hex(16),from_version,to_version,artifact_sha256,artifact_name,
            Phase.DETECTED.value,Status.ACTIVE.value,1,started_at_epoch=now,phase_started_at_epoch=now,updated_at_epoch=now,evidence=[])
    def _phase(self,s,phase,evidence=None):
        now=time.time();s.phase=phase.value;s.step=_STEP[phase];s.status=Status.COMPLETE.value if phase==Phase.COMPLETE else Status.ACTIVE.value
        s.phase_started_at_epoch=now;s.updated_at_epoch=now;s.blocker='';s.required_action='';s.wait_reason=''
        if evidence:s.evidence=(s.evidence or [])+list(evidence)
    def mark_verified(self,s,evidence):
        if s.phase!=Phase.DETECTED.value:raise RuntimeError('verify requires DETECTED')
        self._phase(s,Phase.VERIFIED,evidence);return s
    def _outcome(self,s,out,success_phase,adapter,*,rollback_allowed):
        s.updated_at_epoch=time.time()
        if out.evidence:s.evidence=(s.evidence or [])+out.evidence
        if out.status=='GREEN':self._phase(s,success_phase);return s
        if out.status=='WAITING':
            s.status=Status.WAITING.value;s.wait_reason=out.reason;s.blocker='';s.required_action='';return s
        if out.status=='ROLLED_BACK':
            s.status=Status.ROLLED_BACK.value;s.blocker=out.reason;s.required_action='';s.wait_reason='';return s
        if out.status=='BLOCKED':
            if out.rollback and rollback_allowed:
                rb=adapter.rollback(s,out.reason)
                if rb.status in {'GREEN','ROLLED_BACK'}:
                    s.status=Status.ROLLED_BACK.value;s.blocker=out.reason;s.required_action='';s.wait_reason=''
                    s.evidence=(s.evidence or [])+rb.evidence;return s
                s.status=Status.BLOCKED.value;s.blocker='rollback_unproven';s.required_action=rb.required_action or rb.reason;return s
            s.status=Status.BLOCKED.value;s.blocker=out.reason;s.required_action=out.required_action;s.wait_reason='';return s
        raise RuntimeError('unknown outcome')
    def cycle(self,s,adapter):
        if s.status in {Status.COMPLETE.value,Status.ROLLED_BACK.value}:return s
        # Side-effect phases are entered in their own cycle. The service persists
        # the phase before the next cycle can perform the side effect. This makes
        # INSTALLING/RUNTIME_ALIGNING durable authorization fences across crashes.
        if s.phase==Phase.VERIFIED.value:
            self._phase(s,Phase.INSTALLING);return s
        if s.phase==Phase.INSTALLING.value:
            return self._outcome(s,adapter.install(s),Phase.INSTALLED,adapter,rollback_allowed=True)
        if s.phase==Phase.INSTALLED.value:
            self._phase(s,Phase.RUNTIME_ALIGNING);return s
        if s.phase==Phase.RUNTIME_ALIGNING.value:
            return self._outcome(s,adapter.runtime_align(s),Phase.VERIFYING,adapter,rollback_allowed=True)
        if s.phase==Phase.VERIFYING.value:
            v=adapter.verify_live(s)
            if v.status!='GREEN':return self._outcome(s,v,Phase.VERIFYING,adapter,rollback_allowed=True)
            if v.evidence:s.evidence=(s.evidence or [])+v.evidence
            return self._outcome(s,adapter.atomic_accept(s),Phase.ACCEPTED,adapter,rollback_allowed=True)
        if s.phase==Phase.ACCEPTED.value:return self._outcome(s,adapter.delivery(s),Phase.COMPLETE,adapter,rollback_allowed=False)
        return s
    @staticmethod
    def external_evidence_matches(s,e):
        return all(str(e.get(k) or '')==str(v) for k,v in {'generation':s.generation,'release_id':s.release_id,'to_version':s.to_version,'artifact_sha256':s.artifact_sha256}.items())
