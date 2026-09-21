from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
CP = ROOT / 'tools/control_plane'
for path in (str(PM), str(CP)):
    if path not in sys.path:
        sys.path.insert(0, path)

from command_gateway import plan_command
from platform_test_service import ConfiguredPlatformTestService, PROFILE


def _load_control_plane():
    spec = importlib.util.spec_from_file_location('platformtest_control_plane', CP / 'control_plane.py')
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_platformtest_gateway_is_safe_nonapproval_action():
    plan = plan_command({'intent': 'platformtest_run', 'source': 'mcp_remote'})
    assert plan['action'] == 'platformtest_run'
    assert plan['allowed_without_approval'] is True


def test_platformtest_service_materializes_only_exact_request(tmp_path):
    root = tmp_path / 'project'
    candidate = 'a' * 40
    workspace = root / 'Data/03_Systeem/Projectmanager/Staging/PlatformTest' / candidate
    workspace.mkdir(parents=True)
    service = ConfiguredPlatformTestService(root)

    result = service.run(candidate_sha=candidate, test_profile=PROFILE)

    assert result['status'] == 'PENDING'
    request = json.loads(service.request_path.read_text(encoding='utf-8'))
    assert request == {
        'schema': 'energie_platformtest_run_request_v1',
        'request_id': result['request_id'],
        'action': 'platformtest_run',
        'candidate_sha': candidate,
        'test_profile': 'publisher_full_suite_v1',
    }


def test_platformtest_service_fails_closed_on_bad_identity(tmp_path):
    service = ConfiguredPlatformTestService(tmp_path / 'project')
    with pytest.raises(RuntimeError, match='candidate_sha'):
        service.run(candidate_sha='not-a-sha')
    with pytest.raises(RuntimeError, match='test_profile'):
        service.run(candidate_sha='b' * 40, test_profile='arbitrary-shell')


def test_platformtest_payload_is_fixed_network_none_and_read_only():
    cp = _load_control_plane()
    request = {
        'schema': cp.PLATFORMTEST_REQUEST_SCHEMA,
        'request_id': '1' * 32,
        'action': 'platformtest_run',
        'candidate_sha': 'c' * 40,
        'test_profile': cp.PLATFORMTEST_PROFILE,
    }
    payload = cp.platformtest_create_payload('/share/Energie_NAS/EnergieProject', request)

    assert payload['Image'] == 'energie-filesystem-mcp:runtime-v1'
    assert payload['Cmd'] == ['python3', '-m', 'pytest', '-q', '-p', 'no:cacheprovider']
    assert payload['WorkingDir'] == '/workspace'
    host = payload['HostConfig']
    assert host['NetworkMode'] == 'none'
    assert host['ReadonlyRootfs'] is True
    assert host['CapDrop'] == ['ALL']
    assert host['SecurityOpt'] == ['no-new-privileges']
    assert host['Binds'] == [
        '/share/Energie_NAS/EnergieProject/Data/03_Systeem/Projectmanager/Staging/PlatformTest/'
        + ('c' * 40) + ':/workspace:ro'
    ]


def test_platformtest_request_rejects_extra_fields(tmp_path):
    cp = _load_control_plane()
    inbox = tmp_path / 'Inbox'
    path = inbox / 'control_plane/requests/platformtest_run.json'
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        'schema': cp.PLATFORMTEST_REQUEST_SCHEMA,
        'request_id': '2' * 32,
        'action': 'platformtest_run',
        'candidate_sha': 'd' * 40,
        'test_profile': cp.PLATFORMTEST_PROFILE,
        'command': 'rm -rf /',
    }), encoding='utf-8')
    with pytest.raises(RuntimeError, match='onbekende/ontbrekende'):
        cp.load_platformtest_request(inbox)


class _FakeDocker:
    def __init__(self, *, exit_code=0, logs='12 passed, 2 skipped in 1.00s'):
        self.exit_code = exit_code
        self.logs = logs
        self.created = None
        self.started = False
        self.removed = False

    def ping(self):
        return {'ok': True}

    def inspect_image(self, image):
        assert image == 'energie-filesystem-mcp:runtime-v1'
        return {'Id': 'local-image'}

    def inspect_container(self, name):
        if self.created is None:
            return None
        if self.removed:
            return None
        return {'State': {'Running': False, 'ExitCode': self.exit_code}}

    def create_container(self, name, payload):
        self.created = (name, payload)
        return {'Id': 'test'}

    def start_container(self, name):
        self.started = True
        return {'ok': True}

    def container_logs(self, name):
        return self.logs

    def remove_container(self, name, *, force=True):
        self.removed = True
        return {'ok': True}


def _plane(tmp_path, docker):
    cp = _load_control_plane()
    inbox = tmp_path / 'Inbox'
    approved = tmp_path / 'approved.json'
    approved.write_text('{"items": []}\n', encoding='utf-8')
    version = tmp_path / 'VERSIE.txt'
    version.write_text('32.4.59\n', encoding='utf-8')
    evidence = tmp_path / 'evidence'
    evidence.mkdir()
    request = inbox / 'control_plane/requests/platformtest_run.json'
    request.parent.mkdir(parents=True)
    request.write_text(json.dumps({
        'schema': cp.PLATFORMTEST_REQUEST_SCHEMA,
        'request_id': '3' * 32,
        'action': 'platformtest_run',
        'candidate_sha': 'e' * 40,
        'test_profile': cp.PLATFORMTEST_PROFILE,
    }), encoding='utf-8')
    plane = cp.ControlPlane(
        inbox=inbox,
        approved_queue=approved,
        version_path=version,
        runtime_evidence=evidence,
        host_project_root='/share/Energie_NAS/EnergieProject',
        docker=docker,
    )
    return cp, plane, inbox


def test_platformtest_executor_returns_green_and_removes_container(tmp_path):
    docker = _FakeDocker()
    cp, plane, inbox = _plane(tmp_path, docker)

    result = plane.run_platformtest()

    assert result['status'] == 'GREEN'
    assert result['ok'] is True
    assert result['exit_code'] == 0
    assert result['network_mode'] == 'none'
    assert result['production_modified'] is False
    assert result['container_removed'] is True
    assert result['test_counts']['passed'] == 12
    assert result['test_counts']['skipped'] == 2
    assert docker.started is True and docker.removed is True
    persisted = json.loads((inbox / 'control_plane/results/platformtest_run.json').read_text())
    assert persisted['request_id'] == '3' * 32


def test_platformtest_executor_nonzero_is_terminal_red(tmp_path):
    docker = _FakeDocker(exit_code=1, logs='1 failed, 11 passed in 1.00s')
    cp, plane, inbox = _plane(tmp_path, docker)

    result = plane.run_platformtest()

    assert result['status'] == 'RED'
    assert result['ok'] is False
    assert result['exit_code'] == 1
    assert result['test_counts']['failed'] == 1
    assert result['test_counts']['passed'] == 11
    assert docker.removed is True
    assert cp.terminal_result(inbox / 'control_plane/results/platformtest_run.json', '3' * 32) is True


def test_processor_and_orchestrator_wire_platformtest_service():
    processor = (PM / 'command_processor.py').read_text(encoding='utf-8')
    orchestrator = (PM / 'orchestrator.py').read_text(encoding='utf-8')
    ingress = (PM / 'command_ingress.py').read_text(encoding='utf-8')

    assert "elif action == 'platformtest_run':" in processor
    assert 'platform_test_service.run(' in processor
    assert 'ConfiguredPlatformTestService(config.project_root)' in orchestrator
    assert "'candidate_sha', 'test_profile'" in ingress
