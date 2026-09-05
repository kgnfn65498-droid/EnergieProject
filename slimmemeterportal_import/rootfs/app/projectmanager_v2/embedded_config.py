from pathlib import Path

from manager_config import ManagerConfig


def build_embedded_config(project_root, manager_app_root, *, supervisor_token=''):
    root = Path(project_root)
    return ManagerConfig(
        project_root=str(root),
        system_root=str(root / 'Inbox/projectmanager_v2/RuntimeV2'),
        input_root=str(root / 'Data/01_Input'),
        recovery_root=str(root / 'Backups'),
        reports_root=str(root / 'Data/02_Output/Rapportages'),
        interval_seconds=300,
        timezone='Europe/Amsterdam',
        ha_base_url='http://supervisor/core',
        ha_token=supervisor_token or '',
        ha_notify_service='',
        market_enabled=True,
        mode_state_path=str(root / 'Inbox/operating_mode/operating_mode_state.json'),
        mode_command_path=str(root / 'Inbox/operating_mode/operating_mode_command.json'),
        manager_app_root=str(Path(manager_app_root)),
        command_ingress_root=str(root / 'Data/03_Systeem/Projectmanager/CommandIngress'),
        approval_ingress_root=str(root / 'Inbox/projectmanager_v2/ApprovalIngress'),
        handoff_result_ingress_root=str(root / 'Data/03_Systeem/Projectmanager/HandoffResultIngress'),
        canonical_roadmap_path=str(root / 'Data/03_Systeem/Projectmanager/Roadmap/canonical_roadmap_v3.json'),
        nas_docker_tls_root='/data/projectmanager_v2/docker_tls',
    )
