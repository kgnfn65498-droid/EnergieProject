from __future__ import annotations

import importlib.util
import hashlib
import json
import os
import subprocess
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


def _git_object(kind: str, data: bytes) -> str:
    return hashlib.sha1(kind.encode() + b' ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def _write_source_manifest(workspace: Path, candidate: str | None = None) -> tuple[str, str]:
    entries = []
    for path in sorted(p for p in workspace.rglob('*') if p.is_file()):
        relative = path.relative_to(workspace).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        mode = '100755' if path.stat().st_mode & 0o111 else '100644'
        entries.append({'path': relative, 'sha256': digest, 'size': path.stat().st_size, 'mode': mode})
    canonical = json.dumps(entries, separators=(',', ':'), sort_keys=True).encode()
    source_sha256 = hashlib.sha256(canonical).hexdigest()
    tree_data = b''.join(
        item['mode'].encode() + b' ' + item['path'].encode() + b'\0' + bytes.fromhex(_git_object('blob', (workspace/item['path']).read_bytes()))
        for item in entries
    )
    tree_sha = _git_object('tree', tree_data)
    commit_data = f'tree {tree_sha}\n\nplatformtest fixture\n'.encode()
    candidate = candidate or _git_object('commit', commit_data)
    (workspace / '.energie-platformtest-source.json').write_text(json.dumps({
        'schema': 'energie_platformtest_source_v1',
        'candidate_sha': candidate,
        'source_sha256': source_sha256,
        'git_commit_hex': commit_data.hex(),
        'files': entries,
    }), encoding='utf-8')
    return candidate, source_sha256


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
    temporary = root / 'Data/03_Systeem/Projectmanager/Staging/PlatformTest/workspace'
    temporary.mkdir(parents=True)
    (temporary / 'sample.py').write_text('VALUE = 1\n', encoding='utf-8')
    candidate, source_sha256 = _write_source_manifest(temporary)
    workspace = temporary.with_name(candidate)
    temporary.rename(workspace)
    service = ConfiguredPlatformTestService(root)

    result = service.run(candidate_sha=candidate, test_profile=PROFILE)

    assert result['status'] == 'PENDING'
    request = json.loads(service.request_path.read_text(encoding='utf-8'))
    assert request == {
        'schema': 'energie_platformtest_run_request_v1',
        'request_id': result['request_id'],
        'action': 'platformtest_run',
        'candidate_sha': candidate,
        'source_sha256': source_sha256,
        'test_profile': 'publisher_full_suite_v1',
    }


def test_platformtest_service_rejects_name_only_or_mutated_workspace(tmp_path):
    root = tmp_path / 'project'
    candidate = '9' * 40
    workspace = root / 'Data/03_Systeem/Projectmanager/Staging/PlatformTest' / candidate
    workspace.mkdir(parents=True)
    source = workspace / 'sample.py'
    source.write_text('VALUE = 1\n', encoding='utf-8')
    service = ConfiguredPlatformTestService(root)

    with pytest.raises(RuntimeError, match='manifest'):
        service.run(candidate_sha=candidate)

    actual_candidate, _ = _write_source_manifest(workspace)
    actual_workspace = workspace.with_name(actual_candidate)
    workspace.rename(actual_workspace)
    service = ConfiguredPlatformTestService(root)
    source = actual_workspace / 'sample.py'
    source.write_text('VALUE = 2\n', encoding='utf-8')
    with pytest.raises(RuntimeError, match='identity'):
        service.run(candidate_sha=actual_candidate)


def test_platformtest_service_rejects_self_consistent_content_with_forged_commit_name(tmp_path):
    root = tmp_path / 'project'
    candidate = 'a' * 40
    workspace = root / 'Data/03_Systeem/Projectmanager/Staging/PlatformTest' / candidate
    workspace.mkdir(parents=True)
    (workspace / 'sample.py').write_text('VALUE = 1\n', encoding='utf-8')
    _write_source_manifest(workspace, candidate)
    service = ConfiguredPlatformTestService(root)
    with pytest.raises(RuntimeError, match='git commit'):
        service.run(candidate_sha=candidate)


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
        'source_sha256': '4' * 64,
        'test_profile': cp.PLATFORMTEST_PROFILE,
    }
    payload = cp.platformtest_create_payload(
        '/share/Energie_NAS/EnergieProject', request, image_id='sha256:' + ('5' * 64),
    )

    assert payload['Image'] == 'sha256:' + ('5' * 64)
    assert payload['Cmd'][0:2] == ['python3', '-c']
    assert 'pytest.main' in payload['Cmd'][2]
    assert payload['WorkingDir'] == '/workspace'
    assert payload['Env'] == [
        'PYTHONPATH=/workspace',
        'ENERGIE_CANDIDATE_SHA=' + ('c' * 40),
        'ENERGIE_SOURCE_SHA256=' + ('4' * 64),
    ]
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
        'source_sha256': '6' * 64,
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
        self.create_calls = 0

    def ping(self):
        return {'ok': True}

    def inspect_image(self, image):
        assert image == 'energie-filesystem-mcp:runtime-v1'
        return {'Id': 'sha256:' + ('7' * 64)}

    def inspect_container(self, name):
        if self.created is None:
            return None
        if self.removed:
            return None
        labels = self.created[1].get('Labels', {}) if isinstance(self.created[1], dict) else {}
        return {
            'State': {'Running': False, 'ExitCode': self.exit_code},
            'Config': {'Labels': labels},
        }

    def create_container(self, name, payload):
        self.create_calls += 1
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
        'source_sha256': '8' * 64,
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
    assert result['image_id'] == 'sha256:' + ('7' * 64)
    assert result['source_sha256'] == '8' * 64
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
    assert cp.terminal_result(inbox / 'control_plane/results/platformtest_run.json', cp.load_platformtest_request(inbox)) is True


