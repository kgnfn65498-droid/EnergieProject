import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
TOOLS = ROOT / 'tools'

import sys
for path in (str(PM), str(TOOLS)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _write(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, str):
        path.write_text(payload, encoding='utf-8')
    else:
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _runtime_module_from_template(tmp_path: Path):
    import native_mcp_runtime_contract_hotfix as hotfix
    path = tmp_path / 'runtime_fingerprint.py'
    path.write_text(hotfix.RUNTIME_MODULE, encoding='utf-8')
    spec = importlib.util.spec_from_file_location('runtime_fingerprint_32445_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_32445_native_fingerprint_ignores_unloaded_projectmanager_sources(tmp_path):
    module = _runtime_module_from_template(tmp_path)
    native = tmp_path / 'native'
    project = tmp_path / 'project'
    native.mkdir()
    pm = project / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2'
    pm.mkdir(parents=True)

    for name in ('runtime_fingerprint.py', 'server.py', 'registry.py', 'tools_projectmanager.py', 'crash_recovery.py', 'tools_recovery.py'):
        (native / name).write_text(f'{name}:native-v1\n', encoding='utf-8')
    for name in ('command_gateway.py', 'projectmanager_api.py', 'secret_guard.py'):
        (pm / name).write_text(f'{name}:pm-v1\n', encoding='utf-8')

    first, targets = module.compute_fingerprint(native_root=native, project_root=project)
    (pm / 'command_gateway.py').write_text('pm-only-release-change\n', encoding='utf-8')
    second, targets_after = module.compute_fingerprint(native_root=native, project_root=project)

    assert first == second
    assert targets == targets_after
    assert targets == [
        'native:runtime_fingerprint.py', 'native:server.py', 'native:registry.py',
        'native:tools_projectmanager.py', 'native:crash_recovery.py', 'native:tools_recovery.py',
    ]
    assert module.SCHEMA == 'energie_native_mcp_runtime_v3'


def test_32445_native_fingerprint_still_changes_for_loaded_native_source(tmp_path):
    module = _runtime_module_from_template(tmp_path)
    native = tmp_path / 'native'
    project = tmp_path / 'project'
    native.mkdir()
    (project / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2').mkdir(parents=True)
    for name in ('runtime_fingerprint.py', 'server.py', 'registry.py', 'tools_projectmanager.py', 'crash_recovery.py', 'tools_recovery.py'):
        (native / name).write_text(f'{name}:native-v1\n', encoding='utf-8')

    first, _ = module.compute_fingerprint(native_root=native, project_root=project)
    (native / 'server.py').write_text('server:native-v2\n', encoding='utf-8')
    second, _ = module.compute_fingerprint(native_root=native, project_root=project)
    assert first != second


def test_32445_final_coordination_is_not_invalidated_only_by_wall_clock_skew(tmp_path):
    from self_audit import SelfAuditor

    root = tmp_path / 'RuntimeV2'
    generation = 'gen-32445'
    stale = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    release = '32.4.45'

    status = {
        'mode': 'MAINTENANCE',
        'health': {'status': 'GREEN'},
        'updated_at': stale,
        'release': {'version': release, 'ha_runtime_version': release, 'active_verified': True},
        'cycle_generation': generation,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
        'manager': {'version': '2.0.0-rc32'},
        'conversation_intake': {}, 'canonical_roadmap': {}, 'state_reconciliation': {},
        'open_issues': [], 'progress': {}, 'acceptance_matrix': {},
        'development_efficiency': {}, 'development_context': {},
        'pending_commands': 0, 'handoffs': [], 'active_task': {},
    }
    heartbeat = {
        'mode': 'MAINTENANCE', 'health': 'GREEN', 'heartbeat_at': stale,
        'cycle_generation': generation,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
    }
    handover = {
        'mode': 'MAINTENANCE', 'release': {'version': release},
        'cycle_generation': generation,
        'provenance': {'generation': generation, 'phase': 'FINAL'},
        'manager': {'version': '2.0.0-rc32'},
        'conversation_intake': {}, 'canonical_roadmap': {}, 'state_reconciliation': {},
        'progress': {}, 'acceptance_matrix': {}, 'development_efficiency': {},
        'development_context': {}, 'open_issues': [], 'handoffs': [], 'active_task': {},
    }
    _write(root / 'status/current.json', status)
    _write(root / 'heartbeat/manager.json', heartbeat)
    _write(root / 'handover/current.json', handover)
    _write(root / 'audit/events.jsonl', json.dumps({'event_type': 'cycle'}) + '\n')
    _write(root / 'commands/queue.json', {'items': []})
    _write(root / 'handoffs/queue.json', {'items': []})

    auditor = SelfAuditor(root, max_age_seconds=60, running_release_version=release)
    result = auditor.run(now=datetime.now(timezone.utc), require_coordination=True)
    stale_reasons = [
        item for item in result['invalid']
        if item.get('reason') == 'stale' and item.get('path') in {'status/current.json', 'heartbeat/manager.json'}
    ]
    assert stale_reasons == []


def test_32445_noncoordinated_stale_heartbeat_still_fails_closed(tmp_path):
    from self_audit import SelfAuditor
    auditor = SelfAuditor(tmp_path, max_age_seconds=60, running_release_version='32.4.45')
    old = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
    assert auditor._fresh(old, datetime.now(timezone.utc)) is False


def test_32445_control_plane_accepts_v3_runtime_evidence():
    control = (ROOT / 'tools/control_plane/control_plane.py').read_text(encoding='utf-8')
    legacy_executor = (ROOT / 'tools/native_mcp_reload_executor.py').read_text(encoding='utf-8')
    assert 'energie_native_mcp_runtime_v3' in control
    assert 'energie_native_mcp_runtime_v3' in legacy_executor
    assert 'time.monotonic()' in control


def test_32445_exact_32444_build_basis_is_recorded():
    evidence = json.loads((ROOT / 'docs/32.4.45-build-basis.json').read_text(encoding='utf-8'))
    assert evidence['target_release'] == '32.4.45'
    assert evidence['previous_release'] == '32.4.44'
    assert evidence['artifact_sha256'] == '0dc1312b75afd6bdf281c8fe881c765e3bcda658339418366e8cad2459e34df0'
    assert evidence['manifest_files_verified'] == 425
    assert evidence['verified_against_live_atomic_swap'] is True


def test_32445_release_identity_is_coherent():
    import release_test_contract as contract
    assert contract.CURRENT_RELEASE == '32.4.47'
    assert contract.CURRENT_PM_VERSION == '2.0.0-rc34'
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == contract.CURRENT_RELEASE
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == contract.CURRENT_PM_VERSION
    assert f'version: "{contract.CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert f'APP_VERSION = "{contract.CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/rootfs/app/main.py').read_text(encoding='utf-8')
    assert f'TARGET_RELEASE_VERSION = "{contract.CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/rootfs/app/mode_entrypoint.py').read_text(encoding='utf-8')
