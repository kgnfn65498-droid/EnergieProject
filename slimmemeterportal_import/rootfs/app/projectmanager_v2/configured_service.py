from approved_action_store import ApprovedActionStore
from command_store import CommandStore
from manager_service import ManagerService
from runtime_sources import RuntimeCollector


class ConfiguredManagerService(ManagerService):
    """ManagerService wired to canonical runtime sources plus coordination gates."""

    def __init__(self, config, **kwargs):
        runtime_collector = kwargs.pop('runtime_collector', None)
        super().__init__(config, runtime_collector=runtime_collector, **kwargs)
        if runtime_collector is None:
            self.runtime_collector = RuntimeCollector(
                config.project_root,
                mode_state_path=getattr(config, 'mode_state_path', '') or None,
            )
        self._coordination_commands = CommandStore(self.root / 'commands' / 'queue.json')
        self._coordination_actions = ApprovedActionStore(self.root / 'approved_actions' / 'queue.json')

    def _maybe_select_roadmap_task(self, health: dict, pending_decisions: list):
        if self.tasks.active() is not None or pending_decisions:
            return None
        if health.get('status') == 'RED':
            return None
        if self.mode.get().get('mode') != 'USER':
            return None
        if self._coordination_commands.by_status(
            'PENDING',
            'PROCESSING',
            'WAITING_APPROVAL',
            'APPROVED_READY',
            'APPROVED_WAITING_EXECUTOR',
        ):
            return None
        if self._coordination_actions.open_items():
            return None

        item = self.roadmap.next_open(mode='USER')
        if not item:
            return None
        next_action = f"handoff:{item['key']} — {item['title']}"
        task = self.tasks.start(
            item['title'],
            item['title'],
            mode='USER',
            steps_total=1,
            priority=int(item.get('priority', 5)),
        )
        task = self.tasks.progress(task['id'], next_action=next_action)
        self.roadmap.mark_active(item['key'], task['id'])
        self.audit.write(
            'roadmap.task.selected',
            actor='projectmanager',
            result='ok',
            details={'roadmap_key': item['key'], 'task_id': task['id'], 'executor': item.get('executor')},
        )
        return {
            'key': item['key'],
            'task_id': task['id'],
            'executor': item.get('executor'),
            'next_action': next_action,
        }
