from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for p in (ROOT, APP, PM, TOOLS):
    s=str(p)
    if s not in sys.path:
        sys.path.insert(0,s)


def _write_project_cr(root: Path, version: str):
    target=root/'Backups/CrashRecovery'; target.mkdir(parents=True, exist_ok=True)
    stem=f'2026-09-11 08.00 {version} CR EnergieProject'
    z=target/f'{stem}.zip'
    with zipfile.ZipFile(z,'w') as arc: arc.writestr('EnergieProject/ok.txt','ok')
    sha=hashlib.sha256(z.read_bytes()).hexdigest()
    (target/f'{stem}.sha256').write_text(f'{sha}  {z.name}\n')
    (target/f'{stem}.manifest.json').write_text(json.dumps({'file_count':1,'version':version}))
    (target/f'{stem}.restore.txt').write_text('VERIFIED restore drill\n')
    return z


def _write_nas_cr(root: Path, version: str):
    target=root/'Backups/NAS Container'; target.mkdir(parents=True, exist_ok=True)
    stem=f'2026-09-11 08.01 {version} CR NAS Containers'
    z=target/f'{stem}.zip'
    with zipfile.ZipFile(z,'w') as arc: arc.writestr('ok.txt','ok')
    sha=hashlib.sha256(z.read_bytes()).hexdigest()
    (target/f'{stem}.zip.sha256').write_text(f'{sha}  {z.name}\n')
    (target/f'{stem} VERIFY.txt').write_text('NAS_CONTAINER_CR_ACCEPTANCE_OK\nPRODUCTION_CONTAINERS_CHANGED=NO\nNAS_CR_RETENTION_MAX1_OK\n')
    return z


def test_release_identity_is_32438_and_pm_rc25():
    assert (ROOT/'VERSIE.txt').read_text().strip() == '32.4.39'
    assert (PM/'VERSION.txt').read_text().strip() == '2.0.0-rc26'


def test_short_running_signal_is_projectmanager_intent():
    from conversation_runtime import ProjectmanagerConversationRuntime
    assert ProjectmanagerConversationRuntime.handles('32.4.38 draait') is True
    assert ProjectmanagerConversationRuntime.handles('v38 draait') is True


def test_clearup_quarantine_itself_is_not_hygiene_debt(tmp_path):
    from project_hygiene import project_hygiene_check
    (tmp_path/'CLEARUP/run-1/original').mkdir(parents=True)
    (tmp_path/'CLEARUP/run-1/manifest.json').write_text('{}')
    result=project_hygiene_check(tmp_path)
    assert result['details']['clearup_run_count'] == 1
    assert result['status'] == 'GREEN'


