from __future__ import annotations
import json, time, sys
from pathlib import Path
from typing import Any

_PM_DIR = Path(__file__).resolve().parent
if str(_PM_DIR) not in sys.path:
    sys.path.append(str(_PM_DIR))

try:
    from .release_transition import ReleaseTransitionCoordinator
    from .release_ownership import migrate_legacy_tasks
    from .command_store import CommandStore
    from .task_engine import TaskStore
    from .project_close_state import write_project_close
except ImportError:
    from release_transition import ReleaseTransitionCoordinator
    from release_ownership import migrate_legacy_tasks
    from command_store import CommandStore
    from task_engine import TaskStore
    from project_close_state import write_project_close


def plan_transition_step(state: dict[str,Any], facts: dict[str,Any]) -> dict[str,Any]:
    phase=str(state.get('phase') or '')
    if phase=='APP_PROMOTED': return {'action':'RECONCILE_OLD_STATE'}
    if phase=='RECONCILE_OLD_STATE': return {'action':'ADVANCE_PM_CURRENT'}
    if phase=='PM_CURRENT': return {'action':'ADVANCE_NATIVE_RUNTIME_CURRENT' if facts.get('pm_green') else 'WAIT_PM_CURRENT'}
    if phase=='NATIVE_RUNTIME_CURRENT': return {'action':'ADVANCE_HOLD_VALID' if facts.get('native_green') else 'QUEUE_NATIVE_MCP_RELOAD'}
    if phase=='HOLD_VALID': return {'action':'ADVANCE_ATOMIC_ACCEPTANCE_COMMITTED' if facts.get('atomic_committed') else 'COMMIT_ATOMIC_ACCEPTANCE'}
    if phase=='ATOMIC_ACCEPTANCE_COMMITTED': return {'action':'ADVANCE_PROJECT_CR'}
    if phase=='PROJECT_CR': return {'action':'ADVANCE_NAS_CR' if facts.get('project_cr_green') else 'QUEUE_PROJECT_CR'}
    if phase=='NAS_CR': return {'action':'ADVANCE_CLEARUP' if facts.get('nas_cr_green') else 'QUEUE_NAS_CR'}
    if phase=='CLEARUP': return {'action':'ADVANCE_HYGIENE' if facts.get('clearup_green') else 'WAIT_CLEARUP'}
    if phase=='HYGIENE': return {'action':'ADVANCE_LIVE_PROVEN' if facts.get('hygiene_green') else 'WAIT_HYGIENE'}
    if phase=='LIVE_PROVEN': return {'action':'RESTORE_DEVELOPMENT'}
    if phase=='RESTORE_DEVELOPMENT': return {'action':'COMPLETE'}
    if phase=='COMPLETE': return {'action':'NOOP'}
    return {'action':'BLOCK','reason':'unknown_transition_phase'}


def _load(path: Path):
    try: value=json.loads(path.read_text(encoding='utf-8'))
    except Exception: return {}
    return value if isinstance(value,dict) else {}


def _checks(root: Path):
    status=_load(root/'Inbox/projectmanager_v2/RuntimeV2/status/current.json')
    checks=((status.get('health') or {}).get('checks') or []) if isinstance(status,dict) else []
    by={str(x.get('name')):str(x.get('status')) for x in checks if isinstance(x,dict)}
    audit=_load(root/'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json')
    atomic=_load(root/'Inbox/atomic_app_swap_state.json')
    hold=_load(root/'Inbox/operating_mode/release_validation_hold.json')
    clear=_load(root/'Inbox/logs/project_clearup_runtime.json')
    mode=_load(root/'Inbox/operating_mode/operating_mode_state.json')
    return {
        'pm_green': audit.get('status')=='GREEN',
        'native_green': by.get('native_mcp_runtime')=='GREEN',
        'atomic_committed': str(atomic.get('state') or '').upper()=='ACCEPTED' and hold.get('active') is False and hold.get('validation_status')=='ok',
        'project_cr_green': by.get('project_crash_recovery_set')=='GREEN',
        'nas_cr_green': by.get('nas_container_crash_recovery_retention')=='GREEN',
        'clearup_green': str(clear.get('status') or '') in {'completed','already_completed','no_action'},
        'hygiene_green': by.get('project_structure_hygiene')=='GREEN',
        'development_restored': str(mode.get('base_mode') or mode.get('mode') or '').upper()=='DEVELOPMENT' and str(mode.get('effective_mode') or 'DEVELOPMENT').upper()=='DEVELOPMENT',
    }


