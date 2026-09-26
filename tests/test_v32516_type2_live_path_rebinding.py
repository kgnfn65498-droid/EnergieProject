from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
CP_DIR = TOOLS / 'control_plane'
for path in (str(APP), str(PM), str(TOOLS), str(CP_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

from mode_bridge import ModeBridge
from native_mcp_self_heal import NativeMcpSelfHealAuthorizer
from nas_container_cr_service import ConfiguredNasContainerCrService
from platform_test_service import ConfiguredPlatformTestService
from project_cr_service import ConfiguredProjectCrService
from protected_action_executor import ProtectedActionExecutor
from release_transition import ReleaseTransitionCoordinator
from release_controller_service import ReleaseControllerService
from release_controller import ReleaseController
from ha_runtime_marker import write_ha_runtime_marker
from process_workspace import ensure_process_workspace
from controller_lock import controller_lease
import watcher_container_contract

SCHEMA = 'energie_clearup_system_path_contract_v1'


class _Dummy:
    def pending(self):
        return []


def _activate(root: Path, key: str, destination: str) -> Path:
    dest = root / destination
    dest.parent.mkdir(parents=True, exist_ok=True)
    # File mappings need a regular destination; directory mappings need a dir.
    if dest.suffix and key not in {'release_controller', 'native_mcp_runtime', 'control_plane_runtime', 'project_cr_local', 'nas_container_cr_local', 'operating_mode'}:
        dest.write_bytes(b'')
    else:
        dest.mkdir(parents=True, exist_ok=True)
    marker = root / 'Data/03_Systeem/Projectmanager/ClearUp/PathActivation' / f'{key}.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        'schema': SCHEMA,
        'key': key,
        'active': True,
    }), encoding='utf-8')
    return dest


