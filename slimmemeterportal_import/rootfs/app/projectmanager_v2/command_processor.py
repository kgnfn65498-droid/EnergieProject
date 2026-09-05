from approval_gate import PROTECTED_ACTIONS, can_execute
from command_gateway import plan_command


class CommandProcessor:
    def __init__(self, commands, decisions, mode_store, task_store, *, audit=None, mode_bridge=None, approved_actions=None):
        self.commands = commands
        self.decisions = decisions
        self.mode = mode_store
        self.tasks = task_store
        self.audit = audit
        self.mode_bridge = mode_bridge
        self.approved_actions = approved_actions

    def _request_mode(self, mode: str, *, reason: str, source: str):
        if self.mode_bridge is not None:
            return self.mode_bridge.request_base_mode(mode, reason=reason, issued_by='projectmanager')
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
        )
        task = self.tasks.start(
            item.get('title') or item.get('text') or f'{target_mode.title()} task',
            item.get('goal') or item.get('text') or f'{target_mode.title()} task',
            mode=target_mode,
            steps_total=max(1, int(item.get('steps_total') or 1)),
            priority=int(item.get('priority') or 2),
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

        if action == 'production_deploy':
            if self.approved_actions is None:
                raise RuntimeError('approved action store unavailable; fail closed')
            approved_action = self.approved_actions.add(
                decision=approval,
                command=item,
                action=action,
            )
            return {
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
            if item.get('source') == 'mcp_remote' and action in {'mode_development', 'mode_maintenance'}:
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
                mode_request = self._request_mode('DEVELOPMENT', reason=item.get('text') or 'development command', source=item.get('source'))
                task = self.tasks.start(
                    item.get('title') or item.get('text') or 'Development task',
                    item.get('goal') or item.get('text') or 'Development task',
                    mode='DEVELOPMENT',
                    steps_total=max(1, int(item.get('steps_total') or 1)),
                    priority=int(item.get('priority') or 2),
                )
                if item.get('next_action'):
                    task = self.tasks.progress(task['id'], next_action=item['next_action'])
                result = {'ok': True, 'executed': True, 'task_id': task['id'], 'requested_mode': 'DEVELOPMENT', 'mode_request': mode_request}
            elif action == 'mode_maintenance':
                mode_request = self._request_mode('MAINTENANCE', reason=item.get('text') or 'maintenance command', source=item.get('source'))
                task = self.tasks.start(
                    item.get('title') or item.get('text') or 'Maintenance task',
                    item.get('goal') or item.get('text') or 'Maintenance task',
                    mode='MAINTENANCE',
                    steps_total=max(1, int(item.get('steps_total') or 1)),
                    priority=int(item.get('priority') or 2),
                )
                result = {'ok': True, 'executed': True, 'task_id': task['id'], 'requested_mode': 'MAINTENANCE', 'mode_request': mode_request}
            elif action in {'read_status', 'read_energy', 'read_roadmap'}:
                result = {'ok': True, 'executed': False, 'read_request': action}
            elif action == 'admin_update':
                result = {'ok': True, 'executed': True, 'admin_note': item.get('text') or ''}
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
        return results

    def _audit(self, event_type, item, result):
        if self.audit is not None:
            self.audit.write(
                event_type,
                actor='projectmanager',
                result='ok' if item.get('status') in {'DONE', 'WAITING_APPROVAL', 'APPROVED_WAITING_EXECUTOR', 'CANCELLED'} else 'blocked',
                details={'command_id': item.get('id'), 'intent': item.get('intent'), 'result': result},
            )