class ReleaseTransitionWorker:
    def __init__(self, project_root, app_module):
        self.root=Path(project_root); self.app=app_module
        self.coord=ReleaseTransitionCoordinator(self.root)
        self.runtime=self.root/'Inbox/projectmanager_v2/RuntimeV2'
        self.commands=CommandStore(self.runtime/'commands/queue.json')
        self.tasks=TaskStore(self.runtime/'state/tasks.json')

    def _queue_once(self,intent,state):
        gen=str(state.get('generation_id') or ''); rel=str(state.get('to_release') or '')
        active={'PENDING','PROCESSING','WAITING_APPROVAL','APPROVED_READY','APPROVED_WAITING_EXECUTOR'}
        matches=[x for x in self.commands.all() if x.get('intent')==intent and x.get('transition_generation')==gen]
        if any(x.get('status') in active for x in matches): return matches[-1]
        if matches and matches[-1].get('status')=='DONE': return matches[-1]
        if matches and matches[-1].get('status') in {'FAILED','CANCELLED','SUPERSEDED','INTERRUPTED'}:
            self.coord.block(expected_revision=int(state['revision']),expected_generation=gen,blocker='executor_side_effect_unknown')
            return matches[-1]
        ticket=self.coord.issue_executor_ticket(intent,expected_revision=int(state['revision']),expected_generation=gen)
        return self.commands.enqueue({
            'intent':intent,'source':'projectmanager_auto','text':f'release transition {gen}: {intent}',
            'release_version':rel,'release_owner':rel,'scope':'RELEASE','lifecycle_class':'RELEASE_TRANSITION',
            'created_generation':gen,'transition_generation':gen,'transition_phase':ticket.get('phase'),
            'transition_revision':ticket.get('revision'),'transition_request_id':ticket.get('request_id'),
            'transition_idempotency_key':ticket.get('idempotency_key'),'executor_name':ticket.get('executor_name'),
            'title':f'{rel} transition {intent}','goal':'Generation-fenced release transition executor','steps_total':1,'priority':1,
        })


    def _restore_previous_mode(self, state):
        from operating_modes import Mode, load_mode_state, save_mode_state, set_base_mode
        gen=str(state.get('generation_id') or '')
        target=str(state.get('previous_base_mode') or 'DEVELOPMENT').upper()
        if target not in {'USER','DEVELOPMENT','MAINTENANCE'}:
            self.coord.block(expected_revision=int(state['revision']),expected_generation=gen,blocker='invalid_previous_base_mode')
            return {'status':'RED','side_effect_state':'UNKNOWN','target_mode':target}
        current=self.coord.load() or state
        ticket=current.get('current_ticket') if isinstance(current.get('current_ticket'),dict) else None
        if ticket:
            if ticket.get('executor_name')!='mode_restore':
                self.coord.block(expected_revision=int(current['revision']),expected_generation=gen,blocker='unexpected_executor_ticket_during_mode_restore')
                return {'status':'RED','side_effect_state':'UNKNOWN','target_mode':target}
        else:
            ticket=self.coord.issue_executor_ticket('mode_restore',expected_revision=int(current['revision']),expected_generation=gen)
        mode_state=load_mode_state(self.root)
        if mode_state.base_mode.value != target:
            updated=set_base_mode(mode_state,Mode(target),confirmed_by_user=True)
            save_mode_state(self.root,updated)
        readback=load_mode_state(self.root)
        if readback.base_mode.value != target:
            current=self.coord.load() or current
            self.coord.block(expected_revision=int(current['revision']),expected_generation=gen,blocker='mode_restore_readback_mismatch')
            return {'status':'RED','side_effect_state':'UNKNOWN','target_mode':target}
        result={**ticket,'status':'GREEN','side_effect_state':'PROVEN','evidence_refs':[str(self.root/'Inbox/operating_mode/operating_mode_state.json')]}
        accepted=self.coord.accept_executor_result(result)
        self.coord.advance(expected_revision=int(accepted['revision']),expected_generation=gen,phase='RESTORE_DEVELOPMENT',next_action='complete transition')
        return result

    def run_once(self):
        state=self.coord.load() or self.coord.bootstrap_legacy_if_needed()
        if state.get('lifecycle_state') in {'COMPLETE','ROLLED_BACK','CANCELLED'}: return state
        facts=_checks(self.root); step=plan_transition_step(state,facts); action=step['action']
        gen=state['generation_id']; rev=int(state['revision']); rel=state['to_release']
        if action=='RECONCILE_OLD_STATE':
            migrate_legacy_tasks(self.tasks,project_root=self.root,current_release=rel,evidence_ref='App/VERSIE.txt')
            return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='RECONCILE_OLD_STATE',next_action='verify Projectmanager current')
        if action=='ADVANCE_PM_CURRENT':
            return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='PM_CURRENT',phase_status='PENDING',next_action='wait Projectmanager self-audit')
        if action=='WAIT_PM_CURRENT': return state
        if action=='ADVANCE_NATIVE_RUNTIME_CURRENT':
            return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='NATIVE_RUNTIME_CURRENT',phase_status='PENDING',next_action='verify Native MCP runtime')
        if action=='QUEUE_NATIVE_MCP_RELOAD': self._queue_once('native_mcp_reload',state); return self.coord.load()
        if action=='ADVANCE_HOLD_VALID':
            return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='HOLD_VALID',phase_status='PENDING',next_action='validate and commit atomic acceptance')
        if action=='COMMIT_ATOMIC_ACCEPTANCE':
            from operating_mode_runtime import attempt_release_hold
            result=attempt_release_hold(self.app,self.root,rel,issued_by='release_transition_coordinator')
            if result.get('status') not in {'released','already_released'}: return state
            state=self.coord.load() or state
            return self.coord.advance(expected_revision=int(state['revision']),expected_generation=gen,phase='ATOMIC_ACCEPTANCE_COMMITTED',next_action='create current Project CR')
        if action=='ADVANCE_ATOMIC_ACCEPTANCE_COMMITTED':
            return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='ATOMIC_ACCEPTANCE_COMMITTED',next_action='create current Project CR')
        if action=='ADVANCE_PROJECT_CR':
            write_project_close(self.root,release_version=rel,state='REQUESTED',reason='release_transition_project_close',source='release_transition_coordinator')
            return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='PROJECT_CR',phase_status='PENDING',next_action='current Project CR')
        if action=='QUEUE_PROJECT_CR': self._queue_once('project_cr_create',state); return self.coord.load()
        if action=='ADVANCE_NAS_CR': return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='NAS_CR',phase_status='PENDING',next_action='current NAS Container CR')
        if action=='QUEUE_NAS_CR': self._queue_once('nas_container_cr_create',state); return self.coord.load()
        if action=='ADVANCE_CLEARUP': return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='CLEARUP',phase_status='PENDING',next_action='wait reversible CLEARUP')
        if action=='WAIT_CLEARUP': return state
        if action=='ADVANCE_HYGIENE': return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='HYGIENE',phase_status='PENDING',next_action='verify project hygiene')
        if action=='WAIT_HYGIENE': return state
        if action=='ADVANCE_LIVE_PROVEN': return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='LIVE_PROVEN',next_action='restore DEVELOPMENT')
        if action=='RESTORE_DEVELOPMENT':
            self._restore_previous_mode(state)
            return self.coord.load() or state
        if action=='COMPLETE': return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='COMPLETE',next_action='')
        return state


def release_transition_daemon(stop_event, app_module, project_root, *, interval=5.0):
    worker=ReleaseTransitionWorker(project_root,app_module)
    last={}
    while not stop_event.is_set():
        try: last=worker.run_once()
        except Exception as exc: last={'lifecycle_state':'BLOCKED','error':f'{type(exc).__name__}: {exc}'}
        if stop_event.wait(interval): break
    return last
