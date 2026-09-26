from system_path_contract import project_system_path
import json
from transition_state_io import read_transition_state
from approval_gate import PROTECTED_ACTIONS, can_execute
from command_gateway import plan_command
from development_build_contract import build_metadata_from_command
from release_controller_state import load_release_controller_state, release_active, release_view


class CommandProcessor:
    def __init__(self, commands, decisions, mode_store, task_store, *, audit=None, mode_bridge=None, approved_actions=None, project_cr_service=None, nas_container_cr_service=None, platform_test_service=None, conversation_intake=None, project_root=None):
        self.commands = commands
        self.decisions = decisions
        self.mode = mode_store
        self.tasks = task_store
        self.audit = audit
        self.mode_bridge = mode_bridge
        self.approved_actions = approved_actions
        self.project_cr_service = project_cr_service
        self.nas_container_cr_service = nas_container_cr_service
        self.platform_test_service = platform_test_service
        self.conversation_intake = conversation_intake
        self.project_root = project_root

    def _active_release(self):
        if not self.project_root:
            return ''
        from pathlib import Path
        try:
            return (Path(self.project_root) / 'App' / 'VERSIE.txt').read_text(encoding='utf-8').strip()
        except OSError:
            return ''

    def _release_controller_enabled(self):
        active = self._active_release()
        try:
            return tuple(int(part) for part in active.split('.')) >= (32, 4, 57)
        except ValueError:
            return False

    def _controller_state(self):
        if not self.project_root or not self._release_controller_enabled():
            return None
        return load_release_controller_state(self.project_root)

    def _guard_release_owned_closure(self, item, action):
        if action not in {'project_cr_create', 'nas_container_cr_create'}:
            return None
        active = self._active_release()
        # Backwards-compatible standalone/unit callers without a project root
        # have no release authority and keep the historical behavior. The real
        # embedded runtime always provides project_root and is strict.
        if not active:
            return None
        owned = str(item.get('release_version') or '').strip()
        if owned == active and owned:
            # A queued command can outlive the REQUESTED state that created it.
            # Recheck the shared gate at execution, before either CR service can
            # write a request or start a backup. Historical releases predate it.
            try:
                release_parts = tuple(int(part) for part in active.split('.'))
            except ValueError:
                raise RuntimeError('project_close_deferred: active release is invalid')
            if release_parts >= (32, 4, 57):
                # CR is post-release maintenance from 32.4.57 onward; it is no
                # longer sequenced by or allowed to gate the release controller.
                return None
            if release_parts >= (32, 4, 43):
                from project_close_state import load_project_close
                close = load_project_close(self.project_root, active_release=active)
                if close.get('current') is not True or close.get('state') != 'REQUESTED':
                    raise RuntimeError('project_close_deferred: current REQUESTED state required before CR execution')
            return None
        superseded = self.commands.supersede(
            item['id'],
            reason='release_owner_mismatch_or_missing',
            active_release=active,
        )
        self._audit('command.release_superseded', superseded, {
            'owned_release': owned, 'active_release': active, 'side_effect_executed': False,
        })
        return superseded


    def _guard_active_transition_mutation(self, item, action):
        if not self.project_root:
            return None
        if self._release_controller_enabled():
            state = self._controller_state()
            if not release_active(state):
                return None
            # Normal PM work, mode changes and post-release maintenance no longer
            # participate in release sequencing. Only competing release mutation
            # is fenced while the one controller owns a generation.
            if action in {'production_deploy', 'native_mcp_reload', 'watcher_recreate', 'release_recover'}:
                raise RuntimeError('release_controller_active_competing_release_mutation_blocked')
            return None
        from pathlib import Path
        path = project_system_path(Path(self.project_root), 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json')
        transition = read_transition_state(path, missing_ok=True)
        if not isinstance(transition, dict):
            return None
        if str(transition.get('lifecycle_state') or '').upper() in {'COMPLETE', 'ROLLED_BACK', 'CANCELLED'}:
            return None

        # Read-only commands remain available while release mutation is fenced.
        if action in {'read_status', 'read_energy', 'read_roadmap'}:
            return None

        # Release executors are allowed only with the exact current coordinator
        # ticket; the detailed identity check is performed immediately after
        # this general mutation gate by _guard_transition_ticket.
        transition_actions = {'native_mcp_reload', 'watcher_recreate', 'project_cr_create', 'nas_container_cr_create'}
        if action in transition_actions and str(item.get('transition_generation') or '') == str(transition.get('generation_id') or ''):
            return None

        raise RuntimeError('release_transition_active_normal_mutation_blocked')

    def _guard_transition_ticket(self, item, action):
        if self._release_controller_enabled():
            return None
        protected = {'native_mcp_reload', 'watcher_recreate', 'project_cr_create', 'nas_container_cr_create'}
        if action not in protected or not self.project_root:
            return None
        from pathlib import Path
        path = project_system_path(Path(self.project_root), 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json')
        transition = read_transition_state(path, missing_ok=True)
        if not isinstance(transition, dict) or str(transition.get('lifecycle_state') or '') in {'COMPLETE','ROLLED_BACK','CANCELLED'}:
            return None
        ticket = transition.get('current_ticket') if isinstance(transition.get('current_ticket'), dict) else {}
        required = {
            'transition_generation': transition.get('generation_id'),
            'transition_phase': transition.get('phase'),
            'transition_request_id': ticket.get('request_id'),
            'transition_idempotency_key': ticket.get('idempotency_key'),
            'executor_name': ticket.get('executor_name'),
            'release_owner': transition.get('to_release'),
        }
        mismatched = [key for key,value in required.items() if not value or str(item.get(key) or '') != str(value)]
        if mismatched:
            raise RuntimeError('release_transition_ticket_required:' + ','.join(mismatched))
        return None

    def _request_mode(self, mode: str, *, reason: str, source: str, confirmed_by_user: bool=False):
        if self.mode_bridge is not None:
            return self.mode_bridge.request_base_mode(mode, reason=reason, issued_by='projectmanager', confirmed_by_user=confirmed_by_user)
        self.mode.set(mode, reason=reason, source=source or 'command')
        return None

    def resume_resolved_decisions(self):
        resumed = []
        for item in self.commands.by_status('WAITING_APPROVAL'):
            decision_id = item.get('approval_decision_id')
            if not decision_id:
                self.commands.fail(item['id'], error='WAITING_APPROVAL without decision id')
                continue
            try:
                decision = self.decisions.get(decision_id)
            except KeyError:
                self.commands.fail(item['id'], error='approval decision missing')
                continue
            if decision.get('status') == 'APPROVED':
                resumed.append(self.commands.mark_approved_ready(item['id']))
                self._audit('command.approval.resumed', item, {'decision_id': decision_id})
            elif decision.get('status') == 'REJECTED':
                cancelled = self.commands.cancel(item['id'], reason='Peter rejected protected action')
                resumed.append(cancelled)
                self._audit('command.approval.rejected', cancelled, {'decision_id': decision_id})
        return resumed

    @staticmethod
    def _approval_matches(action: str, approval: dict) -> bool:
        required_kind = PROTECTED_ACTIONS.get(action)
        return bool(
            required_kind
            and approval
            and approval.get('kind') == required_kind
            and approval.get('status') == 'APPROVED'
            and approval.get('approved_by') == 'Peter'
        )

    @staticmethod
    def _mode_approval_matches(approval: dict) -> bool:
        return bool(
            approval
            and approval.get('kind') == 'MODE_CHANGE'
            and approval.get('status') == 'APPROVED'
            and approval.get('approved_by') == 'Peter'
        )

    @staticmethod
    def _decision_context(item: dict, *, target_mode=None):
        context = {
            'command_id': item.get('id'),
            'source': item.get('source'),
            'intent': item.get('intent'),
            'title': item.get('title'),
            'goal': item.get('goal'),
            'steps_total': item.get('steps_total'),
            'priority': item.get('priority'),
            'next_action': item.get('next_action'),
            'artifact_path': item.get('artifact_path'),
            'artifact_sha256': item.get('artifact_sha256'),
            'release_version': item.get('release_version'),
            'verification_report': item.get('verification_report'),
        }
        if target_mode:
            context['target_mode'] = target_mode
        return context

    def _remote_mode_change(self, item, plan):
        target_mode = 'DEVELOPMENT' if plan.get('action') == 'mode_development' else 'MAINTENANCE'
        decision_id = item.get('approval_decision_id')
        if not decision_id:
            decision = self.decisions.request(
                'MODE_CHANGE',
                item.get('text') or f'Wijzig Projectmanager-modus naar {target_mode}?',
                fingerprint=f"command:{item['id']}:MODE_CHANGE",
                context=self._decision_context(item, target_mode=target_mode),
            )
            waiting = self.commands.wait_for_approval(item['id'], decision_id=decision['id'])
            self._audit('command.mode_decision_requested', waiting, {'decision_id': decision['id'], 'target_mode': target_mode})
            return waiting

        approval = self.decisions.get(decision_id)
        if not self._mode_approval_matches(approval):
            raise RuntimeError('remote mode command resumed without Peter MODE_CHANGE approval')
        mode_request = self._request_mode(
            target_mode,
            reason=item.get('text') or f'Peter approved {target_mode}',
            source='approved_decision',
            confirmed_by_user=True,
        )
        task = self.tasks.start(
            item.get('title') or item.get('text') or f'{target_mode.title()} task',
            item.get('goal') or item.get('text') or f'{target_mode.title()} task',
            mode=target_mode,
            steps_total=max(1, int(item.get('steps_total') or 1)),
            priority=int(item.get('priority') or 2),
            build_metadata=build_metadata_from_command(item),
        )
        if item.get('next_action'):
            task = self.tasks.progress(task['id'], next_action=item['next_action'])
        result = {
            'ok': True,
            'executed': True,
            'approved_continuation': True,
            'protected_side_effect_executed': False,
            'task_id': task['id'],
            'requested_mode': target_mode,
            'mode_request': mode_request,
            'approval_decision_id': approval['id'],
        }
        finished = self.commands.complete(item['id'], result=result)
        self._audit('command.mode_approved_continued', finished, result)
        return finished

    def _approved_continuation(self, item, plan, approval):
        action = plan.get('action')
        if not self._approval_matches(action, approval):
            raise RuntimeError('approval does not match protected action')

        protected_execution_allowed = can_execute(
            action,
            safety={'proven_safe': False},
            approval=approval,
        )
        if protected_execution_allowed:
            raise RuntimeError('protected side effect unexpectedly became executable without safety evidence')

        if action == 'architecture_change':
            mode_request = self._request_mode(
                'DEVELOPMENT',
                reason=item.get('text') or 'approved architecture change',
                source='approved_decision',
            )
            task = self.tasks.start(
                item.get('title') or item.get('text') or 'Approved architecture change',
                item.get('goal') or item.get('text') or 'Continue approved architecture work in staging',
                mode='DEVELOPMENT',
                steps_total=max(1, int(item.get('steps_total') or 1)),
                priority=int(item.get('priority') or 2),
                build_metadata=build_metadata_from_command(item),
            )
            next_action = item.get('next_action') or 'continue approved architecture work in isolated staging and verify before deployment'
            task = self.tasks.progress(task['id'], next_action=next_action, change='Peter approved architecture_change')
            return {
                'ok': True,
                'executed': True,
                'approved_continuation': True,
                'production_changed': False,
                'protected_side_effect_executed': False,
                'protected_execution_gate': 'BLOCKED_UNTIL_PROVEN_SAFE',
                'task_id': task['id'],
                'requested_mode': 'DEVELOPMENT',
                'mode_request': mode_request,
                'approval_decision_id': approval['id'],
                'next_action': next_action,
            }

        if action in {'production_deploy', 'native_mcp_reload', 'watcher_recreate'}:
            if self.approved_actions is None:
                raise RuntimeError('approved action store unavailable; fail closed')
            mode_request = None
            requested_mode = None
            if action == 'production_deploy' and not self._release_controller_enabled():
                # Legacy watcher releases required DEVELOPMENT. 32.4.57+ Incoming
                # is mode-independent and must not create a mode dependency.
                requested_mode = 'DEVELOPMENT'
                mode_request = self._request_mode(
                    'DEVELOPMENT',
                    reason=item.get('text') or 'approved release publication requires release ingress',
                    source='approved_decision',
                    confirmed_by_user=False,
                )
            approved_action = self.approved_actions.add(
                decision=approval,
                command=item,
                action=action,
            )
            result = {
                'ok': True,
                'executed': False,
                'approved_continuation': True,
                'awaiting_executor': True,
                'production_changed': False,
                'protected_side_effect_executed': False,
                'protected_execution_gate': 'APPROVED_AWAITING_SAFETY_OR_EXECUTOR',
                'approved_action_id': approved_action['id'],
                'approval_decision_id': approval['id'],
                'approved_action': approved_action,
            }
            if requested_mode:
                result['requested_mode'] = requested_mode
                result['mode_request'] = mode_request
            return result
        raise RuntimeError(f'unsupported protected continuation: {action}')

    def process_next(self):
        item = self.commands.claim_next()
        if item is None:
            return None
        plan = plan_command(item)
        try:
            if plan.get('action') == 'blocked':
                raise RuntimeError(f"blocked: {plan.get('reason', 'unknown_intent_fail_closed')}")

            action = plan.get('action')
            self._guard_active_transition_mutation(item, action)
            self._guard_transition_ticket(item, action)
            superseded = self._guard_release_owned_closure(item, action)
            if superseded is not None:
                return superseded
            if (
                item.get('source') == 'mcp_remote'
                and action in {'mode_development', 'mode_maintenance'}
                and item.get('approval_decision_id')
            ):
                # Backward compatibility for already-pending pre-32.4.35 decisions.
                # New operational mode commands follow COMMANDS.allowed_without_approval
                # and are processed directly below.
                return self._remote_mode_change(item, plan)

            if not plan.get('allowed_without_approval', False):
                decision_id = item.get('approval_decision_id')
                if decision_id:
                    approval = self.decisions.get(decision_id)
                    if approval.get('status') != 'APPROVED':
                        raise RuntimeError('protected command resumed without approved decision')
                    result = self._approved_continuation(item, plan, approval)
                    if result.get('awaiting_executor'):
                        waiting = self.commands.wait_for_executor(
                            item['id'],
                            approved_action=result['approved_action'],
                            result={key: value for key, value in result.items() if key != 'approved_action'},
                        )
                        self._audit('command.approved_handed_off', waiting, result)
                        return waiting
                    finished = self.commands.complete(item['id'], result=result)
                    self._audit('command.approved_continued', finished, result)
                    return finished

                decision = self.decisions.request(
                    plan['decision_kind'],
                    item.get('text') or f"Approval required for {plan.get('intent')}",
                    fingerprint=f"command:{item['id']}:{plan['decision_kind']}",
                    context=self._decision_context(item),
                )
                waiting = self.commands.wait_for_approval(item['id'], decision_id=decision['id'])
                self._audit('command.decision_requested', waiting, {'decision_id': decision['id'], 'executed': False})
                return waiting

            if action == 'mode_development':
                mode_request = self._request_mode(
                    'DEVELOPMENT',
                    reason=item.get('text') or 'development command',
                    source=item.get('source'),
                    confirmed_by_user=(item.get('source') == 'mcp_remote'),
                )
                task = self.tasks.start(
                    item.get('title') or item.get('text') or 'Development task',
                    item.get('goal') or item.get('text') or 'Development task',
                    mode='DEVELOPMENT',
                    steps_total=max(1, int(item.get('steps_total') or 1)),
                    priority=int(item.get('priority') or 2),
                    build_metadata=build_metadata_from_command(item),
                )
                if item.get('next_action'):
                    task = self.tasks.progress(task['id'], next_action=item['next_action'])
                result = {'ok': True, 'executed': True, 'task_id': task['id'], 'requested_mode': 'DEVELOPMENT', 'mode_request': mode_request}
            elif action == 'mode_maintenance':
                mode_request = self._request_mode(
                    'MAINTENANCE',
                    reason=item.get('text') or 'maintenance command',
                    source=item.get('source'),
                    confirmed_by_user=(item.get('source') == 'mcp_remote'),
                )
                task = self.tasks.start(
                    item.get('title') or item.get('text') or 'Maintenance task',
                    item.get('goal') or item.get('text') or 'Maintenance task',
                    mode='MAINTENANCE',
                    steps_total=max(1, int(item.get('steps_total') or 1)),
                    priority=int(item.get('priority') or 2),
                    build_metadata=build_metadata_from_command(item),
                )
                result = {'ok': True, 'executed': True, 'task_id': task['id'], 'requested_mode': 'MAINTENANCE', 'mode_request': mode_request}
            elif action in {'read_status', 'read_energy', 'read_roadmap'}:
                result = {'ok': True, 'executed': False, 'read_request': action}
            elif action == 'conversation_intake':
                if self.conversation_intake is None:
                    raise RuntimeError('conversation_intake_unavailable')
                intake = self.conversation_intake.accept(item)
                result = {'ok': True, 'executed': True, 'intake': intake}
            elif action == 'admin_update':
                hint = str(item.get('classification_hint') or '')
                if hint == 'clearup_apply':
                    if not self.project_root:
                        raise RuntimeError('clearup_apply requires project_root')
                    from clearup_chat_service import apply_clearup_001
                    result = dict(apply_clearup_001(
                        self.project_root, explicit_user_text=str(item.get('text') or ''), source=str(item.get('source') or ''),
                    ))
                    result['executed'] = True
                    result['action'] = 'clearup_apply'
                    result['transport_intent'] = 'admin_update'
                elif hint in {
                    'clearup_type2_prepare', 'clearup_type2_refresh_recovery', 'clearup_type2_export_info', 'clearup_type2_export_chunk',
                    'clearup_type2_migrate', 'clearup_type2_validate', 'clearup_type2_external_recovery_confirm', 'clearup_type2_finalize', 'clearup_type2_restore',
                }:
                    if not self.project_root:
                        raise RuntimeError('Type2 ClearUp requires project_root')
                    from clearup_type2_service import (
                        prepare_type2, refresh_recovery_type2, export_info, export_chunk,
                        migrate_type2, validate_type2, confirm_external_recovery_type2, finalize_type2, restore_type2,
                    )
                    clearup_id = str(item.get('artifact_path') or '').strip()
                    source = str(item.get('source') or '')
                    if hint == 'clearup_type2_prepare':
                        result = dict(prepare_type2(self.project_root, clearup_id=clearup_id, source=source))
                    elif hint == 'clearup_type2_refresh_recovery':
                        result = dict(refresh_recovery_type2(self.project_root, clearup_id=clearup_id, source=source))
                    elif hint == 'clearup_type2_export_info':
                        result = dict(export_info(self.project_root, clearup_id=clearup_id, source=source))
                    elif hint == 'clearup_type2_export_chunk':
                        raw = str(item.get('text') or '').strip()
                        try:
                            args = json.loads(raw) if raw else {}
                        except json.JSONDecodeError as exc:
                            raise RuntimeError('Type2 export chunk text must be JSON') from exc
                        result = dict(export_chunk(
                            self.project_root, clearup_id=clearup_id,
                            offset=int(args.get('offset') or 0), max_bytes=int(args.get('max_bytes') or 32768), source=source,
                        ))
                    elif hint == 'clearup_type2_migrate':
                        result = dict(migrate_type2(
                            self.project_root, clearup_id=clearup_id, explicit_user_text=str(item.get('text') or ''), source=source,
                        ))
                    elif hint == 'clearup_type2_validate':
                        result = dict(validate_type2(self.project_root, clearup_id=clearup_id, source=source))
                    elif hint == 'clearup_type2_external_recovery_confirm':
                        result = dict(confirm_external_recovery_type2(
                            self.project_root, explicit_user_text=str(item.get('text') or ''), source=source,
                        ))
                    elif hint == 'clearup_type2_finalize':
                        result = dict(finalize_type2(
                            self.project_root, clearup_id=clearup_id, explicit_user_text=str(item.get('text') or ''), source=source,
                        ))
                    else:
                        result = dict(restore_type2(
                            self.project_root, clearup_id=clearup_id, explicit_user_text=str(item.get('text') or ''), source=source,
                        ))
                    result['executed'] = True
                    result['action'] = hint
                    result['transport_intent'] = 'admin_update'
                else:
                    result = {'ok': True, 'executed': True, 'admin_note': item.get('text') or ''}
            elif action == 'clearup_apply':
                if not self.project_root:
                    raise RuntimeError('clearup_apply requires project_root')
                from clearup_chat_service import apply_clearup_001
                result = dict(apply_clearup_001(
                    self.project_root, explicit_user_text=str(item.get('text') or ''), source=str(item.get('source') or ''),
                ))
                result['executed'] = True
                result['action'] = 'clearup_apply'
            elif action == 'release_recover':
                if not self.project_root:
                    raise RuntimeError('release_recover requires project_root')
                if self._release_controller_enabled():
                    state = self._controller_state()
                    result = {
                        'ok': True, 'executed': False, 'action': 'release_recover',
                        'recovery': {
                            'status': 'CONTROLLER_OWNED',
                            'reason': 'same_generation_resume_is_built_into_release_controller',
                            'release_controller': release_view(state),
                        },
                    }
                    finished = self.commands.complete(item['id'], result=result)
                    self._audit('command.processed', finished, result)
                    return finished
                from release_recovery import ReleaseRecoveryService
                recovery = ReleaseRecoveryService(self.project_root).recover()
                if recovery.get('needs_development'):
                    recovery['mode_request'] = self._request_mode(
                        'DEVELOPMENT',
                        reason='release_recover: canonical release ingress herstellen',
                        source=item.get('source') or 'projectmanager_auto',
                        confirmed_by_user=False,
                    )
                if recovery.get('needs_watcher_recreate'):
                    active_release = self._active_release()
                    existing = [
                        command for command in self.commands.all()
                        if command.get('intent') == 'watcher_recreate'
                        and command.get('status') in {'PENDING','PROCESSING','WAITING_APPROVAL','APPROVED_READY','APPROVED_WAITING_EXECUTOR'}
                        and str(command.get('release_version') or '') == active_release
                    ]
                    if existing:
                        recovery['watcher_recreate_command_id'] = existing[-1].get('id')
                    else:
                        queued = self.commands.enqueue({
                            'intent': 'watcher_recreate',
                            'source': 'projectmanager_auto',
                            'text': 'release_recover: herstel exact de bestaande release-watcher via protected route',
                            'release_version': active_release,
                            'title': 'Release recovery watcher recreate',
                            'goal': 'Herstel de canonieke watcher zonder alternatieve release-route.',
                            'steps_total': 1,
                            'priority': 1,
                        })
                        recovery['watcher_recreate_command_id'] = queued.get('id')
                result = {'ok': True, 'executed': True, 'action': 'release_recover', 'recovery': recovery}
            elif action == 'platformtest_run':
                if self.platform_test_service is None:
                    raise RuntimeError('platformtest service is niet geconfigureerd; fail closed')
                result = dict(self.platform_test_service.run(
                    candidate_sha=str(item.get('candidate_sha') or ''),
                    test_profile=str(item.get('test_profile') or 'publisher_full_suite_v1'),
                ) or {})
                if result.get('status') == 'PENDING':
                    pending = self.commands.requeue(item['id'], result=result)
                    self._audit('command.external_executor_pending', pending, result)
                    return pending
                if (
                    result.get('status') != 'GREEN'
                    or result.get('ok') is not True
                    or result.get('network_mode') != 'none'
                    or result.get('production_modified') is not False
                ):
                    raise RuntimeError('platformtest gaf geen GREEN geïsoleerd resultaat')
                result['executed'] = True
                result['action'] = 'platformtest_run'
            elif action == 'project_cr_create':
                if self.project_cr_service is None:
                    raise RuntimeError('EnergieProject CR service is niet geconfigureerd; fail closed')
                if self.project_root:
                    result = dict(self.project_cr_service.create(
                        command_id=item['id'], expected_release=str(item.get('release_version') or ''), wait_for_result=False,
                    ) or {})
                else:
                    result = dict(self.project_cr_service.create() or {})
                if result.get('status') == 'PENDING':
                    pending = self.commands.requeue(item['id'], result=result)
                    self._audit('command.external_executor_pending', pending, result)
                    return pending
                if result.get('ok') is not True or result.get('status') != 'GREEN' or result.get('deep_verified') is not True:
                    raise RuntimeError('EnergieProject CR service gaf geen GREEN deep-verified resultaat')
                result['executed'] = True
                result['action'] = 'project_cr_create'
            elif action == 'nas_container_cr_create':
                if self.nas_container_cr_service is None:
                    raise RuntimeError('NAS Container CR service is niet geconfigureerd; fail closed')
                if self.project_root:
                    result = dict(self.nas_container_cr_service.create(
                        command_id=item['id'], expected_release=str(item.get('release_version') or ''), wait_for_result=False,
                    ) or {})
                else:
                    result = dict(self.nas_container_cr_service.create() or {})
                if result.get('status') == 'PENDING':
                    pending = self.commands.requeue(item['id'], result=result)
                    self._audit('command.external_executor_pending', pending, result)
                    return pending
                if result.get('ok') is not True or result.get('status') != 'GREEN':
                    raise RuntimeError('NAS Container CR service gaf geen GREEN resultaat')
                if result.get('production_containers_changed') is not False:
                    raise RuntimeError('NAS Container CR mist bewijs PRODUCTION_CONTAINERS_CHANGED=NO')
                result['executed'] = True
                result['action'] = 'nas_container_cr_create'
            else:
                raise RuntimeError(f'unsupported safe action: {action}')

            finished = self.commands.complete(item['id'], result=result)
            self._audit('command.processed', finished, result)
            return finished
        except Exception as exc:
            finished = self.commands.fail(item['id'], error=f'{type(exc).__name__}: {exc}')
            self._audit('command.failed', finished, {'error': str(exc)})
            return finished

    def process_all(self, *, max_items=50):
        self.resume_resolved_decisions()
        results = []
        for _ in range(max(0, int(max_items))):
            result = self.process_next()
            if result is None:
                break
            results.append(result)
            if result.get('status') == 'PENDING' and result.get('pending_reason') == 'external_executor_pending':
                break
        return results

    def _audit(self, event_type, item, result):
        if self.audit is not None:
            self.audit.write(
                event_type,
                actor='projectmanager',
                result='ok' if item.get('status') in {'DONE', 'WAITING_APPROVAL', 'APPROVED_WAITING_EXECUTOR', 'CANCELLED'} else 'blocked',
                details={'command_id': item.get('id'), 'intent': item.get('intent'), 'result': result},
            )
