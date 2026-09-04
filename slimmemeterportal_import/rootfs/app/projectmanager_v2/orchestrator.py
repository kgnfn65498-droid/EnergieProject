from pathlib import Path

from command_processor import CommandProcessor
from command_store import CommandStore
from configured_service import ConfiguredManagerService
from handover import build_handover
from mode_bridge import ModeBridge
from persistence import atomic_write_json


def _read_manager_version(app_root) -> str:
    path=Path(app_root or '.')/'VERSION.txt'
    try:
        return path.read_text(encoding='utf-8').strip() or 'NOG_TE_CONTROLEREN'
    except OSError:
        return 'NOG_TE_CONTROLEREN'


class ProjectmanagerRuntime:
    def __init__(self, config, *, base_service=None):
        self.config=config
        self.base=base_service or ConfiguredManagerService(config)
        root=Path(config.system_root)
        self.root=root
        self.commands=CommandStore(root/'commands'/'queue.json')
        mode_bridge=ModeBridge(config.mode_command_path) if getattr(config,'mode_command_path','') else None
        self.processor=CommandProcessor(
            self.commands,
            self.base.decisions,
            self.base.mode,
            self.base.tasks,
            audit=self.base.audit,
            mode_bridge=mode_bridge,
        )

    def run_once(self, *, now=None):
        status=dict(self.base.run_once(now=now))
        processed=self.processor.process_all(max_items=50)
        status['manager']={'version':_read_manager_version(getattr(self.config,'manager_app_root',''))}
        status['processed_commands']=len(processed)
        if processed:
            status['command_results']=processed[-10:]
        self._refresh_coordination(status)
        return status

    def _refresh_coordination(self, status: dict):
        active=self.base.tasks.active()
        decisions=self.base.decisions.pending()
        status['active_task']=active
        status['decisions_needed']=decisions
        status['needs_human']=bool(decisions)
        status['next_action']=(active or {}).get('next_action')
        status['pending_commands']=self.commands.pending_count()
        atomic_write_json(self.root/'status'/'current.json',status)
        handover=build_handover(
            mode=self.base.mode.get(),
            active_task=active,
            release=status.get('release') or {},
            decisions=decisions,
            evidence=(status.get('health') or {}).get('checks',[]),
            last_changes=[f"command:{item.get('intent')}:{item.get('status')}" for item in status.get('command_results',[])],
        )
        handover['manager']=status.get('manager',{})
        atomic_write_json(self.root/'handover'/'current.json',handover)
