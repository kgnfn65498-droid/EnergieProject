from __future__ import annotations

from command_gateway import plan_command
from command_processor import CommandProcessor

_PENDING = {'PENDING', 'APPROVED_READY'}


class PreparedJobCommandProcessor(CommandProcessor):
    """32.5.31 typed prepared-job extension without changing legacy dispatch."""

    def __init__(self, *args, prepared_job_service=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.prepared_job_service = prepared_job_service

    def process_next(self):
        first = next((item for item in self.commands.all() if item.get('status') in _PENDING), None)
        if first is None or first.get('intent') != 'prepared_job_run':
            return super().process_next()

        item = self.commands.claim_next()
        if item is None:
            return None
        if item.get('id') != first.get('id'):
            finished = self.commands.fail(item['id'], error='RuntimeError: prepared_job queue identity race')
            self._audit('command.failed', finished, {'error': 'prepared_job queue identity race'})
            return finished

        try:
            plan = plan_command(item)
            if plan.get('action') != 'prepared_job_run' or plan.get('allowed_without_approval') is not True:
                raise RuntimeError('prepared_job command plan invalid')
            self._guard_active_transition_mutation(item, plan.get('action'))
            self._guard_transition_ticket(item, plan.get('action'))
            superseded = self._guard_release_owned_closure(item, plan.get('action'))
            if superseded is not None:
                return superseded
            if self.prepared_job_service is None:
                raise RuntimeError('prepared_job service is niet geconfigureerd; fail closed')

            active_task = self.tasks.active()
            result = dict(self.prepared_job_service.run(
                task=active_task or {},
                artifact_path=str(item.get('artifact_path') or ''),
                artifact_sha256=str(item.get('artifact_sha256') or ''),
                target_release=str(item.get('release_version') or ''),
                operation=str(item.get('classification_hint') or '').upper(),
            ) or {})

            if result.get('status') == 'PENDING':
                pending = self.commands.requeue(item['id'], result=result)
                self._audit('command.external_executor_pending', pending, result)
                return pending

            if (
                result.get('status') != 'GREEN'
                or result.get('ok') is not True
                or result.get('network_mode') != 'none'
                or result.get('project_mount') != 'read_only'
                or result.get('production_modified') is not False
                or result.get('container_removed') is not True
            ):
                raise RuntimeError('prepared_job gaf geen GREEN bounded resultaat')

            result['executed'] = True
            result['action'] = 'prepared_job_run'
            finished = self.commands.complete(item['id'], result=result)
            self._audit('command.processed', finished, result)
            return finished
        except Exception as exc:
            finished = self.commands.fail(item['id'], error=f'{type(exc).__name__}: {exc}')
            self._audit('command.failed', finished, {'error': str(exc)})
            return finished
