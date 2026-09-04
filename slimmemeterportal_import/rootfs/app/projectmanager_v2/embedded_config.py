from pathlib import Path
from manager_config import ManagerConfig


def build_embedded_config(project_root, manager_app_root, *, supervisor_token=''):
    root=Path(project_root)
    return ManagerConfig(
        project_root=str(root),
        system_root=str(root/'Data/03_Systeem/Projectmanager/RuntimeV2'),
        input_root=str(root/'Data/01_Input'),
        recovery_root=str(root/'Backups'),
        reports_root=str(root/'Data/02_Output/Rapportages'),
        interval_seconds=300,
        timezone='Europe/Amsterdam',
        ha_base_url='http://supervisor/core',
        ha_token=supervisor_token or '',
        ha_notify_service='',
        market_enabled=True,
        mode_state_path=str(root/'Inbox/operating_mode/operating_mode_state.json'),
        mode_command_path=str(root/'Inbox/operating_mode/operating_mode_command.json'),
        manager_app_root=str(Path(manager_app_root)),
    )
