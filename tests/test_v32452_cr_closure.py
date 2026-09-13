import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for p in (APP, PM, TOOLS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _project(tmp_path, version='32.4.52'):
    (tmp_path/'App').mkdir(parents=True)
    (tmp_path/'App/VERSIE.txt').write_text(version+'\n', encoding='utf-8')
    return tmp_path


def test_hotfix_adds_strict_atomic_temp_snapshot_policy():
    import cr_standard_native_mcp_hotfix as hotfix
    live = '''from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import os
import shutil
import stat

def _excluded(relative: PurePosixPath) -> bool:
    parts = relative.parts
    return (
        len(parts) >= 2
        and parts[0] == "Backups"
        and parts[1] in {CRASH_DIR_NAME, "CRRetentionQuarantine", "RestoreStaging", "_release_prepare"}
    )

def _inventory(project_root: Path, max_files: int, max_source_bytes: int) -> dict:
    files = []
    directories = []
    symlinks = []
    source_bytes = 0

    for root, dirnames, filenames in os.walk(project_root, topdown=True, followlinks=False):
        root_path = Path(root)
        root_rel = root_path.relative_to(project_root)
        for name in sorted(filenames):
            p = root_path / name
            rel = PurePosixPath((root_rel / name).as_posix())
            if _excluded(rel):
                continue
            if p.is_symlink():
                continue
    return {
        "files": files,
        "directories": sorted(set(directories)),
        "symlinks": sorted(symlinks, key=lambda x: x["path"]),
        "file_count": len(files),
        "directory_count": len(set(directories)),
        "symlink_count": len(symlinks),
        "source_bytes": source_bytes,
    }

def _copy_stable(src: Path, dst: Path, retries: int = 4):
    pass

def create_crash_recovery_backup(project_root: Path, recovery_root: Path, *, retention: int = 1,
                                 max_files: int = 50000,
                                 max_source_bytes: int = 20 * 1024 * 1024 * 1024) -> dict:
    inventory = _inventory(project_root, max_files, max_source_bytes)
    records = []

    try:
        for item in inventory["files"]:
            src = project_root.joinpath(*PurePosixPath(item["path"]).parts)
            dst = Path("stage").joinpath(*PurePosixPath(item["path"]).parts)
            size, mtime_ns, mode, digest = _copy_stable(src, dst)
            records.append({"path": item["path"], "size": size, "mtime_ns": mtime_ns,
                            "mode": mode, "sha256": digest})
        manifest = {
            "schema": "energie_crash_recovery_v1",
            "type": "EnergieProject_CRASH_RECOVERY",
        }
        return {
            "retention_delete_performed": False,
            "excluded": ["Backups/CrashRecovery/**"],
        }
    finally:
        pass
'''
    out = hotfix._crash_recovery_snapshot_v2(live)
    assert 'energie_cr_snapshot_v2' in out
    assert 'known_atomic_temp_disappeared_after_inventory' in out
    assert 'Data/03_Systeem/' in out and 'Inbox/' in out
    assert 'Data/02_Output/' not in out
    assert hotfix._crash_recovery_snapshot_v2(out) == out
    ns={}
    exec(compile(out, '<transformed-cr>', 'exec'), ns)
    from pathlib import PurePosixPath
    assert ns['_is_known_atomic_temp'](PurePosixPath('Data/03_Systeem/x/.a.json.tmp-12-abcd1234')) is True
    assert ns['_is_known_atomic_temp'](PurePosixPath('Inbox/.request.json.tmp-12')) is True
    assert ns['_is_known_atomic_temp'](PurePosixPath('Data/02_Output/.a.json.tmp-12-abcd1234')) is False
    assert ns['_is_known_atomic_temp'](PurePosixPath('Data/03_Systeem/x/normal.json')) is False

def test_project_cr_reconciles_stale_release_when_worker_not_active(tmp_path):
    from project_cr_service import ConfiguredProjectCrService
    root=_project(tmp_path)
    bridge=root/'Inbox/project_cr_local'; bridge.mkdir(parents=True)
    old={'schema':'energie_project_cr_local_request_v1','request_id':'a'*32,'operation':'project_cr_create','expected_runtime_version':'32.4.51','command_id':'b'*32}
    (bridge/'request.json').write_text(json.dumps(old),encoding='utf-8')
    service=ConfiguredProjectCrService(root, timeout_seconds=.01, poll_seconds=.001)
    result=service.create(command_id='c'*32, expected_release='32.4.52', wait_for_result=False)
    assert result['status']=='PENDING' and result['command_id']=='c'*32
    evidence=list((bridge/'evidence').glob('*.json'))
    assert evidence
    current=json.loads((bridge/'request.json').read_text())
    assert current['expected_runtime_version']=='32.4.52' and current['command_id']=='c'*32


def test_project_cr_stale_release_fails_closed_while_worker_marker_present(tmp_path):
    from project_cr_service import ConfiguredProjectCrService
    root=_project(tmp_path); bridge=root/'Inbox/project_cr_local'; bridge.mkdir(parents=True)
    old={'schema':'energie_project_cr_local_request_v1','request_id':'a'*32,'operation':'project_cr_create','expected_runtime_version':'32.4.51','command_id':'b'*32}
    (bridge/'request.json').write_text(json.dumps(old),encoding='utf-8')
    (bridge/'project_cr_local_worker.pid').write_text('123\n',encoding='utf-8')
    service=ConfiguredProjectCrService(root, timeout_seconds=.01, poll_seconds=.001)
    try:
        service.create(command_id='c'*32, expected_release='32.4.52', wait_for_result=False)
    except RuntimeError as exc:
        assert 'actieve worker' in str(exc)
    else:
        raise AssertionError('expected fail-closed')


def test_project_cr_result_requires_exact_identity(tmp_path):
    from project_cr_service import ConfiguredProjectCrService
    root=_project(tmp_path); bridge=root/'Inbox/project_cr_local'; bridge.mkdir(parents=True)
    req={'schema':'energie_project_cr_local_request_v1','request_id':'a'*32,'operation':'project_cr_create','expected_runtime_version':'32.4.52','command_id':'b'*32}
    (bridge/'request.json').write_text(json.dumps(req),encoding='utf-8')
    bad={'schema':'energie_project_cr_local_result_v1','request_id':'a'*32,'operation':'wrong','status':'GREEN','ok':True,'version':'32.4.52','command_id':'b'*32,'deep_verified':True}
    (bridge/'result.json').write_text(json.dumps(bad),encoding='utf-8')
    service=ConfiguredProjectCrService(root, timeout_seconds=.01, poll_seconds=.001)
    try:
        service.create(command_id='b'*32, expected_release='32.4.52')
    except RuntimeError as exc:
        assert 'resultaat ongeldig' in str(exc)
    else:
        raise AssertionError('expected identity validation failure')


def test_32452_scope_does_not_add_general_retry_or_change_sequencer():
    orch=(PM/'orchestrator.py').read_text(encoding='utf-8')
    closure=(PM/'series_324_live_closure.py').read_text(encoding='utf-8')
    assert "previous_terminal_block" in orch
    assert "return 'CREATE_PROJECT_CR'" in closure
    assert "return 'CREATE_NAS_CR'" in closure
    assert "return 'RUN_CLEARUP'" in closure

def test_canonical_cr_sets_publish_green_and_drive_existing_closure_sequence(tmp_path):
    import hashlib
    from datetime import datetime, timezone
    from energy_health_collector import EnergyHealthCollector
    from series_324_live_closure import next_action, evaluate

    root=_project(tmp_path)
    backups=root/'Backups'; inputs=root/'Data/01_Input'
    project_dir=backups/'CrashRecovery'; project_dir.mkdir(parents=True)
    pzip=project_dir/'2026-09-13 15.30 32.4.52 CR EnergieProject.zip'
    pzip.write_bytes(b'project-cr')
    psha=hashlib.sha256(pzip.read_bytes()).hexdigest()
    (project_dir/'2026-09-13 15.30 32.4.52 CR EnergieProject.sha256').write_text(f'{psha}  {pzip.name}\n',encoding='utf-8')
    (project_dir/'2026-09-13 15.30 32.4.52 CR EnergieProject.manifest.json').write_text('{}\n',encoding='utf-8')
    (project_dir/'2026-09-13 15.30 32.4.52 CR EnergieProject.restore.txt').write_text('restore\n',encoding='utf-8')

    nas_dir=backups/'NAS Container'; nas_dir.mkdir(parents=True)
    nzip=nas_dir/'2026-09-13 15.31 32.4.52 CR NAS Containers.zip'
    nzip.write_bytes(b'nas-cr')
    nsha=hashlib.sha256(nzip.read_bytes()).hexdigest()
    (nas_dir/(nzip.name+'.sha256')).write_text(f'{nsha}  {nzip.name}\n',encoding='utf-8')
    (nas_dir/'2026-09-13 15.31 32.4.52 CR NAS Containers VERIFY.txt').write_text(
        'NAS_CONTAINER_CR_ACCEPTANCE_OK\nPRODUCTION_CONTAINERS_CHANGED=NO\nNAS_CR_RETENTION_MAX1_OK\n',encoding='utf-8')

    checks=EnergyHealthCollector(root,inputs,backups).collect(now=datetime.now(timezone.utc))
    status={item['name']:item['status'] for item in checks}
    assert status['project_crash_recovery_set']=='GREEN'
    assert status['nas_container_crash_recovery_retention']=='GREEN'

    base={'watcher_container_contract':'GREEN','native_mcp_runtime':'GREEN',
          'project_crash_recovery_set':'GREEN','nas_container_crash_recovery_retention':'ORANGE',
          'project_structure_hygiene':'ORANGE'}
    assert next_action(base,clearup_done=False)=='CREATE_NAS_CR'
    base['nas_container_crash_recovery_retention']='GREEN'
    assert next_action(base,clearup_done=False)=='RUN_CLEARUP'
    base['project_structure_hygiene']='GREEN'
    assert next_action(base,clearup_done=True)=='COMPLETE'
    closure=evaluate([{'name':k,'status':v} for k,v in base.items()],
                     clearup={'status':'completed','release_version':'32.4.52'},release_version='32.4.52')
    assert closure['status']=='GREEN'