def test_platformtest_terminal_result_rejects_incomplete_forged_green(tmp_path):
    cp = _load_control_plane()
    path = tmp_path / 'result.json'
    request = {
        'request_id': '3' * 32, 'candidate_sha': 'e' * 40,
        'source_sha256': '8' * 64, 'test_profile': cp.PLATFORMTEST_PROFILE,
    }
    path.write_text(json.dumps({'request_id': '3' * 32, 'status': 'GREEN'}), encoding='utf-8')
    assert cp.terminal_result(path, request) is False


def test_platformtest_retry_reconciles_exact_stopped_container(tmp_path):
    docker = _FakeDocker()
    cp, plane, inbox = _plane(tmp_path, docker)
    request = cp.load_platformtest_request(inbox)
    image_id = 'sha256:' + ('7' * 64)
    attempt = {
        'schema': 'energie_platformtest_attempt_v1', 'status': 'RUNNING',
        'request_id': request['request_id'], 'candidate_sha': request['candidate_sha'],
        'source_sha256': request['source_sha256'], 'test_profile': request['test_profile'],
        'image_id': image_id,
    }
    attempt_path = inbox / 'control_plane/results/platformtest_attempt.json'
    attempt_path.parent.mkdir(parents=True, exist_ok=True)
    attempt_path.write_text(json.dumps(attempt), encoding='utf-8')
    docker.created = (
        'energie-platformtest-' + request['request_id'][:12],
        {'Labels': {'com.energie.request_id': request['request_id'], 'com.energie.source_sha256': request['source_sha256']}},
    )

    result = plane.run_platformtest()

    assert result['status'] == 'GREEN'
    assert docker.create_calls == 0
    assert docker.started is False
    assert docker.removed is True


def test_processor_and_orchestrator_wire_platformtest_service():
    processor = (PM / 'command_processor.py').read_text(encoding='utf-8')
    orchestrator = (PM / 'orchestrator.py').read_text(encoding='utf-8')
    ingress = (PM / 'command_ingress.py').read_text(encoding='utf-8')

    assert "elif action == 'platformtest_run':" in processor
    assert 'platform_test_service.run(' in processor
    assert 'ConfiguredPlatformTestService(config.project_root)' in orchestrator
    assert "'candidate_sha', 'test_profile'" in ingress


def test_platformtest_mailboxes_are_not_world_read_write(tmp_path):
    qnap = _load_control_plane()
    bootstrap_path = CP / 'qnap_control_plane_bootstrap.py'
    spec = importlib.util.spec_from_file_location('platformtest_qnap_bootstrap', bootstrap_path)
    assert spec and spec.loader
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)
    result = bootstrap._ensure_control_plane_mailboxes(tmp_path / 'Inbox')
    assert result['root_mode'] == '0755'
    assert result['requests_mode'] == '1733'
    assert result['results_mode'] == '0755'
    assert oct((tmp_path / 'Inbox/control_plane').stat().st_mode & 0o7777) == '0o755'
    assert oct((tmp_path / 'Inbox/control_plane/requests').stat().st_mode & 0o7777) == '0o1733'
    assert oct((tmp_path / 'Inbox/control_plane/results').stat().st_mode & 0o7777) == '0o755'


