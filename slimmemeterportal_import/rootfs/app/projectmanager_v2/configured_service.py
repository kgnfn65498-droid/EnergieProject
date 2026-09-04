from manager_service import ManagerService
from runtime_sources import RuntimeCollector


class ConfiguredManagerService(ManagerService):
    """ManagerService wired to the explicitly mounted canonical mode-state path."""
    def __init__(self, config, **kwargs):
        runtime_collector=kwargs.pop('runtime_collector', None)
        super().__init__(config, runtime_collector=runtime_collector, **kwargs)
        if runtime_collector is None:
            self.runtime_collector=RuntimeCollector(
                config.project_root,
                mode_state_path=getattr(config,'mode_state_path','') or None,
            )
