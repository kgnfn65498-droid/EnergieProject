from __future__ import annotations
from system_path_contract import project_system_path
import json, time, sys
from datetime import datetime, timezone
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
    from .persistence import atomic_write_json
except ImportError:
    from release_transition import ReleaseTransitionCoordinator
    from release_ownership import migrate_legacy_tasks
    from command_store import CommandStore
    from task_engine import TaskStore
    from project_close_state import write_project_close
    from persistence import atomic_write_json


def plan_transition_step(state: dict[str,Any], facts: dict[str,Any]) -> dict[str,Any]:
    phase=str(state.get('phase') or '')
    if phase=='TRANSITION_PREPARED':
        target=str(state.get('to_release') or '')
        source=str(state.get('from_release') or '')
        atomic_state=str(facts.get('atomic_state') or '').upper()
        hold_ok=(
            (atomic_state=='LIVE_ACCEPTANCE' and facts.get('hold_active') is True)
            or (atomic_state=='ACCEPTED' and facts.get('hold_active') is False and facts.get('hold_validation_status')=='ok')
        )
        promoted=(
            facts.get('active_version')==target
            and facts.get('atomic_from_version')==source
            and facts.get('atomic_to_version')==target
            and atomic_state in {'LIVE_ACCEPTANCE','ACCEPTED'}
            and facts.get('hold_release_version')==target
            and hold_ok
        )
        return {'action':'ADVANCE_APP_PROMOTED' if promoted else 'WAIT_APP_PROMOTED'}
    if phase=='APP_PROMOTED': return {'action':'RECONCILE_OLD_STATE'}
    if phase=='RECONCILE_OLD_STATE': return {'action':'ADVANCE_PM_CURRENT'}
    if phase=='PM_CURRENT': return {'action':'ADVANCE_NATIVE_RUNTIME_CURRENT' if facts.get('pm_green') else 'WAIT_PM_CURRENT'}
    if phase=='NATIVE_RUNTIME_CURRENT': return {'action':'ADVANCE_HOLD_VALID' if facts.get('native_green') else 'QUEUE_NATIVE_MCP_RELOAD'}
    if phase=='HOLD_VALID': return {'action':'ADVANCE_ATOMIC_ACCEPTANCE_COMMITTED' if facts.get('atomic_committed') else 'COMMIT_ATOMIC_ACCEPTANCE'}
    if phase=='ATOMIC_ACCEPTANCE_COMMITTED': return {'action':'ADVANCE_PROJECT_CR'}
    if phase=='PROJECT_CR':
        if state.get('current_ticket'): return {'action':'WAIT_PROJECT_CR_RESULT'}
        if str(state.get('phase_status') or '').upper()=='GREEN' and 'PROJECT_CR' in (state.get('completed_phases') or []): return {'action':'ADVANCE_NAS_CR'}
        return {'action':'ADVANCE_NAS_CR' if facts.get('project_cr_green') else 'QUEUE_PROJECT_CR'}
    if phase=='NAS_CR':
        if state.get('current_ticket'): return {'action':'WAIT_NAS_CR_RESULT'}
        if str(state.get('phase_status') or '').upper()=='GREEN' and 'NAS_CR' in (state.get('completed_phases') or []): return {'action':'ADVANCE_CLEARUP'}
        return {'action':'ADVANCE_CLEARUP' if facts.get('nas_cr_green') else 'QUEUE_NAS_CR'}
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
    status=_load(project_system_path(root, 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'))
    checks=((status.get('health') or {}).get('checks') or []) if isinstance(status,dict) else []
    by={str(x.get('name')):str(x.get('status')) for x in checks if isinstance(x,dict)}
    audit=_load(project_system_path(root, 'Inbox/projectmanager_v2/RuntimeV2/self_audit/current.json'))
    atomic=_load(project_system_path(root, 'Inbox/atomic_app_swap_state.json'))
    hold=_load(project_system_path(root, 'Inbox/operating_mode/release_validation_hold.json'))
    clear=_load(project_system_path(root, 'Inbox/logs/project_clearup_runtime.json'))
    mode=_load(project_system_path(root, 'Inbox/operating_mode/operating_mode_state.json'))
    try: active_version=(root/'App/VERSIE.txt').read_text(encoding='utf-8').strip()
    except OSError: active_version=''
    return {
        'active_version': active_version,
        'atomic_state': str(atomic.get('state') or '').upper(),
        'atomic_from_version': str(atomic.get('from_version') or ''),
        'atomic_to_version': str(atomic.get('to_version') or ''),
        'hold_active': hold.get('active'),
        'hold_release_version': str(hold.get('release_version') or ''),
        'hold_validation_status': str(hold.get('validation_status') or ''),
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
        self.runtime=project_system_path(self.root, 'Inbox/projectmanager_v2/RuntimeV2')
        self.commands=CommandStore(self.runtime/'commands/queue.json')
        self.tasks=TaskStore(self.runtime/'state/tasks.json')

    def _queue_once(self,intent,state):
        gen=str(state.get('generation_id') or ''); rel=str(state.get('to_release') or '')
        active={'PENDING','PROCESSING','WAITING_APPROVAL','APPROVED_READY','APPROVED_WAITING_EXECUTOR'}
        matches=[x for x in self.commands.all() if x.get('intent')==intent and x.get('transition_generation')==gen]
        if any(x.get('status') in active for x in matches): return matches[-1]
        if matches and matches[-1].get('status')=='DONE': return matches[-1]
        if matches and matches[-1].get('status') in {'FAILED','CANCELLED','SUPERSEDED','INTERRUPTED'}:
            failed=matches[-1]
            failed_request=str(failed.get('transition_request_id') or '')
            attempts=state.get('attempts') or {}
            attempt=attempts.get(failed_request) if isinstance(attempts,dict) else None
            reissue_allowed=isinstance(attempt,dict) and attempt.get('reissue_allowed') is True
            if not reissue_allowed:
                self.coord.block(expected_revision=int(state['revision']),expected_generation=gen,blocker='executor_side_effect_unknown')
                return failed
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
        result={**ticket,'status':'GREEN','side_effect_state':'PROVEN','evidence_refs':[str(project_system_path(self.root, 'Inbox/operating_mode/operating_mode_state.json'))]}
        accepted=self.coord.accept_executor_result(result)
        self.coord.advance(expected_revision=int(accepted['revision']),expected_generation=gen,phase='RESTORE_DEVELOPMENT',next_action='complete transition')
        return result

    def _ticketless_nas_cr_absent_readback(self):
        bridge = project_system_path(self.root, 'Inbox/nas_container_cr_local')
        refs = [str(bridge/'request.json'), str(bridge/'result.json'), str(self.root/'Backups/NAS Container')]
        if any(path.exists() or path.is_symlink() for path in (bridge/'request.json', bridge/'result.json')):
            return None
        return {'state': 'ABSENT', 'evidence_refs': refs}

    def _recover_ticketless_nas_cr_once(self, state):
        if 'current_ticket' not in state or (state.get('lifecycle_state'), state.get('phase'), state.get('phase_status'), state.get('blocker'), state.get('current_ticket')) != ('BLOCKED', 'NAS_CR', 'RED', 'executor_side_effect_unknown', None):
            return None
        attempts = state.get('attempts') or {}
        previous = next((request_id for request_id, attempt in reversed(list(attempts.items())) if isinstance(attempt, dict) and attempt.get('executor_name') == 'nas_container_cr_create' and attempt.get('reissue_allowed') is True), None)
        readback = self._ticketless_nas_cr_absent_readback()
        if not previous or not readback: return None
        return self.coord.recover_ticketless_nas_cr_not_performed(expected_generation=str(state.get('generation_id') or ''), expected_revision=int(state['revision']), previous_request_id=previous, readback=readback)


    def _settle_current_ticket(self, state):
        ticket=state.get('current_ticket') if isinstance(state.get('current_ticket'),dict) else None
        if not ticket or ticket.get('executor_name') not in {'project_cr_create','nas_container_cr_create'}:
            return None
        request_id=str(ticket.get('request_id') or '')
        generation=str(ticket.get('generation_id') or '')
        matches=[command for command in self.commands.all() if
                 command.get('transition_request_id')==request_id and
                 command.get('transition_generation')==generation and
                 command.get('executor_name')==ticket.get('executor_name')]
        if not matches:
            return None
        command=matches[-1]
        if command.get('status')=='DONE':
            result=command.get('result') if isinstance(command.get('result'),dict) else {}
            evidence=[]
            for key in ('backup_name','backup_sha256','result_path','evidence_ref'):
                if result.get(key): evidence.append(str(result.get(key)))
            accepted=self.coord.accept_executor_result({
                **ticket, 'status':'GREEN', 'side_effect_state':'PROVEN',
                'evidence_refs':evidence,
            })
            return accepted
        if command.get('status') in {'FAILED','CANCELLED','SUPERSEDED'}:
            self.coord.block(
                expected_revision=int(state['revision']), expected_generation=generation,
                blocker='executor_command_failed_before_ticket_settlement',
                next_action='inspect exact executor command result',
            )
            return self.coord.load()
        return None

    def _ensure_project_cr_maintenance_bridge(self, state):
        ticket=state.get('current_ticket') if isinstance(state.get('current_ticket'),dict) else None
        if not ticket or ticket.get('executor_name')!='project_cr_create':
            return None
        request_id=str(ticket.get('request_id') or '')
        matches=[command for command in self.commands.all() if
                 command.get('transition_request_id')==request_id and
                 command.get('transition_generation')==state.get('generation_id') and
                 command.get('executor_name')=='project_cr_create']
        if not matches:
            return None
        command=matches[-1]
        pending_result=command.get('result') if isinstance(command.get('result'),dict) else {}
        project_cr_request_id=str(pending_result.get('request_id') or '')
        if command.get('status')!='PENDING' or not project_cr_request_id:
            return None
        from mode_bridge import ModeBridge
        bridge=ModeBridge(project_system_path(self.root, 'Inbox/operating_mode/operating_mode_command.json'), project_root=self.root)
        return bridge.request_transition_owned_temporary_maintenance(
            generation_id=str(state.get('generation_id') or ''),
            ticket_request_id=request_id,
            idempotency_key=str(ticket.get('idempotency_key') or ''),
            command_id=str(command.get('id') or ''),
            project_cr_request_id=project_cr_request_id,
            release_owner=str(state.get('to_release') or ''),
            approval_reference='release_transition_authorized_release_e2e',
            confirmed_by_user=True,
        )

    def run_once(self):
        state=self.coord.load() or self.coord.bootstrap_legacy_if_needed()
        settled=self._settle_current_ticket(state)
        if settled is not None:
            state=settled
        recovered = self._recover_ticketless_nas_cr_once(state)
        if recovered is not None:
            return recovered
        if state.get('lifecycle_state') == 'BLOCKED':
            return state
        if state.get('lifecycle_state') in {'COMPLETE','ROLLED_BACK','CANCELLED'}: return state
        if state.get('phase')=='PROJECT_CR' and state.get('current_ticket'):
            self._ensure_project_cr_maintenance_bridge(state)
            return self.coord.load() or state
        if state.get('phase')=='NAS_CR' and state.get('current_ticket'):
            return state
        facts=_checks(self.root); step=plan_transition_step(state,facts); action=step['action']
        gen=state['generation_id']; rev=int(state['revision']); rel=state['to_release']
        if action=='ADVANCE_APP_PROMOTED':
            return self.coord.advance(expected_revision=rev,expected_generation=gen,phase='APP_PROMOTED',next_action='reconcile old state')
        if action=='WAIT_APP_PROMOTED': return state
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
        if action=='QUEUE_PROJECT_CR':
            self._queue_once('project_cr_create',state)
            current=self.coord.load() or state
            self._ensure_project_cr_maintenance_bridge(current)
            return self.coord.load() or current
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
    root = Path(project_root)
    worker=ReleaseTransitionWorker(root,app_module)
    status_path = project_system_path(root, 'Inbox/projectmanager_v2/RuntimeV2/release_transition/worker_status.json')
    last={}
    while not stop_event.is_set():
        observed_at = datetime.now(timezone.utc).isoformat()
        try:
            last=worker.run_once()
            atomic_write_json(status_path, {
                'schema': 1, 'status': 'GREEN', 'observed_at': observed_at,
                'phase': last.get('phase') if isinstance(last, dict) else None,
                'lifecycle_state': last.get('lifecycle_state') if isinstance(last, dict) else None,
                'revision': last.get('revision') if isinstance(last, dict) else None,
                'error': None,
            })
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
            last={'lifecycle_state':'BLOCKED','error':error}
            atomic_write_json(status_path, {
                'schema': 1, 'status': 'RED', 'observed_at': observed_at,
                'lifecycle_state': 'BLOCKED', 'error': error,
            })
        if stop_event.wait(interval): break
    return last