def test_platformtest_bootstrap_retires_legacy_world_writable_evidence(tmp_path):
    inbox = tmp_path / 'Inbox'
    root = inbox / 'control_plane'
    requests = root / 'requests'
    results = root / 'results'
    requests.mkdir(parents=True)
    results.mkdir()
    root.chmod(0o777); requests.chmod(0o777); results.chmod(0o777)
    forged = results / 'platformtest_run.json'
    forged.write_text('{"status":"GREEN"}\n', encoding='utf-8')
    forged.chmod(0o666)
    bootstrap_path = CP / 'qnap_control_plane_bootstrap.py'
    spec = importlib.util.spec_from_file_location('platformtest_qnap_bootstrap_legacy', bootstrap_path)
    assert spec and spec.loader
    bootstrap = importlib.util.module_from_spec(spec); spec.loader.exec_module(bootstrap)

    result = bootstrap._ensure_control_plane_mailboxes(inbox)

    assert not forged.exists()
    assert result['legacy_platformtest_evidence_retired'] is True


def test_platformtest_bootstrap_retires_forged_result_after_intermediate_0755_upgrade(tmp_path):
    inbox = tmp_path / 'Inbox'
    root = inbox / 'control_plane'; requests = root / 'requests'; results = root / 'results'
    requests.mkdir(parents=True); results.mkdir()
    root.chmod(0o755); requests.chmod(0o1733); results.chmod(0o755)
    forged = results / 'platformtest_run.json'
    forged.write_text('{"status":"GREEN"}\n', encoding='utf-8'); forged.chmod(0o666)
    bootstrap_path = CP / 'qnap_control_plane_bootstrap.py'
    spec = importlib.util.spec_from_file_location('platformtest_qnap_bootstrap_intermediate', bootstrap_path)
    assert spec and spec.loader
    bootstrap = importlib.util.module_from_spec(spec); spec.loader.exec_module(bootstrap)

    result = bootstrap._ensure_control_plane_mailboxes(inbox)

    assert not forged.exists()
    assert result['legacy_platformtest_evidence_retired'] is True


def test_platformtest_secure_terminal_result_survives_same_fingerprint_restart(tmp_path):
    inbox = tmp_path / 'Inbox'
    bootstrap_path = CP / 'qnap_control_plane_bootstrap.py'
    spec = importlib.util.spec_from_file_location('platformtest_qnap_bootstrap_durable', bootstrap_path)
    assert spec and spec.loader
    bootstrap = importlib.util.module_from_spec(spec); spec.loader.exec_module(bootstrap)
    bootstrap._ensure_control_plane_mailboxes(inbox)
    result_path = inbox / 'control_plane/results/platformtest_run.json'
    result_path.write_text('{"status":"GREEN","secure":true}\n', encoding='utf-8')
    result_path.chmod(0o600)

    second = bootstrap._ensure_control_plane_mailboxes(inbox)

    assert json.loads(result_path.read_text())['secure'] is True
    assert second['legacy_platformtest_evidence_retired'] is False


def test_platformtest_atomic_write_does_not_use_predictable_pid_temp(tmp_path, monkeypatch):
    service = ConfiguredPlatformTestService(tmp_path / 'project')
    target = tmp_path / 'result.json'
    predictable = target.with_name(target.name + f'.tmp-{os.getpid()}')
    predictable.symlink_to(tmp_path / 'victim')
    service._atomic(target, {'ok': True})
    assert json.loads(target.read_text()) == {'ok': True}
    assert predictable.is_symlink()


def test_platformtest_workspace_builder_binds_exact_git_commit_and_tree(tmp_path):
    repo = tmp_path / 'repo'; repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.name', 'Test'], check=True)
    subprocess.run(['git', '-C', str(repo), 'config', 'user.email', 'test@example.invalid'], check=True)
    (repo / 'nested').mkdir(); (repo / 'nested/module.py').write_text('VALUE = 1\n', encoding='utf-8')
    script = repo / 'run.sh'; script.write_text('#!/bin/sh\nexit 0\n', encoding='utf-8'); script.chmod(0o755)
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(repo), 'commit', '-qm', 'fixture'], check=True)
    module_path = ROOT / 'tools/prepare_platformtest_workspace.py'
    spec = importlib.util.spec_from_file_location('prepare_platformtest_workspace_test', module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)

    project = tmp_path / 'project'
    target_root = project / 'Data/03_Systeem/Projectmanager/Staging/PlatformTest'
    result = module.prepare(repo, target_root)
    service = ConfiguredPlatformTestService(project)

    request = service.run(candidate_sha=result['candidate_sha'])
    assert request['source_sha256'] == result['source_sha256']
