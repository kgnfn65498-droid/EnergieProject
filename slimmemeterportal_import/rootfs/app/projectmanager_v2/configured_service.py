import json
from pathlib import Path

from approved_action_store import ApprovedActionStore
from canonical_roadmap_migration import migrate_canonical_roadmap
from command_store import CommandStore
from handoff_queue import HandoffQueue
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
                running_release_version=getattr(config, 'running_release_version', '') or None,
            )
        self._coordination_commands = CommandStore(self.root / 'commands' / 'queue.json')
        self._coordination_actions = ApprovedActionStore(self.root / 'approved_actions' / 'queue.json')
        self.handoffs = HandoffQueue(self.root / 'handoffs' / 'queue.json')
        self._canonical_roadmap_path = Path(getattr(config, 'canonical_roadmap_path', '') or '') if getattr(config, 'canonical_roadmap_path', '') else None

    def _load_canonical_roadmap(self):
        if self._canonical_roadmap_path is None or not self._canonical_roadmap_path.is_file():
            return None
        migration = migrate_canonical_roadmap(self._canonical_roadmap_path)
        if migration.get('status') in {'invalid', 'unsupported'}:
            return None
        if migration.get('status') == 'migrated_read_only' and isinstance(migration.get('spec'), dict):
            return migration['spec']
        try:
            value = json.loads(self._canonical_roadmap_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

    def _reconcile_canonical_roadmap(self):
        spec = self._load_canonical_roadmap()
        if spec is None:
            self.issues.open(
                'roadmap:canonical_missing',
                severity='RED',
                title='Canonieke Projectmanager-roadmap ontbreekt of is ongeldig',
                details={'path': str(self._canonical_roadmap_path or '')},
            )
            return {'ok': False, 'reason': 'canonical_roadmap_missing'}
        result = self.roadmap.reconcile_canonical(spec, source_path=str(self._canonical_roadmap_path))
        self.issues.resolve_fingerprint('roadmap:canonical_missing', resolution='canonical roadmap loaded and reconciled')
        for item in result.get('deactivated', []):
            task_id = item.get('task_id')
            if not task_id:
                continue
            try:
                self.tasks.pause(task_id, item.get('reason') or 'canonical roadmap reprioritized')
            except KeyError:
                pass
            self.handoffs.cancel_for_task(task_id, reason=item.get('reason') or 'canonical roadmap reprioritized')
            self.roadmap.reopen_for_task(task_id, reason=item.get('reason') or 'canonical roadmap reprioritized')
            self.audit.write(
                'roadmap.task.deactivated',
                actor='projectmanager',
                result='safe',
                details=item,
            )
        return {'ok': True, **result}

    def _maybe_select_roadmap_task(self, health: dict, pending_decisions: list):
        reconciliation = self._reconcile_canonical_roadmap()
        if reconciliation.get('ok') is not True:
            return None
        if self.tasks.active() is not None or pending_decisions:
            return None
        if health.get('status') == 'RED':
            return None
        current_mode = self.mode.get().get('mode')
        if current_mode not in {'USER', 'DEVELOPMENT'}:
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

        item = self.roadmap.next_open(mode=current_mode)
        if not item:
            backlog = self.tasks.next_captured(mode=current_mode)
            if not backlog:
                return None
            resumed = self.tasks.resume_captured(
                backlog['id'], reason='autonomous safe conversation backlog selection'
            )
            self.audit.write(
                'conversation_backlog.task.selected',
                actor='projectmanager',
                result='ok',
                details={'task_id': resumed['id'], 'mode': current_mode},
            )
            return {
                'task_id': resumed['id'],
                'source': 'conversation_backlog',
                'next_action': resumed.get('next_action', ''),
                'canonical': reconciliation.get('canonical', {}),
            }
        next_action = f"handoff:{item['key']} — {item['title']}"
        task = self.tasks.start(
            item['title'],
            item['title'],
            mode=current_mode,
            steps_total=1,
            priority=int(item.get('priority', 5)),
        )
        task = self.tasks.progress(task['id'], next_action=next_action)
        active_item = self.roadmap.mark_active(item['key'], task['id'])
        handoff = None
        if item.get('executor') == 'handoff':
            handoff = self.handoffs.ensure_for_task(task, active_item)
        self.audit.write(
            'roadmap.task.selected',
            actor='projectmanager',
            result='ok',
            details={
                'roadmap_key': item['key'],
                'task_id': task['id'],
                'executor': item.get('executor'),
                'handoff_id': (handoff or {}).get('id'),
            },
        )
        return {
            'key': item['key'],
            'task_id': task['id'],
            'executor': item.get('executor'),
            'handoff_id': (handoff or {}).get('id'),
            'next_action': next_action,
            'canonical': reconciliation.get('canonical', {}),
        }
