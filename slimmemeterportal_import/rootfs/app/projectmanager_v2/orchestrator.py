import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from approval_ingress import ApprovalIngressConsumer
from approved_action_store import ApprovedActionStore
from command_ingress import CommandIngressConsumer
from command_processor import CommandProcessor
from command_store import CommandStore
from conversation_intake import ConversationIntakeBridge
from conversation_approval import ConversationApprovalCoordinator
from conversation_runtime import ProjectmanagerConversationRuntime
from configured_service import ConfiguredManagerService
from handoff_queue import HandoffQueue
from handoff_result_ingress import HandoffResultIngressConsumer
from issue_repair_evidence import collect_issue_repair_evidence
from handover import build_handover
from handover_snapshot import HandoverSnapshotService
from health_engine import summarize_health_with_self_audit
from mode_bridge import ModeBridge
from native_mcp_self_heal import NativeMcpSelfHealAuthorizer
from nas_container_cr_service import ConfiguredNasContainerCrService
from project_cr_service import ConfiguredProjectCrService
from project_close_state import write_project_close
from series_324_live_closure import evaluate as evaluate_324_closure, next_action as next_324_action
from persistence import atomic_write_json, load_json
from protected_action_executor import ProtectedActionExecutor
from progress_truth import build_task_progress
from roadmap_regie import RoadmapRegie
from state_reconciliation import StateReconciler


def _read_manager_version(app_root) -> str:
    path = Path(app_root or '.') / 'VERSION.txt'
    try:
        return path.read_text(encoding='utf-8').strip() or 'NOG_TE_CONTROLEREN'
    except OSError:
        return 'NOG_TE_CONTROLEREN'


