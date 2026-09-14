from __future__ import annotations
import json, os, secrets, fcntl, stat, contextlib
from pathlib import Path
from typing import Any
from transition_state_io import read_transition_state, TransitionStateReadError

PHASES = (
    'TRANSITION_PREPARED','APP_PROMOTED','RECONCILE_OLD_STATE','PM_CURRENT','NATIVE_RUNTIME_CURRENT',
    'HOLD_VALID','ATOMIC_ACCEPTANCE_COMMITTED','PROJECT_CR','NAS_CR','CLEARUP','HYGIENE',
    'LIVE_PROVEN','RESTORE_DEVELOPMENT','COMPLETE'
)
PHASE_SUCCESSOR = {PHASES[i]: PHASES[i + 1] for i in range(len(PHASES) - 1)}
TERMINAL_LIFECYCLES = {'COMPLETE','ROLLED_BACK','CANCELLED'}

class TransitionBlocked(RuntimeError): pass
class StaleRevision(RuntimeError): pass
class InvalidTransitionResult(RuntimeError): pass


def _json(path: Path):
    try:
        return read_transition_state(path, missing_ok=True)
    except TransitionStateReadError as exc:
        raise TransitionBlocked(str(exc)) from exc


def _atomic(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        st=path.lstat()
    except FileNotFoundError:
        st=None
    if st is not None and stat.S_ISLNK(st.st_mode):
        raise TransitionBlocked(f'transition state path is symlink: {path}')
    tmp=path.with_name(f'.{path.name}.tmp-{os.getpid()}-{secrets.token_hex(4)}')
    with tmp.open('x',encoding='utf-8') as h:
        json.dump(data,h,ensure_ascii=False,indent=2,sort_keys=True); h.write('\n'); h.flush(); os.fsync(h.fileno())
    os.replace(tmp,path)


class ReleaseTransitionCoordinator:
    def __init__(self, project_root: Path|str):
        self.root=Path(project_root)
        self.runtime=self.root/'Inbox/projectmanager_v2/RuntimeV2/release_transition'
        self.path=self.runtime/'current.json'
        self.history=self.runtime/'history'
        self.lock_path=self.root/'Inbox/.release-transition.operation.lock'
        self.lock_path.parent.mkdir(parents=True,exist_ok=True)
        self._ensure_lock_file()

    def _ensure_lock_file(self):
        try:
            st=self.lock_path.lstat()
        except FileNotFoundError:
            flags=os.O_RDWR | os.O_CREAT | os.O_EXCL
            if hasattr(os,'O_NOFOLLOW'): flags |= os.O_NOFOLLOW
            try:
                fd=os.open(str(self.lock_path),flags,0o644)
            except FileExistsError:
                st=self.lock_path.lstat()
            else:
                os.close(fd)
                st=self.lock_path.lstat()
        if stat.S_ISLNK(st.st_mode) or not stat.S_ISREG(st.st_mode):
            raise TransitionBlocked('transition lock is not a regular non-symlink file')

    @contextlib.contextmanager
    def _lease(self):
        flags=os.O_RDWR
        if hasattr(os,'O_NOFOLLOW'): flags |= os.O_NOFOLLOW
        try:
            fd=os.open(str(self.lock_path),flags)
        except OSError as exc:
            raise TransitionBlocked('transition lock open failed') from exc
        try:
            st=os.fstat(fd)
            if not stat.S_ISREG(st.st_mode): raise TransitionBlocked('transition lock is not regular file')
            try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc: raise TransitionBlocked('transition writer lease busy') from exc
            try: yield
            finally: fcntl.flock(fd,fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def load(self): return _json(self.path)

    def _save_unlocked(self, state: dict, *, expected_revision: int|None=None):
        cur=self.load()
        actual=int((cur or {}).get('revision',0))
        if expected_revision is not None and actual != int(expected_revision):
            raise StaleRevision(f'expected revision {expected_revision}, actual {actual}')
        state=dict(state); state['revision']=actual+1
        _atomic(self.path,state); return state

    def _save(self, state: dict, *, expected_revision: int|None=None):
        with self._lease():
            return self._save_unlocked(state,expected_revision=expected_revision)

    def create_prepared(self, from_release:str, to_release:str, *, previous_base_mode:str='DEVELOPMENT'):
        with self._lease():
            cur=self.load()
            if cur and cur.get('lifecycle_state') not in TERMINAL_LIFECYCLES:
                if cur.get('to_release')==to_release: return cur
                raise TransitionBlocked('another transition is active')
            if cur:
                generation=str(cur.get('generation_id') or '').strip()
                if not generation:
                    raise TransitionBlocked('terminal transition missing generation id')
                self.history.mkdir(parents=True,exist_ok=True)
                history_path=self.history/f'{generation}.json'
                if history_path.exists():
                    existing=_json(history_path)
                    if existing != cur:
                        raise TransitionBlocked('transition history collision')
                else:
                    _atomic(history_path,cur)
            state={'schema_version':1,'generation_id':secrets.token_hex(16),'revision':1,'from_release':from_release,'to_release':to_release,
                   'lifecycle_state':'ACTIVE','phase':'TRANSITION_PREPARED','phase_status':'GREEN','previous_base_mode':str(previous_base_mode).upper(),
                   'bootstrap_origin':'native_pre_transition_v1','completed_phases':['TRANSITION_PREPARED'],'attempts':{},'evidence_refs':[],
                   'blocker':'','next_action':'promote app','current_ticket':None}
            _atomic(self.path,state)
            return state

    def bootstrap_legacy_if_needed(self):
        cur=self.load()
        if cur: return cur
        release=(self.root/'App/VERSIE.txt').read_text(encoding='utf-8').strip()
        hold=_json(self.root/'Inbox/operating_mode/release_validation_hold.json') or {}
        atomic=_json(self.root/'Inbox/atomic_app_swap_state.json') or {}
        ok=(hold.get('active') is True and hold.get('activated_reason')=='release_install' and str(hold.get('release_version') or '')==release
            and str(atomic.get('to_version') or '')==release and str(atomic.get('from_version') or '') and str(atomic.get('state') or '').upper() in {'LIVE_ACCEPTANCE','ACCEPTED'})
        hs=str(hold.get('artifact_sha256') or ''); aas=str(atomic.get('artifact_sha256') or '')
        if hs and aas and hs!=aas: ok=False
        if not ok: raise TransitionBlocked('legacy pre-transition fence mismatch')
        state={'schema_version':1,'generation_id':secrets.token_hex(16),'revision':0,'from_release':str(atomic['from_version']),'to_release':release,
               'lifecycle_state':'ACTIVE','phase':'APP_PROMOTED','phase_status':'GREEN','previous_base_mode':'DEVELOPMENT',
               'bootstrap_origin':'legacy_pre_transition_fence_v1','completed_phases':['APP_PROMOTED'],'attempts':{},
               'evidence_refs':[str(self.root/'Inbox/operating_mode/release_validation_hold.json'),str(self.root/'Inbox/atomic_app_swap_state.json')],
               'blocker':'','next_action':'reconcile old state','current_ticket':None}
        return self._save(state,expected_revision=0)

    def advance(self, *, expected_revision:int, expected_generation:str, phase:str, phase_status:str='GREEN', next_action:str=''):
        if phase not in PHASES: raise ValueError('unknown phase')
        cur=self.load() or {}
        if cur.get('generation_id')!=expected_generation: raise InvalidTransitionResult('generation mismatch')
        if int(cur.get('revision',0))!=int(expected_revision): raise StaleRevision('stale revision')
        current_phase=str(cur.get('phase') or '')
        expected_phase=PHASE_SUCCESSOR.get(current_phase)
        if expected_phase != phase:
            raise InvalidTransitionResult(f'illegal phase transition {current_phase}->{phase}; expected {expected_phase}')
        if str(cur.get('phase_status') or '').upper() == 'RED':
            raise InvalidTransitionResult('cannot advance from red phase')
        state=dict(cur); state.update(phase=phase,phase_status=phase_status,next_action=next_action,current_ticket=None,blocker='')
        completed=list(state.get('completed_phases') or [])
        if phase_status=='GREEN' and phase not in completed: completed.append(phase)
        state['completed_phases']=completed
        if phase=='COMPLETE' and phase_status=='GREEN': state['lifecycle_state']='COMPLETE'
        return self._save(state,expected_revision=expected_revision)

    def block(self, *, expected_revision:int, expected_generation:str, blocker:str, next_action:str='manual evidence required'):
        cur=self.load() or {}
        if cur.get('generation_id') != expected_generation: raise InvalidTransitionResult('generation mismatch')
        if int(cur.get('revision',0)) != int(expected_revision): raise StaleRevision('stale revision')
        state=dict(cur); state['lifecycle_state']='BLOCKED'; state['phase_status']='RED'; state['blocker']=str(blocker); state['next_action']=str(next_action)
        return self._save(state,expected_revision=expected_revision)

    def issue_executor_ticket(self, executor_name:str, *, expected_revision:int, expected_generation:str):
        cur=self.load() or {}
        if cur.get('generation_id')!=expected_generation: raise InvalidTransitionResult('generation mismatch')
        if int(cur.get('revision',0))!=int(expected_revision): raise StaleRevision('stale revision')
        if cur.get('current_ticket'):
            raise TransitionBlocked('transition already has active executor ticket')
        request_id=secrets.token_hex(16); key=secrets.token_hex(16); issued_revision=int(expected_revision)+1
        ticket={'request_id':request_id,'idempotency_key':key,'generation_id':expected_generation,'revision':issued_revision,
                'phase':cur.get('phase'),'release_owner':cur.get('to_release'),'executor_name':executor_name}
        state=dict(cur); state['current_ticket']=dict(ticket); state['phase_status']='WAITING_RESULT'
        state.setdefault('attempts',{})[request_id]={'executor_name':executor_name,'reissue_allowed':False}
        saved=self._save(state,expected_revision=expected_revision)
        if int(saved.get('revision',0)) != issued_revision:
            raise StaleRevision('ticket revision did not match committed state revision')
        return dict(ticket)

    def accept_executor_result(self, result:dict[str,Any]):
        cur=self.load() or {}; ticket=cur.get('current_ticket') or {}
        for key in ('request_id','idempotency_key','generation_id','executor_name','phase','release_owner','revision'):
            if str(result.get(key) or '') != str(ticket.get(key) or ''): raise InvalidTransitionResult(f'{key} mismatch')
        if int(cur.get('revision',0)) != int(ticket.get('revision',-1)):
            raise StaleRevision('executor ticket revision is not current')
        if str(cur.get('phase') or '') != str(ticket.get('phase') or '') or str(cur.get('to_release') or '') != str(ticket.get('release_owner') or ''):
            raise InvalidTransitionResult('executor ticket no longer matches current phase/release')
        if result.get('status')!='GREEN' or result.get('side_effect_state') not in {'PROVEN','NOT_REQUIRED'}:
            raise InvalidTransitionResult('executor result not proven green')
        state=dict(cur); state['phase_status']='GREEN'; state['current_ticket']=None; state['next_action']=''
        state.setdefault('evidence_refs',[]).extend(result.get('evidence_refs') or [])
        return self._save(state,expected_revision=int(cur.get('revision',0)))

    def recover_waiting_result(self, request_id:str, *, readback:dict[str,Any]):
        cur=self.load() or {}; ticket=cur.get('current_ticket') or {}
        if ticket.get('request_id')!=request_id: raise InvalidTransitionResult('request mismatch')
        state_name=str(readback.get('state') or '').upper()
        if state_name in {'PROVEN','DONE'}:
            return self.accept_executor_result({**ticket,'status':'GREEN','side_effect_state':'PROVEN','evidence_refs':readback.get('evidence_refs') or []})
        if state_name in {'NOT_PERFORMED','ABSENT'}:
            state=dict(cur); state['phase_status']='PENDING'; state['current_ticket']=None; state.setdefault('attempts',{}).setdefault(request_id,{})['reissue_allowed']=True
            return self._save(state,expected_revision=int(cur.get('revision',0)))
        state=dict(cur); state['lifecycle_state']='BLOCKED'; state['phase_status']='RED'; state['blocker']='executor_side_effect_unknown'; state['next_action']='manual evidence required'
        state.setdefault('attempts',{}).setdefault(request_id,{})['reissue_allowed']=False
        return self._save(state,expected_revision=int(cur.get('revision',0)))
