from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))


class FakeCrService:
    def __init__(self):
        self.calls = 0
    def create(self):
        self.calls += 1
        return {
            'ok': True,
            'status': 'GREEN',
            'backup_dir': '/project/Backups/NAS Container',
            'zip': '/project/Backups/NAS Container/new.zip',
            'production_containers_changed': False,
        }


def test_command_processor_runs_nas_cr_once_and_records_visible_path(tmp_path):
    from audit_log import AuditLog
    from command_processor import CommandProcessor
    from command_store import CommandStore
    from decision_queue import DecisionQueue
    from operating_mode import ModeStore
    from task_engine import TaskStore

    commands = CommandStore(tmp_path / 'commands.json')
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    mode = ModeStore(tmp_path / 'mode.json')
    tasks = TaskStore(tmp_path / 'tasks.json')
    audit = AuditLog(tmp_path / 'audit.jsonl')
    service = FakeCrService()
    commands.enqueue({'intent': 'nas_container_cr_create', 'source': 'mcp_remote'})

    processor = CommandProcessor(
        commands, decisions, mode, tasks,
        audit=audit,
        nas_container_cr_service=service,
    )
    result = processor.process_next()

    assert service.calls == 1
    assert result['status'] == 'DONE'
    assert result['result']['ok'] is True
    assert result['result']['backup_dir'].endswith('Backups/NAS Container')
    assert result['result']['production_containers_changed'] is False


def test_configured_service_uses_fixed_local_bridge_and_fails_closed_without_executor(tmp_path):
    from nas_container_cr_service import ConfiguredNasContainerCrService
    import pytest

    project = tmp_path / 'EnergieProject'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.36\n', encoding='utf-8')
    service = ConfiguredNasContainerCrService(project, timeout_seconds=0.1, poll_seconds=0.01)
    with pytest.raises(RuntimeError, match='timeout'):
        service.create()
    request = project / 'Inbox/nas_container_cr_local/request.json'
    assert request.is_file()
    assert 'nas_container_cr_create' in request.read_text(encoding='utf-8')


def test_embedded_config_legacy_tls_value_is_not_active_nas_cr_dependency(tmp_path):
    from embedded_config import build_embedded_config
    import inspect
    from orchestrator import ProjectmanagerRuntime

    config = build_embedded_config(tmp_path / 'EnergieProject', PM)
    assert 'nas_docker_tls_root' not in config.public_dict()
    source = inspect.getsource(ProjectmanagerRuntime.__init__)
    assert 'nas_docker_tls_root' not in source


def test_runtime_constructor_supports_injected_nas_cr_service():
    import inspect
    from orchestrator import ProjectmanagerRuntime

    assert 'nas_container_cr_service' in inspect.signature(ProjectmanagerRuntime.__init__).parameters