def test_long_lived_objects_resolve_moved_paths_after_activation(tmp_path):
    root = tmp_path / 'project'
    (root / 'Inbox/operating_mode').mkdir(parents=True)
    (root / 'Inbox/native_mcp_runtime').mkdir(parents=True)
    (root / 'Inbox/control_plane/requests').mkdir(parents=True)
    (root / 'Inbox/control_plane/results').mkdir(parents=True)
    (root / 'Inbox/project_cr_local').mkdir(parents=True)
    (root / 'Inbox/nas_container_cr_local').mkdir(parents=True)
    (root / 'Inbox/release_controller').mkdir(parents=True)
    (root / 'Inbox').mkdir(parents=True, exist_ok=True)
    for rel in ('Inbox/atomic_app_swap_state.json', 'Inbox/.release-transition.operation.lock'):
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b'')

    mode = ModeBridge(root / 'Inbox/operating_mode/operating_mode_command.json', project_root=root)
    native = NativeMcpSelfHealAuthorizer(root, _Dummy(), _Dummy())
    platform = ConfiguredPlatformTestService(root)
    project_cr = ConfiguredProjectCrService(root)
    nas_cr = ConfiguredNasContainerCrService(root)
    protected = ProtectedActionExecutor(root, _Dummy(), _Dummy(), _Dummy())
    transition = ReleaseTransitionCoordinator(root)
    controller = ReleaseControllerService(root, object())

    assert str(mode.command_path).endswith('Inbox/operating_mode/operating_mode_command.json')
    assert str(native.atomic_path).endswith('Inbox/atomic_app_swap_state.json')
    assert str(native.guard_path).endswith('Inbox/native_mcp_runtime/runtime_guard.json')
    assert str(platform.request_path).endswith('Inbox/control_plane/requests/platformtest_run.json')
    assert str(project_cr.bridge_root).endswith('Inbox/project_cr_local')
    assert str(nas_cr.bridge_root).endswith('Inbox/nas_container_cr_local')
    assert str(protected.control_plane_request_root).endswith('Inbox/control_plane/requests')
    assert str(transition.lock_path).endswith('Inbox/.release-transition.operation.lock')
    assert str(controller.store.path).endswith('Inbox/release_controller/current.json')

    _activate(root, 'operating_mode', 'Data/03_Systeem/Projectmanager/OperatingMode')
    _activate(root, 'native_mcp_runtime', 'Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP')
    _activate(root, 'control_plane_runtime', 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime')
    _activate(root, 'project_cr_local', 'Data/03_Systeem/Projectmanager/CrashRecovery/ProjectLocal')
    _activate(root, 'nas_container_cr_local', 'Data/03_Systeem/Projectmanager/CrashRecovery/NASContainerLocal')
    _activate(root, 'atomic_state', 'Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json')
    new_lock = _activate(root, 'release_transition_lock', 'Data/03_Systeem/Projectmanager/Runtime/Locks/release-transition.operation.lock')
    _activate(root, 'release_controller', 'Data/03_Systeem/Projectmanager/ReleaseController')
    _activate(root, 'ha_runtime', 'Data/03_Systeem/Projectmanager/RuntimeEvidence/HomeAssistant')
    _activate(root, 'process', 'Data/03_Systeem/Projectmanager/Runtime/Process')
    _activate(root, 'watcher_contract', 'Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_container_contract.json')
    _activate(root, 'release_controller_lock', 'Data/03_Systeem/Projectmanager/Runtime/Locks/release-controller.lock')

    assert mode.command_path == root / 'Data/03_Systeem/Projectmanager/OperatingMode/operating_mode_command.json'
    assert native.atomic_path == root / 'Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json'
    assert native.guard_path == root / 'Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP/runtime_guard.json'
    assert platform.request_path == root / 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime/requests/platformtest_run.json'
    assert project_cr.bridge_root == root / 'Data/03_Systeem/Projectmanager/CrashRecovery/ProjectLocal'
    assert nas_cr.bridge_root == root / 'Data/03_Systeem/Projectmanager/CrashRecovery/NASContainerLocal'
    assert protected.control_plane_request_root == (root / 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime/requests').resolve()
    assert transition.lock_path == new_lock
    assert controller.store.path == root / 'Data/03_Systeem/Projectmanager/ReleaseController/current.json'

    # Prove actual writers use the newly activated path, not just the properties.
    mode.request_base_mode('DEVELOPMENT')
    assert (root / 'Data/03_Systeem/Projectmanager/OperatingMode/operating_mode_command.json').is_file()
    assert not (root / 'Inbox/operating_mode/operating_mode_command.json').exists()

    state = ReleaseController().new_state(
        from_version='32.5.15', to_version='32.5.16', artifact_sha256='a' * 64, artifact_name='x.zip'
    )
    controller.store.save(state.to_dict())
    assert (root / 'Data/03_Systeem/Projectmanager/ReleaseController/current.json').is_file()
    assert not (root / 'Inbox/release_controller/current.json').exists()

    write_ha_runtime_marker(root, '32.5.16')
    assert (root / 'Data/03_Systeem/Projectmanager/RuntimeEvidence/HomeAssistant/current.json').is_file()
    assert not (root / 'Inbox/ha_runtime').exists()

    ensure_process_workspace(root)
    assert (root / 'Data/03_Systeem/Projectmanager/Runtime/Process/process_map.json').is_file()
    assert not (root / 'Inbox/process').exists()

    with controller_lease(root):
        pass
    assert (root / 'Data/03_Systeem/Projectmanager/Runtime/Locks/release-controller.lock').is_file()
    assert not (root / 'Inbox/.release-controller.lock').exists()

    result = watcher_container_contract.probe(root, socket_path=root / 'missing-docker.sock')
    assert result['status'] == 'RECREATE_REQUIRED'
    assert (root / 'Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_container_contract.json').is_file()
    assert not (root / 'Inbox/watcher_container_contract.json').exists()



def test_control_plane_uses_migrated_runtime_roots_without_recreating_inbox(tmp_path):
    import importlib.util

    module_path = ROOT / 'tools/control_plane/control_plane.py'
    spec = importlib.util.spec_from_file_location('control_plane_v32516_path_test', module_path)
    cp_module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cp_module)

    root = tmp_path / 'project'
    inbox = root / 'Inbox'
    runtime = root / 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime'
    native = root / 'Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP'
    release = root / 'Data/03_Systeem/Projectmanager/ReleaseController'
    approved = root / 'approved.json'
    evidence = root / 'Data/03_Systeem/Projectmanager/RuntimeEvidence'
    version = root / 'VERSIE.txt'
    for p in (runtime, native, release, evidence, inbox):
        p.mkdir(parents=True, exist_ok=True)
    version.write_text('32.5.16\n', encoding='utf-8')
    approved.write_text('{"items": []}\n', encoding='utf-8')
    (release / 'current.json').write_text(json.dumps({'to_version': '32.5.16'}) + '\n', encoding='utf-8')

    control = cp_module.ControlPlane(
        inbox=inbox,
        approved_queue=approved,
        version_path=version,
        runtime_evidence=evidence,
        runtime_root=runtime,
        release_controller_root=release,
        native_mcp_runtime_root=native,
        host_project_root='/share/Energie_NAS/EnergieProject',
        docker=object(),
    )

    payload = {'schema': 'energie_control_plane_result_v1', 'status': 'GREEN', 'ok': True}
    control._write_native_result(payload)
    assert (runtime / 'results/native_mcp_reload.json').is_file()
    assert not (native / 'reload_result.json').exists()
    assert not (inbox / 'native_mcp_runtime').exists()
    assert not (inbox / 'control_plane').exists()

    archive = control._stale_native_archive_root()
    assert archive == runtime / 'archive'
    assert 'Inbox/projectmanager_v2/RuntimeV2' not in archive.as_posix()


def test_control_plane_compose_needs_no_new_mount_contract_for_32516():
    compose = (ROOT / 'tools/control_plane/docker-compose.containerstation.yml').read_text(encoding='utf-8')
    assert '--runtime-root' in compose and '/control-plane-runtime' in compose
    assert '--native-mcp-runtime-root' in compose and '/native-mcp-runtime' in compose
    assert '--pm-runtime-root' not in compose
    assert 'Projectmanager/ControlPlane/Runtime:/control-plane-runtime:rw' in compose
    # Native-MCP remains read-only evidence; 32.5.16 no longer writes its result there.
    assert 'Projectmanager/RuntimeEvidence/NativeMCP:/native-mcp-runtime:ro' in compose


def test_32516_stale_control_plane_request_archives_in_migrated_control_runtime(tmp_path):
    import importlib.util

    module_path = ROOT / 'tools/control_plane/control_plane.py'
    spec = importlib.util.spec_from_file_location('control_plane_v32516_stale_archive_test', module_path)
    cp_module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(cp_module)

    root = tmp_path / 'project'
    inbox = root / 'Inbox'
    runtime = root / 'Data/03_Systeem/Projectmanager/ControlPlane/Runtime'
    release = root / 'Data/03_Systeem/Projectmanager/ReleaseController'
    native = root / 'Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP'
    evidence = root / 'Data/03_Systeem/Projectmanager/RuntimeEvidence'
    approved = root / 'approved.json'
    version = root / 'VERSIE.txt'
    for p in (inbox, runtime / 'requests', release, native, evidence):
        p.mkdir(parents=True, exist_ok=True)
    approved.write_text('{"items": []}\n', encoding='utf-8')
    version.write_text('32.5.16\n', encoding='utf-8')
    (release / 'current.json').write_text(json.dumps({'to_version': '32.5.16'}) + '\n', encoding='utf-8')
    request = {
        'schema': 'energie_control_plane_request_v1',
        'request_id': '1' * 32,
        'action': 'native_mcp_reload',
        'approved_by': 'Peter',
        'decision_id': 'stale-decision',
        'command_id': 'stale-command',
        'release_version': '32.5.15',
        'expected_fingerprint': 'a' * 64,
    }
    (runtime / 'requests/native_mcp_reload.json').write_text(json.dumps(request) + '\n', encoding='utf-8')
    plane = cp_module.ControlPlane(
        inbox=inbox,
        approved_queue=approved,
        version_path=version,
        runtime_evidence=evidence,
        runtime_root=runtime,
        release_controller_root=release,
        native_mcp_runtime_root=native,
        host_project_root='/share/Energie_NAS/EnergieProject',
        docker=object(),
    )
    assert plane.process_once() == []
    archived = list((runtime / 'archive').glob('native_mcp_reload.stale.32.5.15.*.json'))
    assert len(archived) == 1
    assert not (runtime / 'requests/native_mcp_reload.json').exists()
    assert not (inbox / 'projectmanager_v2/RuntimeV2').exists()
    assert not (inbox / 'control_plane').exists()
