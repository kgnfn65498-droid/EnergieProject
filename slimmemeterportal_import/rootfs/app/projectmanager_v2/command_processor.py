from command_gateway import plan_command


class CommandProcessor:
    def __init__(self, commands, decisions, mode_store, task_store, *, audit=None, mode_bridge=None):
        self.commands = commands
        self.decisions = decisions
        self.mode = mode_store
        self.tasks = task_store
        self.audit = audit
        self.mode_bridge = mode_bridge

    def _request_mode(self, mode: str, *, reason: str, source: str):
        if self.mode_bridge is not None:
            return self.mode_bridge.request_base_mode(mode, reason=reason, issued_by='projectmanager')
        self.mode.set(mode, reason=reason, source=source or 'command')
        return None

    def process_next(self):
        item = self.commands.claim_next()
        if item is None:
            return None
        plan = plan_command(item)
        try:
            if plan.get('action') == 'blocked':
                raise RuntimeError(f"blocked: {plan.get('reason', 'unknown_intent_fail_closed')}")

            if not plan.get('allowed_without_approval', False):
                decision = self.decisions.request(
                    plan['decision_kind'],
                    item.get('text') or f"Approval required for {plan.get('intent')}",
                    fingerprint=f"command:{item['id']}:{plan['decision_kind']}",
                    context={'command_id':item['id'],'source':item.get('source'),'intent':item.get('intent')},
                )
                result = {'ok':True,'deferred_to_decision':decision['id'],'executed':False}
                finished = self.commands.complete(item['id'], result=result)
                self._audit('command.decision_requested', finished, result)
                return finished

            action = plan.get('action')
            if action == 'mode_development':
                mode_request=self._request_mode('DEVELOPMENT', reason=item.get('text') or 'development command', source=item.get('source'))
                task = self.tasks.start(
                    item.get('title') or item.get('text') or 'Development task',
                    item.get('goal') or item.get('text') or 'Development task',
                    mode='DEVELOPMENT',
                    steps_total=max(1, int(item.get('steps_total') or 1)),
                    priority=int(item.get('priority') or 2),
                )
                if item.get('next_action'):
                    task = self.tasks.progress(task['id'], next_action=item['next_action'])
                result = {'ok':True,'executed':True,'task_id':task['id'],'requested_mode':'DEVELOPMENT','mode_request':mode_request}
            elif action == 'mode_maintenance':
                mode_request=self._request_mode('MAINTENANCE', reason=item.get('text') or 'maintenance command', source=item.get('source'))
                task = self.tasks.start(
                    item.get('title') or item.get('text') or 'Maintenance task',
                    item.get('goal') or item.get('text') or 'Maintenance task',
                    mode='MAINTENANCE',
                    steps_total=max(1, int(item.get('steps_total') or 1)),
                    priority=int(item.get('priority') or 2),
                )
                result = {'ok':True,'executed':True,'task_id':task['id'],'requested_mode':'MAINTENANCE','mode_request':mode_request}
            elif action in {'read_status','read_energy','read_roadmap'}:
                result = {'ok':True,'executed':False,'read_request':action}
            elif action == 'admin_update':
                result = {'ok':True,'executed':True,'admin_note':item.get('text') or ''}
            else:
                raise RuntimeError(f'unsupported safe action: {action}')

            finished = self.commands.complete(item['id'], result=result)
            self._audit('command.processed', finished, result)
            return finished
        except Exception as exc:
            finished = self.commands.fail(item['id'], error=f'{type(exc).__name__}: {exc}')
            self._audit('command.failed', finished, {'error':str(exc)})
            return finished

    def process_all(self, *, max_items=50):
        results=[]
        for _ in range(max(0,int(max_items))):
            result=self.process_next()
            if result is None:
                break
            results.append(result)
        return results

    def _audit(self, event_type, item, result):
        if self.audit is not None:
            self.audit.write(event_type, actor='projectmanager', result='ok' if item.get('status')=='DONE' else 'blocked', details={'command_id':item.get('id'),'intent':item.get('intent'),'result':result})