def test_32438_clearup_requires_current_project_and_nas_cr(tmp_path):
    import project_clearup_auto as auto
    root=tmp_path/'EnergieProject'; (root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.4.38\n')
    _write_project_cr(root,'32.4.37'); _write_nas_cr(root,'32.4.37')
    result=auto._current_release_cr_gate(root, app_version='32.4.38')
    assert result['ok'] is False
    _write_project_cr(root,'32.4.38'); _write_nas_cr(root,'32.4.38')
    # Max-1 is part of the gate: old canonical sets must already have been
    # moved to retention quarantine by the successful new-CR transaction.
    for directory, suffix in ((root/'Backups/CrashRecovery','32.4.37 CR EnergieProject'), (root/'Backups/NAS Container','32.4.37 CR NAS Containers')):
        for item in list(directory.iterdir()):
            if suffix in item.name:
                item.unlink()
    result=auto._current_release_cr_gate(root, app_version='32.4.38')
    assert result['ok'] is True
    assert len(result['fingerprint']) == 64


def test_pre_32438_clearup_keeps_legacy_gate_compatibility(tmp_path):
    import project_clearup_auto as auto
    root=tmp_path/'EnergieProject'; (root/'Backups/CrashRecovery').mkdir(parents=True)
    assert auto._requires_current_release_cr('32.4.37') is False
    assert auto._requires_current_release_cr('32.4.38') is True


def test_32438_already_completed_requires_matching_prerequisite_fingerprint():
    source=(APP/'project_clearup_auto.py').read_text()
    assert 'prerequisite_fingerprint' in source
    assert 'manifest.get("prerequisite_fingerprint") == current_prerequisite_fingerprint' in source


def test_cr_quarantine_is_excluded_from_next_project_cr_hotfix():
    source=(TOOLS/'cr_standard_native_mcp_hotfix.py').read_text()
    assert 'Backups/CRRetentionQuarantine' in source
    assert 'CRRetentionQuarantine' in source


def test_kb_sync_contains_recent_32436_32437_32438_lessons():
    source=(PM/'manager_service.py').read_text()
    for version in ('32.4.36','32.4.37','32.4.38'):
        assert f'Ontwikkelproceslessen {version}' in source
    assert 'vXX draait' in source
    assert 'quarantaine' in source.lower()


def test_canonical_roadmap_has_live_324_closure_before_ngrok():
    source=(PM/'canonical_roadmap_migration.py').read_text()
    assert "TARGET_RELEASE = '32.4.39'" in source
    assert "'32-4-closure-live'" in source
    assert "'depends_on': ['32-4-closure-live']" in source


def test_closure_health_is_separate_from_ngrok_and_requires_live_gates():
    from series_324_live_closure import evaluate
    checks={name:{'name':name,'status':'GREEN'} for name in (
        'watcher_container_contract','native_mcp_runtime','project_crash_recovery_set',
        'nas_container_crash_recovery_retention','project_structure_hygiene')}
    result=evaluate(list(checks.values()), clearup={'status':'completed','release_version':'32.4.38'}, release_version='32.4.38')
    assert result['status']=='GREEN'
    assert 'ngrok_security' not in result['required_checks']
    checks['native_mcp_runtime']['status']='RED'
    assert evaluate(list(checks.values()), clearup={'status':'completed','release_version':'32.4.38'}, release_version='32.4.38')['status']=='RED'


def test_pm_marks_canonical_324_closure_done_only_on_green():
    source=(PM/'orchestrator.py').read_text()
    assert 'series_324_live_closure' in source
    assert "mark_done_by_key('32-4-closure-live'" in source
    assert "closure.get('status') == 'GREEN'" in source


def test_post_release_autonomy_queues_only_needed_fixed_actions():
    from series_324_live_closure import next_action
    base={
        'watcher_container_contract':'GREEN','native_mcp_runtime':'GREEN',
        'project_crash_recovery_set':'GREEN','nas_container_crash_recovery_retention':'GREEN',
        'project_structure_hygiene':'ORANGE',
    }
    assert next_action(base, clearup_done=False)=='RUN_CLEARUP'
    base['project_crash_recovery_set']='ORANGE'
    assert next_action(base, clearup_done=False)=='CREATE_PROJECT_CR'
    base['watcher_container_contract']='RED'
    assert next_action(base, clearup_done=False)=='REQUEST_WATCHER_RECREATE'


def test_project_cr_fixed_request_executor_exists_and_is_narrow():
    gateway=(PM/'command_gateway.py').read_text()
    processor=(PM/'command_processor.py').read_text()
    watcher=(TOOLS/'release_watcher.sh').read_text()
    executor=(TOOLS/'project_cr_local_executor.py').read_text()
    assert "'project_cr_create'" in gateway
    assert 'project_cr_create' in processor
    assert 'process_project_cr_local' in watcher
    assert 'project_cr_local_executor.py' in watcher
    assert 'shell=True' not in executor
    assert 'create_crash_recovery_backup' in executor


def test_main_clearup_wait_does_not_consume_execution_budget_for_prerequisites():
    source=(APP/'main.py').read_text()
    fn=source[source.index('def startup_project_clearup()'):]
    assert 'waiting_for_prerequisites' in fn
    assert 'timeout_seconds=PROJECT_CLEARUP_MAX_SECONDS' in fn


def test_32438_clearup_gate_uses_current_crs_as_authoritative_proof(tmp_path):
    import project_clearup_auto as auto
    root=tmp_path/'EnergieProject'
    (root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.4.38\n')
    approval=root/'Data/03_Systeem/Projectmanager/State/32_4_25_scope_cleanup_and_history_repair_20260909.md'
    approval.parent.mkdir(parents=True)
    approval.write_text('Status: DEVELOPMENT SCOPE APPROVED BY USER\nCLEARUP\n')
    (root/'Inbox/operating_mode').mkdir(parents=True)
    (root/'Inbox/atomic_app_swap_state.json').write_text(json.dumps({'state':'ACCEPTED','to_version':'32.4.38'}))
    (root/'Inbox/operating_mode/release_validation_hold.json').write_text(json.dumps({'active':False,'validation_status':'ok'}))
    (root/'CLEARUP').mkdir()
    _write_project_cr(root,'32.4.38'); _write_nas_cr(root,'32.4.38')
    # The canonical CR restore file contains instructions, not a legacy magic
    # VERIFIED word. Current-release deep verification must be authoritative.
    for restore in (root/'Backups/CrashRecovery').glob('*.restore.txt'):
        restore.write_text('restore instructions present\n')
    gate=auto.clearup_auto_gate(root,app_version='32.4.38')
    assert gate['ready'] is True
    assert gate['blockers'] == []
    assert gate['current_release_cr']['ok'] is True


def test_project_cr_executor_consumes_exact_request(tmp_path, monkeypatch):
    import importlib.util, sys, types, json
    root = tmp_path
    (root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.4.38\n', encoding='utf-8')
    bridge = root/'Inbox/project_cr_local'; bridge.mkdir(parents=True)
    req = {'schema':'energie_project_cr_local_request_v1','request_id':'a'*32,'operation':'project_cr_create','expected_runtime_version':'32.4.38'}
    (bridge/'request.json').write_text(json.dumps(req), encoding='utf-8')
    native = root/'Infra/Docker/native-mcp'; native.mkdir(parents=True)
    fake = types.ModuleType('crash_recovery')
    fake.create_crash_recovery_backup = lambda *a, **k: {'status':'valid','deep_verified':True,'backup_name':'2026-09-11 08.00 32.4.38 CR EnergieProject.zip','backup_sha256':'x','retention_delete_performed':False,'retention_quarantined':[]}
    fake.verify_crash_recovery_backup = lambda *a, **k: {'status':'valid','verified_files':1}
    sys.modules['crash_recovery'] = fake
    spec = importlib.util.spec_from_file_location('project_cr_local_executor_under_test', TOOLS/'project_cr_local_executor.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    result = mod.execute(root)
    assert result['status'] == 'GREEN'
    assert not (bridge/'request.json').exists(), 'consumed request must be removed to prevent repeated backups'


def test_empty_projectmanager_staging_root_is_not_hygiene_debt(tmp_path):
    from project_hygiene import project_hygiene_check
    (tmp_path/'Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2').mkdir(parents=True)
    result = project_hygiene_check(tmp_path)
    assert result['details']['known_staging_path_count'] == 0
    assert result['status'] == 'GREEN'


def test_release_builder_filters_ad_hoc_test_inventory(tmp_path):
    import zipfile
    from release_artifact_builder import build_release_artifact
    source = tmp_path/'src'; source.mkdir()
    for rel, text in {
        'README.md':'x','INSTALL.md':'x','CHANGELOG.md':'x','repository.yaml':'x','VERSIE.txt':'32.4.38\n',
        'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt':'2.0.0-rc25\n',
        '.testfiles438.txt':'tests/test_x.py\n',
    }.items():
        p=source/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8')
    out=tmp_path/'out.zip'
    result=build_release_artifact(source,out)
    assert '.testfiles438.txt' in result['filtered']
    with zipfile.ZipFile(out) as z:
        assert '.testfiles438.txt' not in z.namelist()


def test_project_cr_executor_failure_writes_matching_red_before_consuming_request(tmp_path):
    import importlib.util, sys, types, json, pytest
    root=tmp_path; (root/'App').mkdir(parents=True); (root/'App/VERSIE.txt').write_text('32.4.38\n')
    bridge=root/'Inbox/project_cr_local'; bridge.mkdir(parents=True)
    rid='b'*32
    (bridge/'request.json').write_text(json.dumps({'schema':'energie_project_cr_local_request_v1','request_id':rid,'operation':'project_cr_create','expected_runtime_version':'32.4.38'}))
    native=root/'Infra/Docker/native-mcp'; native.mkdir(parents=True)
    fake=types.ModuleType('crash_recovery')
    def boom(*a,**k): raise RuntimeError('simulated backup failure')
    fake.create_crash_recovery_backup=boom
    fake.verify_crash_recovery_backup=lambda *a,**k: {}
    sys.modules['crash_recovery']=fake
    spec=importlib.util.spec_from_file_location('project_cr_local_executor_failure_test', TOOLS/'project_cr_local_executor.py')
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    with pytest.raises(RuntimeError, match='simulated backup failure'):
        mod.execute(root)
    result=json.loads((bridge/'result.json').read_text())
    assert result['status']=='RED'
    assert result['request_id']==rid
    assert not (bridge/'request.json').exists()
