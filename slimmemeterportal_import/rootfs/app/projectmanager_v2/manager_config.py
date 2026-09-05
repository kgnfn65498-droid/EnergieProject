import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {'1', 'true', 'yes', 'on'}


@dataclass(frozen=True)
class ManagerConfig:
    project_root: str
    system_root: str
    input_root: str
    recovery_root: str
    reports_root: str
    interval_seconds: int
    timezone: str
    ha_base_url: str
    ha_token: str
    ha_notify_service: str
    market_enabled: bool = False
    mode_state_path: str = ''
    mode_command_path: str = ''
    manager_app_root: str = ''
    command_ingress_root: str = ''
    approval_ingress_root: str = ''
    handoff_result_ingress_root: str = ''
    canonical_roadmap_path: str = ''
    nas_docker_tls_root: str = '/data/projectmanager_v2/docker_tls'

    @classmethod
    def from_env(cls):
        project_root = os.getenv('PM_PROJECT_ROOT', '/project')
        return cls(
            project_root=project_root,
            system_root=os.getenv('PM_SYSTEM_ROOT', '/system/Projectmanager/RuntimeV2'),
            input_root=os.getenv('PM_INPUT_ROOT', '/input'),
            recovery_root=os.getenv('PM_RECOVERY_ROOT', '/recovery'),
            reports_root=os.getenv('PM_REPORTS_ROOT', '/reports'),
            interval_seconds=max(60, int(os.getenv('PM_INTERVAL_SECONDS', '300'))),
            timezone=os.getenv('PM_TIMEZONE', 'Europe/Amsterdam'),
            ha_base_url=os.getenv('HOME_ASSISTANT_URL', os.getenv('HA_BASE_URL', '')),
            ha_token=os.getenv('HOME_ASSISTANT_TOKEN', os.getenv('HA_TOKEN', '')),
            ha_notify_service=os.getenv('PM_HA_NOTIFY_SERVICE', ''),
            market_enabled=_env_bool('PM_MARKET_ENABLED', False),
            mode_state_path=os.getenv('PM_MODE_STATE_PATH', f'{project_root}/Inbox/operating_mode/operating_mode_state.json'),
            mode_command_path=os.getenv('PM_MODE_COMMAND_PATH', ''),
            manager_app_root=os.getenv('PM_APP_ROOT', os.getcwd()),
            command_ingress_root=os.getenv('PM_COMMAND_INGRESS_ROOT', ''),
            approval_ingress_root=os.getenv('PM_APPROVAL_INGRESS_ROOT', ''),
            handoff_result_ingress_root=os.getenv('PM_HANDOFF_RESULT_INGRESS_ROOT', ''),
            canonical_roadmap_path=os.getenv('PM_CANONICAL_ROADMAP_PATH', ''),
            nas_docker_tls_root=os.getenv('PM_NAS_DOCKER_TLS_ROOT', '/data/projectmanager_v2/docker_tls'),
        )

    def public_dict(self):
        return {
            'project_root': self.project_root,
            'system_root': self.system_root,
            'input_root': self.input_root,
            'recovery_root': self.recovery_root,
            'reports_root': self.reports_root,
            'interval_seconds': self.interval_seconds,
            'timezone': self.timezone,
            'ha_base_url': self.ha_base_url,
            'ha_notify_service': self.ha_notify_service,
            'market_enabled': self.market_enabled,
            'mode_state_path': self.mode_state_path,
            'mode_command_path': self.mode_command_path,
            'manager_app_root': self.manager_app_root,
            'command_ingress_root': self.command_ingress_root,
            'approval_ingress_root': self.approval_ingress_root,
            'handoff_result_ingress_root': self.handoff_result_ingress_root,
            'canonical_roadmap_path': self.canonical_roadmap_path,
        }