class ProjectmanagerRuntime:
    def __init__(self, config, *, base_service=None, project_cr_service=None, nas_container_cr_service=None):
        self.config = config
        self.base = base_service or ConfiguredManagerService(config)
        root = Path(config.system_root)
        self.root = root
        self.commands = CommandStore(root / 'commands' / 'queue.json')
        self.approved_actions = ApprovedActionStore(root / 'approved_actions' / 'queue.json')
        self.handoffs = getattr(self.base, 'handoffs', None) or HandoffQueue(root / 'handoffs' / 'queue.json')
        self.roadmap = getattr(self.base, 'roadmap', None) or RoadmapRegie(root / 'roadmap' / 'queue.json')
        self.conversation_intake = ConversationIntakeBridge(
            root / 'intake' / 'items.json',
            self.base.tasks,
            self.base.document_sync,
            config.reports_root,
            opportunity_register=getattr(self.base, 'opportunities', None),
            roadmap_regie=self.roadmap,
        )

        recovered = self.commands.recover_interrupted()
        self.recovered_commands = recovered
        if recovered:
            issues = getattr(self.base, 'issues', None)
            if issues is not None:
                issues.open(
                    'commands:interrupted_after_restart',
                    severity='ORANGE',
                    title='Projectmanager commands onderbroken door restart',
                    details={'count': len(recovered), 'command_ids': [item.get('id') for item in recovered[:20]]},
                )
            self.base.audit.write(
                'command.restart_recovery',
                actor='projectmanager',
                result='safe',
                details={'count': len(recovered)},
            )

        mode_bridge = ModeBridge(config.mode_command_path) if getattr(config, 'mode_command_path', '') else None
        self.mode_bridge = mode_bridge
        if project_cr_service is None:
            project_cr_service = ConfiguredProjectCrService(config.project_root)
        if nas_container_cr_service is None:
            nas_container_cr_service = ConfiguredNasContainerCrService(config.project_root)
        self.project_cr_service = project_cr_service
        self.nas_container_cr_service = nas_container_cr_service
        self.processor = CommandProcessor(
            self.commands,
            self.base.decisions,
            self.base.mode,
            self.base.tasks,
            audit=self.base.audit,
            mode_bridge=mode_bridge,
            approved_actions=self.approved_actions,
            project_cr_service=self.project_cr_service,
            nas_container_cr_service=self.nas_container_cr_service,
            conversation_intake=self.conversation_intake,
            project_root=config.project_root,
        )
        ingress_root = getattr(config, 'command_ingress_root', '') or ''
        self.ingress = CommandIngressConsumer(
            ingress_root or None,
            root / 'commands' / 'ingress_receipts.json',
            self.commands,
        )
        approval_root = getattr(config, 'approval_ingress_root', '') or ''
        self.approvals = ApprovalIngressConsumer(
            approval_root or None,
            root / 'decisions' / 'approval_ingress_receipts.json',
            self.base.decisions,
        )
        handoff_result_root = getattr(config, 'handoff_result_ingress_root', '') or ''
        self.handoff_results = HandoffResultIngressConsumer(
            handoff_result_root or None,
            root / 'handoffs' / 'result_ingress_receipts.json',
            self.handoffs,
            self.base.tasks,
            self.roadmap,
        )
        self.protected_executor = ProtectedActionExecutor(
            config.project_root,
            self.approved_actions,
            self.commands,
            self.base.decisions,
            audit=self.base.audit,
        )
        self.native_mcp_self_heal = NativeMcpSelfHealAuthorizer(
            config.project_root,
            self.commands,
            self.base.decisions,
            audit=self.base.audit,
        )
        self.release_validation_path = (
            Path(config.project_root) / 'Inbox' / 'operating_mode' / 'release_validation_hold.json'
        )
        self.state_reconciler = StateReconciler(
            self.base.tasks,
            self.base.decisions,
            self.commands,
            self.handoffs,
            getattr(self.base, 'issues', None),
            audit=self.base.audit,
        )
        self._operation_lock = threading.RLock()
        self.conversation_approval = ConversationApprovalCoordinator(
            root / 'decisions' / 'conversation_challenges.json',
            self.base.decisions,
            commands=self.commands,
            audit=self.base.audit,
        )
        self.handover_snapshots = HandoverSnapshotService(
            root,
            project_root=config.project_root,
            issues=getattr(self.base, 'issues', None),
            audit=self.base.audit,
        )
        self.conversation = ProjectmanagerConversationRuntime(
            root,
            intake=self.conversation_intake,
            approval=self.conversation_approval,
            handover=self.handover_snapshots,
            audit=self.base.audit,
            reports_root=config.reports_root,
        )

    def _open_issue(self, fingerprint, *, severity, title, details):
        issues = getattr(self.base, 'issues', None)
        if issues is not None:
            issues.open(fingerprint, severity=severity, title=title, details=details)

    def _queue_324_action_once(self, intent: str, release_version: str):
        active_statuses = {'PENDING','PROCESSING','WAITING_APPROVAL','APPROVED_READY','APPROVED_WAITING_EXECUTOR'}
        matching = [item for item in self.commands.all() if item.get('intent') == intent and item.get('release_version') == release_version]
        if any(item.get('status') in active_statuses for item in matching):
            return {'status':'already_pending','intent':intent}
        # A successful command is not repeated in the same manager cycle; health
        # immediately after execution decides whether another attempt is needed.
        if matching and matching[-1].get('status') == 'DONE':
            return {'status':'already_done','intent':intent}
        if matching and matching[-1].get('status') in {'FAILED', 'CANCELLED'}:
            previous = matching[-1]
            return {
                'status': 'previous_terminal_block',
                'intent': intent,
                'previous_status': previous.get('status'),
                'previous_command_id': previous.get('id'),
            }
        command = self.commands.enqueue({
            'intent': intent, 'source':'projectmanager_auto',
            'text': f'32.4 live closure: {intent}',
            'release_version': release_version,
            'title': f'32.4 live closure {intent}',
            'goal': 'Autonoom afronden van de goedgekeurde 32.4 live acceptance.',
            'steps_total': 1, 'priority': 1,
        })
        return {'status':'queued','intent':intent,'command_id':command.get('id')}

    def _reconcile_324_live_closure(self, status: dict):
        release_version = str(((status.get('release') or {}).get('installed_version') or (status.get('release') or {}).get('version') or '')).strip()
        if not release_version:
            try:
                release_version = (Path(self.config.project_root) / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
            except OSError:
                return {'status':'NOT_APPLICABLE','reason':'release_version_unavailable'}
        try:
            parts = tuple(int(x) for x in release_version.split('.'))
        except ValueError:
            return {'status':'NOT_APPLICABLE','reason':'release_version_invalid','release_version':release_version}
        if parts < (32,4,38):
            return {'status':'NOT_APPLICABLE','release_version':release_version}

        checks = [dict(item) for item in ((status.get('health') or {}).get('checks') or [])]
        by_name = {str(item.get('name')):str(item.get('status')) for item in checks}
        clearup_path = Path(self.config.project_root) / 'Inbox/logs/project_clearup_runtime.json'
        clearup = load_json(clearup_path, default={}) or {}
        clearup_done = bool(
            str(clearup.get('status') or '') in {'completed','already_completed','no_action'}
            and str(clearup.get('release_version') or '') == release_version
        )
        closure = evaluate_324_closure(checks, clearup=clearup, release_version=release_version)

        # One current-release truth controls project-close side effects. Technical
        # runtime repair may continue while DEFERRED, but CR/CLEARUP only runs
        # after the technical PM gates are GREEN and the project close is still
        # incomplete. Once complete, return to DEFERRED to prevent repeats.
        if closure.get('pm_status') != 'GREEN':
            desired_state = 'DEFERRED'
            close_reason = 'pm_technical_gates_not_green'
        elif closure.get('project_close_status') == 'GREEN':
            desired_state = 'DEFERRED'
            close_reason = 'project_close_complete'
        else:
            desired_state = 'REQUESTED'
            close_reason = 'project_close_incomplete'
        try:
            close_state = write_project_close(
                self.config.project_root,
                release_version=release_version,
                state=desired_state,
                reason=close_reason,
                source='projectmanager_series_32_4_closure',
            )
            close_state_error = ''
        except Exception as exc:
            close_state = {
                'state': 'DEFERRED', 'current': False, 'release_version': release_version,
                'reason': 'project_close_state_write_failed',
            }
            close_state_error = f'{type(exc).__name__}: {exc}'
            self._open_issue(
                'project_close:state_write_failed',
                severity='RED',
                title='Project-close state kon niet veilig worden vastgelegd',
                details={'release_version': release_version, 'error': close_state_error},
            )

        project_close_deferred = not (
            close_state.get('current') is True and close_state.get('state') == 'REQUESTED'
        )
        # 32.4.42 hardcoded project_close_deferred=True. 32.4.43 replaces
        # that split truth with the current shared project-close state.
        action = next_324_action(
            by_name,
            clearup_done=clearup_done,
            project_close_deferred=project_close_deferred,
        )
        closure['project_close_state'] = close_state
        closure['project_close_deferred'] = project_close_deferred
        if close_state_error:
            closure['project_close_state_error'] = close_state_error
        closure['next_action'] = action

        try:
            if closure.get('status') == 'GREEN':
                self.roadmap.mark_acceptance('32-4-closure-live', 'LIVE_PROVEN', evidence_refs=[str(clearup_path)], carry_forward=[])
                self.roadmap.mark_done_by_key('32-4-closure-live', evidence={'release_version':release_version,'clearup':str(clearup_path)})
            else:
                self.roadmap.mark_acceptance('32-4-closure-live', 'LIVE_REQUIRED', carry_forward=list(closure.get('failed_or_missing') or []))
        except (KeyError, ValueError):
            pass

        if closure.get('status') != 'GREEN' and action == 'REQUEST_WATCHER_RECREATE':
            closure['automation'] = self._queue_324_action_once('watcher_recreate', release_version)
        elif closure.get('status') != 'GREEN' and action == 'REQUEST_NATIVE_MCP_RELOAD':
            closure['automation'] = self._queue_324_action_once('native_mcp_reload', release_version)
        elif not project_close_deferred and action == 'CREATE_PROJECT_CR':
            closure['automation'] = self._queue_324_action_once("project_cr_create", release_version)
        elif not project_close_deferred and action == 'CREATE_NAS_CR':
            closure['automation'] = self._queue_324_action_once("nas_container_cr_create", release_version)
        elif not project_close_deferred and action == 'RUN_CLEARUP':
            closure['automation'] = {'status':'requested_by_shared_state','intent':'project_clearup'}

        atomic_write_json(self.root / 'state' / 'series_32_4_live_closure.json', closure)
        return closure


    def _sync_324_closure_task(self, closure, status):
        if not isinstance(closure, dict):
            return
        release = str(closure.get('release_version') or ((status.get('release') or {}).get('version') or '')).strip()
        if not release:
            return
        marker_title = f'{release} Projectmanager technische closure'
        active = self.base.tasks.active()
        if closure.get('pm_status') == 'GREEN':
            if active and active.get('title') == marker_title:
                self.base.tasks.progress(active['id'], step=2, steps_total=2, next_action='')
                gates = {
                    name: True for name in (
                        'code_ready','tests_green','functional_validation_green','kb_updated',
                        'roadmap_updated','handover_updated','release_ready','no_blockers'
                    )
                }
                self.base.tasks.complete(active['id'], gates)
            return
        if active is None:
            active = self.base.tasks.start(
                marker_title,
                'Autonoom alleen de technische Projectmanager-gates runtime-first afronden; Crash Recovery/CLEARUP blijven uitgesteld.',
                mode='MAINTENANCE',
                steps_total=2,
                priority=1,
                build_metadata={
                    'thinking_level': 'HOOG',
                    'release_version': release,
                    'estimated_total_seconds': 2700,
                    'estimated_test_verification_seconds': 900,
                    'step_estimates_seconds': [900, 1800],
                    'original_estimate_recorded_at': datetime.now(timezone.utc).isoformat(),
                },
            )
        if active.get('title') != marker_title:
            return
        mapping = {
            'REQUEST_WATCHER_RECREATE': (1, 'Watcher contract v3 recreëren en live bewijzen'),
            'REQUEST_NATIVE_MCP_RELOAD': (2, 'Native MCP reload + fingerprint readback'),
        }
        step, next_action = mapping.get(
            str(closure.get('next_action') or ''),
            (1, str(closure.get('next_action') or 'Projectmanager technische closure vervolgen')),
        )
        self.base.tasks.progress(active['id'], step=step, steps_total=2, next_action=next_action)

    def _release_validation_snapshot(self):
        path = self.release_validation_path
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data, dict):
                raise ValueError('release validation payload is not an object')
            data = dict(data)
            data['_source'] = str(path)
            return data
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return {'_source': str(path), 'error': f'{type(exc).__name__}: {exc}'}

    def _auto_route_release_ingress(self, runtime_snapshot: dict) -> dict:
        """Use the existing operational mode bridge when one release is waiting.

        The watcher remains fail-closed outside DEVELOPMENT; Projectmanager only
        selects the already-defined operational mode. Ambiguous inbox state never
        causes an automatic mode change.
        """
        release_chain = runtime_snapshot.get('release_chain') if isinstance(runtime_snapshot, dict) else {}
        release_chain = release_chain if isinstance(release_chain, dict) else {}
        incoming = release_chain.get('incoming') if isinstance(release_chain.get('incoming'), dict) else {}
        operating_mode = runtime_snapshot.get('operating_mode') if isinstance(runtime_snapshot, dict) else {}
        operating_mode = operating_mode if isinstance(operating_mode, dict) else {}
        try:
            count = int(incoming.get('count') or 0)
        except (TypeError, ValueError):
            count = 0
        mode = str(operating_mode.get('effective_mode') or '').strip().upper()
        if count <= 0:
            return {'status': 'NO_RELEASE_WAITING', 'requested_mode': None}
        if count != 1:
            return {'status': 'BLOCKED_AMBIGUOUS', 'requested_mode': None, 'incoming_count': count}
        if mode == 'DEVELOPMENT':
            return {'status': 'ALREADY_DEVELOPMENT', 'requested_mode': 'DEVELOPMENT'}
        if self.mode_bridge is None:
            return {'status': 'BLOCKED_MODE_BRIDGE_UNAVAILABLE', 'requested_mode': None}
        request = self.mode_bridge.request_base_mode(
            'DEVELOPMENT',
            reason='exactly one release ZIP waiting in Incoming',
            issued_by='projectmanager',
            confirmed_by_user=False,
        )
        return {
            'status': 'REQUESTED',
            'requested_mode': 'DEVELOPMENT',
            'incoming_count': 1,
            'mode_request': request,
        }

    def handles_conversation(self, text: str) -> bool:
        return self.conversation.handles(text) or self.conversation.handles_followup(text)

    def handle_conversation(self, **kwargs):
        with self._operation_lock:
            return self.conversation.handle(**kwargs)

    def run_once(self, *, now=None):
        with self._operation_lock:
            return self._run_once(now=now)

    def _run_once(self, *, now=None):
        handoff_results = self.handoff_results.consume(max_items=20)
        for result in handoff_results:
            self.base.audit.write(
                'handoff.result_ingress',
                actor='projectmanager',
                result='ok' if result.get('status') == 'APPLIED' else 'blocked',
                details=result,
            )
            if result.get('status') == 'REJECTED':
                self._open_issue(
                    f"handoff_result_ingress:{result.get('ingress_id')}",
                    severity='ORANGE',
                    title='Extern handoff-resultaat geweigerd',
                    details={'reason': result.get('reason')},
                )

        approval_results = self.approvals.consume(max_items=20)
        for result in approval_results:
            self.base.audit.write(
                'approval.ingress',
                actor='projectmanager',
                result='ok' if result.get('status') in {'APPLIED', 'IGNORED_ALREADY_RESOLVED'} else 'blocked',
                details=result,
            )
            if result.get('status') == 'REJECTED':
                self._open_issue(
                    f"approval_ingress:{result.get('ingress_id')}",
                    severity='ORANGE',
                    title='Lokale Projectmanager-goedkeuring geweigerd',
                    details={'reason': result.get('reason')},
                )

        ingress_results = self.ingress.consume(max_items=20)
        for result in ingress_results:
            self.base.audit.write(
                'command.ingress',
                actor='projectmanager',
                result='ok' if result.get('status') == 'IMPORTED' else 'blocked',
                details=result,
            )
            if result.get('status') == 'REJECTED':
                self._open_issue(
                    f"command_ingress:{result.get('ingress_id')}",
                    severity='ORANGE',
                    title='Extern Projectmanager-command geweigerd',
                    details={'reason': result.get('reason')},
                )

        try:
            active_release = (Path(self.config.project_root) / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()
        except OSError:
            active_release = ''
        superseded_release_commands = self.commands.supersede_stale_release_commands(active_release) if active_release else []
        if superseded_release_commands:
            self.base.audit.write(
                'command.release_owner.reconciled',
                actor='projectmanager',
                result='safe',
                details={'active_release': active_release, 'command_ids': [item.get('id') for item in superseded_release_commands]},
            )

        self_heal_authorization = self.native_mcp_self_heal.run_once()
        processed = self.processor.process_all(max_items=50)
        protected_results = self.protected_executor.run_once(max_items=5)
        runtime_snapshot = self.base.runtime_collector.collect()
        release_ingress_mode = self._auto_route_release_ingress(runtime_snapshot)
        release_validation = self._release_validation_snapshot()
        issues = getattr(self.base, 'issues', None)
        issue_repairs = collect_issue_repair_evidence(
            self.root,
            issues.open_items() if issues is not None else [],
        )
        reconciliation_result = self.state_reconciler.reconcile(
            runtime=runtime_snapshot,
            release_validation=release_validation,
            now=now,
            issue_repairs=issue_repairs,
        )
        previous_defer_current = bool(getattr(self.base, 'defer_current_publication', False))
        self.base.defer_current_publication = True
        try:
            status = dict(self.base.run_once(now=now))
        finally:
            self.base.defer_current_publication = previous_defer_current
        cycle_generation = uuid4().hex
        status['cycle_generation'] = cycle_generation
        status['provenance'] = {'generation': cycle_generation, 'phase': 'FINAL'}
        status['manager'] = {'version': _read_manager_version(getattr(self.config, 'manager_app_root', ''))}
        status['handoff_result_ingress_results'] = handoff_results[-20:]
        status['approval_ingress_results'] = approval_results[-20:]
        status['ingress_results'] = ingress_results[-20:]
        status['processed_commands'] = len(processed)
        status['native_mcp_self_heal_authorization'] = self_heal_authorization
        status['superseded_release_commands'] = superseded_release_commands[-20:]
        status['protected_executor_results'] = protected_results[-20:]
        status['release_ingress_mode_route'] = release_ingress_mode
        if processed:
            status['command_results'] = processed[-20:]
        status['interrupted_commands'] = len(self.commands.by_status('INTERRUPTED'))
        status['approved_actions'] = self.approved_actions.open_items()
        status['handoffs'] = self.handoffs.open_items()
        status['canonical_roadmap'] = self.roadmap.canonical_metadata()
        status['conversation_intake'] = self.conversation_intake.summary()
        status['state_reconciliation'] = reconciliation_result
        status['series_324_live_closure'] = self._reconcile_324_live_closure(status)
        self._sync_324_closure_task(status['series_324_live_closure'], status)
        self._refresh_coordination(status)
        self._finalize_coordination_audit(status, now=now)
        return status

    def _finalize_coordination_audit(self, status: dict, *, now=None):
        audit_now = now or datetime.now(timezone.utc)
        checks = [
            dict(item) for item in ((status.get('health') or {}).get('checks') or [])
            if item.get('name') != 'projectmanager_self_audit'
        ]
        generation = str(status.get('cycle_generation') or '').strip()
        if not generation:
            raise RuntimeError('cycle_generation ontbreekt vóór finale Projectmanager-audit')
        provenance = {'generation': generation, 'phase': 'FINAL'}
        status['provenance'] = provenance
        heartbeat_path = self.root / 'heartbeat' / 'manager.json'

        # Bounded stabilization: every published artifact keeps the exact same
        # generation.  We audit only after status, handover and heartbeat are all
        # written as FINAL, eliminating the previous write-order race.
        previous_signature = None
        for _attempt in range(3):
            heartbeat = load_json(heartbeat_path, default={}) or {}
            heartbeat['health'] = (status.get('health') or {}).get('status', 'RED')
            heartbeat['mode'] = status.get('mode', 'USER')
            heartbeat['cycle_generation'] = generation
            heartbeat['provenance'] = provenance
            heartbeat['heartbeat_at'] = audit_now.isoformat()
            atomic_write_json(heartbeat_path, heartbeat)
            self._refresh_coordination(status)

            audit = self.base.self_auditor.run(now=audit_now, require_coordination=True)
            status['self_audit'] = audit
            status['health'] = summarize_health_with_self_audit(checks, audit)
            atomic_write_json(self.root / 'self_audit' / 'current.json', audit)

            reconcile_audit = getattr(self.base, '_reconcile_self_audit_outcome', None)
            if callable(reconcile_audit):
                reconcile_audit(audit, now=audit_now)
            issues = getattr(self.base, 'issues', None)
            status['open_issues'] = issues.open_items() if issues is not None else status.get('open_issues', [])

            heartbeat['health'] = status['health']['status']
            heartbeat['cycle_generation'] = generation
            heartbeat['provenance'] = provenance
            atomic_write_json(heartbeat_path, heartbeat)
            self._refresh_coordination(status)

            signature = (
                audit.get('status'),
                json.dumps(audit.get('invalid') or [], ensure_ascii=False, sort_keys=True),
                json.dumps(audit.get('warnings') or [], ensure_ascii=False, sort_keys=True),
                status['health']['status'],
            )
            if signature == previous_signature:
                return
            previous_signature = signature

        # A bounded third pass is enough to absorb issue reconciliation. If the
        # audit still oscillates, expose that as RED instead of looping forever.
        final_audit = self.base.self_auditor.run(now=audit_now, require_coordination=True)
        if final_audit.get('status') != status.get('self_audit', {}).get('status'):
            final_audit = dict(final_audit)
            final_audit.setdefault('invalid', []).append({
                'path': 'self_audit/current.json', 'reason': 'final_audit_not_stable_within_bound',
            })
            final_audit['status'] = 'RED'
        status['self_audit'] = final_audit
        status['health'] = summarize_health_with_self_audit(checks, final_audit)
        atomic_write_json(self.root / 'self_audit' / 'current.json', final_audit)
        heartbeat = load_json(heartbeat_path, default={}) or {}
        heartbeat.update({
            'health': status['health']['status'], 'mode': status.get('mode', 'USER'),
            'cycle_generation': generation, 'provenance': provenance,
        })
        atomic_write_json(heartbeat_path, heartbeat)
        self._refresh_coordination(status)


    def _refresh_coordination(self, status: dict):
        current_mode = self.base.mode.get()
        active = self.base.tasks.active()
        decisions = self.base.decisions.pending()
        status['mode'] = current_mode.get('mode', status.get('mode', 'USER'))
        status['active_task'] = active
        status['progress'] = build_task_progress(active)
        status['decisions_needed'] = decisions
        status['needs_human'] = bool(decisions)
        status['next_action'] = (active or {}).get('next_action')
        status['pending_commands'] = self.commands.pending_count()
        status['approved_actions'] = self.approved_actions.open_items()
        status['handoffs'] = self.handoffs.open_items()
        status['canonical_roadmap'] = self.roadmap.canonical_metadata()
        status['acceptance_matrix'] = self.roadmap.acceptance_summary()
        status['development_efficiency'] = (status.get('progress') or {}).get('development_efficiency') or {}
        status['development_context'] = {
            'runtime_truth': 'Inbox/projectmanager_v2/RuntimeV2/development_context/current.json',
            'runtime_truth_primary': True,
            'active_context':'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_ACTIVE_DEVELOPMENT_CONTEXT.md',
            'manifest':'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_DEVELOPMENT_MANIFEST.md',
            'ledger':'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/01_UNIFIED_DEVELOPMENT_LEDGER.md',
            'live_handover_primary':True,
        }
        status['conversation_intake'] = self.conversation_intake.summary()
        issues = getattr(self.base, 'issues', None)
        status['open_issues'] = issues.open_items() if issues is not None else status.get('open_issues', [])
        atomic_write_json(self.root / 'status' / 'current.json', status)
        handover = build_handover(
            mode=current_mode,
            active_task=active,
            release=status.get('release') or {},
            decisions=decisions,
            evidence=(status.get('health') or {}).get('checks', []),
            last_changes=[
                f"command:{item.get('intent')}:{item.get('status')}"
                for item in status.get('command_results', [])
            ],
            progress=status.get('progress'),
        )
        handover['manager'] = status.get('manager', {})
        handover['open_issues'] = status.get('open_issues', [])
        handover['interrupted_commands'] = status.get('interrupted_commands', 0)
        handover['approved_actions'] = status.get('approved_actions', [])
        handover['handoffs'] = status.get('handoffs', [])
        handover['canonical_roadmap'] = status.get('canonical_roadmap', {})
        handover['acceptance_matrix'] = status.get('acceptance_matrix', {})
        handover['development_efficiency'] = status.get('development_efficiency', {})
        handover['development_context'] = status.get('development_context', {})
        handover['conversation_intake'] = status.get('conversation_intake', {})
        handover['state_reconciliation'] = status.get('state_reconciliation', {})
        handover['cycle_generation'] = status.get('cycle_generation')
        handover['provenance'] = status.get('provenance', {})
        atomic_write_json(self.root / 'handover' / 'current.json', handover)
