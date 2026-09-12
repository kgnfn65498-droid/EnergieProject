from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for p in (str(ROOT), str(APP), str(PM), str(TOOLS)):
    if p not in sys.path:
        sys.path.insert(0, p)


def test_release_identity_is_32437_and_pm_rc24():
    import release_test_contract as contract
    assert (ROOT / 'VERSIE.txt').read_text().strip() == contract.CURRENT_RELEASE
    assert (PM / 'VERSION.txt').read_text().strip() == contract.CURRENT_PM_VERSION


def test_watcher_contract_fails_closed_without_socket(tmp_path):
    from watcher_container_contract import probe

    root = tmp_path / 'EnergieProject'
    (root / 'Inbox').mkdir(parents=True)
    result = probe(root, socket_path=tmp_path / 'missing.sock')
    assert result['status'] == 'RECREATE_REQUIRED'
    assert result['ready'] is False
    assert result['contract_version'] == 3
    marker = json.loads((root / 'Inbox/watcher_container_contract.json').read_text())
    assert marker['recreate_required'] is True


def test_watcher_bootstrap_declares_and_verifies_contract_v3():
    text = (TOOLS / 'bootstrap_release_watcher_container.sh').read_text()
    assert 'ENERGIE_WATCHER_CONTAINER_CONTRACT=3' in text
    assert '/var/run/docker.sock:/var/run/docker.sock' in text
    assert '--network none' in text
    assert '--cap-drop ALL' in text
    assert 'watcher_container_contract.py' in text
    assert 'watcher_container_contract.json' in text


def test_release_watcher_checks_contract_before_nas_capability():
    text = (TOOLS / 'release_watcher.sh').read_text()
    startup = text[text.index('Release watcher gestart'):text.index('while :; do')]
    assert 'process_watcher_container_contract' in startup
    assert startup.index('process_watcher_container_contract') < startup.index('process_nas_cr_capability_probe')


def test_native_mcp_runtime_guard_detects_missing_or_stale_marker(tmp_path, monkeypatch):
    import native_mcp_runtime_guard as guard

    root = tmp_path / 'EnergieProject'
    (root / 'Inbox').mkdir(parents=True)
    expected = 'e' * 64
    targets = ['native:runtime_fingerprint.py', 'native:server.py', 'pm:command_gateway.py']
    monkeypatch.setattr(guard, 'expected_fingerprint', lambda _root: (expected, targets))

    missing = guard.probe(root)
    assert missing['status'] == 'RELOAD_REQUIRED'

    marker = root / 'Data/03_Systeem/Projectmanager/RuntimeEvidence/native_mcp_runtime_fingerprint.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        'schema': 'energie_native_mcp_runtime_v2', 'fingerprint': '0' * 64, 'targets': targets,
    }))
    stale = guard.probe(root)
    assert stale['status'] == 'RELOAD_REQUIRED'

    marker.write_text(json.dumps({
        'schema': 'energie_native_mcp_runtime_v2', 'fingerprint': expected, 'targets': targets,
    }))
    green = guard.probe(root)
    assert green['status'] == 'GREEN'
    assert green['ready'] is True

def test_native_hotfix_injects_runtime_fingerprint_marker():
    source = (TOOLS / 'cr_standard_native_mcp_hotfix.py').read_text()
    assert 'runtime_fingerprint.json' in source
    assert 'energie_native_mcp_runtime_v1' in source
    assert 'CRRetentionQuarantine' in source


def test_mcp_reload_executor_is_fixed_to_one_container_and_no_generic_cli():
    source = (TOOLS / 'native_mcp_reload_executor.py').read_text()
    assert 'energie-filesystem-mcp' in source
    assert '/restart' in source
    assert 'shell=True' not in source
    assert 'container_name' not in source
    assert 'command' not in source.lower() or 'argparse' not in source
    assert 'reload_request.json' in source
    assert 'reload_result.json' in source


def _minimal_nas_service(tmp_path):
    from nas_container_cr_service import NasContainerCrService

    class Docker:
        pass

    root = tmp_path / 'EnergieProject'
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.37\n')
    (root / 'Backups/NAS Container').mkdir(parents=True)
    return root, NasContainerCrService(root, Docker())


def _write_nas_set(target: Path, stem: str):
    import zipfile
    z = target / f'{stem}.zip'
    with zipfile.ZipFile(z, 'w') as arc:
        arc.writestr('ok.txt', 'ok')
    digest = hashlib.sha256(z.read_bytes()).hexdigest()
    (target / f'{stem}.zip.sha256').write_text(f'{digest}  {z.name}\n')
    (target / f'{stem} VERIFY.txt').write_text(
        'NAS_CONTAINER_CR_ACCEPTANCE_OK\nPRODUCTION_CONTAINERS_CHANGED=NO\nNAS_CR_RETENTION_MAX1_OK\n'
    )


def test_nas_retention_commit_quarantines_old_set_instead_of_unlink(tmp_path):
    root, service = _minimal_nas_service(tmp_path)
    target = root / 'Backups/NAS Container'
    old = '2026-09-09 10.00 32.4.36 CR NAS Containers'
    new = '2026-09-10 10.00 32.4.37 CR NAS Containers'
    _write_nas_set(target, old)
    _write_nas_set(target, new)
    tx = service._stage_keep1(new)
    result = service._commit_keep1(tx)
    assert result['removed'] == 1
    assert not (target / f'{old}.zip').exists()
    qroot = root / 'Backups/CRRetentionQuarantine/NAS Container'
    assert list(qroot.rglob(f'{old}.zip'))
    assert list(qroot.rglob('manifest.json'))
    assert (target / f'{new}.zip').exists()


def test_nas_retention_rollback_restores_old_set_if_manifest_commit_fails(tmp_path, monkeypatch):
    root, service = _minimal_nas_service(tmp_path)
    target = root / 'Backups/NAS Container'
    old = '2026-09-09 10.00 32.4.36 CR NAS Containers'
    new = '2026-09-10 10.00 32.4.37 CR NAS Containers'
    _write_nas_set(target, old)
    _write_nas_set(target, new)
    tx = service._stage_keep1(new)

    original = Path.write_text
    def fail_manifest(self, *args, **kwargs):
        if self.name == 'manifest.json':
            raise OSError('simulated manifest failure')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(Path, 'write_text', fail_manifest)
    with pytest.raises(OSError):
        service._commit_keep1(tx)
    service._rollback_keep1(tx)
    assert (target / f'{old}.zip').exists()
    assert (target / f'{old}.zip.sha256').exists()
    assert (target / f'{old} VERIFY.txt').exists()


def test_clearup_stays_fresh_audit_hard_move_and_no_delete():
    auto = (APP / 'project_clearup_auto.py').read_text()
    core = (APP / 'project_clearup.py').read_text()
    executor = (TOOLS / 'project_clearup_move_executor.py').read_text()
    assert 'fresh_dependency_audit' in auto
    assert 'CLEARUP-plan is gewijzigd; nieuwe dependency-audit vereist.' in auto
    assert 'source.rename(destination)' in core
    assert 'old_path_absent' in core
    assert 'restore_status' in core
    assert 'delete_capability": False' in core or '"delete_capability": False' in core
    assert 'delete_capability moet exact false zijn' in executor


def test_health_includes_watcher_contract_native_runtime_and_canonical_cr_only():
    source = (PM / 'energy_health_collector.py').read_text()
    assert 'watcher_container_contract' in source
    assert 'native_mcp_runtime' in source
    assert '_canonical_cr_regex' in source
    assert "len(project_all_zips) == 1" in source
    assert "len(nas_zips) == 1" in source


def test_installer_records_post_release_maintenance_requirement_and_watcher_applies_it():
    installer = (TOOLS / 'release_installer.sh').read_text()
    watcher = (TOOLS / 'release_watcher.sh').read_text()
    assert 'post_release_maintenance_required.json' in installer
    assert 'process_post_release_maintenance_transition' in watcher
    assert 'MAINTENANCE' in watcher


def test_active_tls_routes_remain_unreachable():
    web = (PM / 'projectmanager_web.py').read_text()
    orch = (PM / 'orchestrator.py').read_text()
    service = (PM / 'nas_container_cr_service.py').read_text()
    assert 'nas_docker_tls_root=' not in orch
    configured = service[service.index('class ConfiguredNasContainerCrService'):]
    assert 'docker_engine_tls_client' not in configured
    assert 'nas_docker_tls' not in configured
    post = web[web.index('def wrapped_do_post'):]
    assert '/api/projectmanager/nas-container-cr/docker-tls' not in post
    assert '/api/projectmanager/nas-container-cr/activate' not in post


def test_post_release_transition_is_idempotent_after_applied(tmp_path):
    from operating_modes import Mode, ModeState, save_mode_state
    from post_release_mode_transition import apply

    root = tmp_path / 'EnergieProject'
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.37\n')
    marker = root / 'Inbox/operating_mode/post_release_maintenance_required.json'
    marker.parent.mkdir(parents=True)
    marker.write_text(json.dumps({
        'schema': 'energie_post_release_maintenance_v1',
        'status': 'APPLIED',
        'release_version': '32.4.37',
        'mode': 'MAINTENANCE',
    }))
    save_mode_state(root, ModeState(base_mode=Mode.USER, effective_mode=Mode.USER))
    result = apply(root)
    assert result['status'] == 'APPLIED'
    assert result['changed'] is False
    from operating_modes import load_mode_state
    state = load_mode_state(root)
    assert state.base_mode is Mode.USER
    assert state.effective_mode is Mode.USER


def test_installer_writes_post_release_marker_before_atomic_rollback_is_disabled():
    text = (TOOLS / 'release_installer.sh').read_text()
    marker = text.rindex('write_post_release_maintenance_required')
    disable = text.rindex('ATOMIC_SWAP_ACTIVE=0')
    assert marker < disable


def test_watcher_startup_failure_cannot_be_masked_by_watcher_active():
    text = (TOOLS / 'release_watcher.sh').read_text()
    startup = text[text.index('Release watcher gestart'):text.index('while :; do')]
    assert 'STARTUP_DEGRADED' in startup
    assert 'watcher-container-recreate-required' in startup
    assert 'native-mcp-reload-required' in startup
    assert 'nas-cr-local-capability' in startup
    active = startup.rfind('write_status "WATCHER_ACTIVE"')
    failed = startup.rfind('write_status "MAINTENANCE_FAILED"')
    assert active != -1 and failed != -1
    assert 'if [ -n "$STARTUP_DEGRADED" ]' in startup


def test_native_mcp_reload_requires_exact_fixed_operation(tmp_path, monkeypatch):
    import native_mcp_reload_executor as executor

    root = tmp_path / 'EnergieProject'
    request = root / 'Inbox/native_mcp_runtime/reload_request.json'
    request.parent.mkdir(parents=True)
    request.write_text(json.dumps({
        'schema': 'energie_native_mcp_reload_request_v1',
        'request_id': 'a' * 32,
        'expected_fingerprint': 'b' * 64,
        'operation': 'anything_else',
    }))
    called = {'restart': False}
    monkeypatch.setattr(executor, '_restart', lambda: called.__setitem__('restart', True))
    with pytest.raises(RuntimeError, match='operation'):
        executor.run(root, wait_seconds=1)
    assert called['restart'] is False


def test_protected_reload_does_not_overwrite_different_pending_request(tmp_path):
    from projectmanager_v2.protected_action_executor import ProtectedActionExecutor

    class Dummy:
        def open_items(self): return []

    root = tmp_path / 'EnergieProject'
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.42\n')
    guard = root / 'Inbox/native_mcp_runtime/runtime_guard.json'
    guard.parent.mkdir(parents=True)
    guard.write_text(json.dumps({
        'status': 'RELOAD_REQUIRED', 'reload_required': True,
        'expected_fingerprint': 'c' * 64,
    }))
    pending = guard.parent / 'reload_request.json'
    pending.write_text(json.dumps({'schema': 'energie_native_mcp_reload_request_v1', 'request_id': 'd' * 32}))
    ex = ProtectedActionExecutor(root, Dummy(), Dummy(), Dummy())
    action = {'id': 'new-action', 'command_id': 'cmd', 'decision_id': 'decision'}
    command = {'id': 'cmd', 'intent': 'native_mcp_reload', 'release_version': '32.4.42', 'approval_decision_id': 'decision'}
    decision = {
        'id': 'decision', 'status': 'APPROVED', 'approved_by': 'Peter', 'kind': 'PRODUCTION_RESTART',
        'context': {'command_id': 'cmd', 'intent': 'native_mcp_reload', 'release_version': '32.4.42'},
    }
    with pytest.raises(RuntimeError, match='pending'):
        ex._queue_native_mcp_reload(action, command, decision)
    assert json.loads(pending.read_text())['request_id'] == 'd' * 32


def test_watcher_clears_stale_reload_result_before_executor():
    text = (TOOLS / 'release_watcher.sh').read_text()
    fn = text[text.index('process_native_mcp_reload(){'):text.index('process_post_release_maintenance_transition(){')]
    assert 'rm -f "$NATIVE_MCP_RELOAD_RESULT"' in fn


def test_hotfix_postcheck_requires_quarantine_and_runtime_fingerprint_contracts():
    source = (TOOLS / 'cr_standard_native_mcp_hotfix.py').read_text()
    post = source[source.index('# Contract-level assertions'):]
    assert "'CRRetentionQuarantine' in crash" in post
    assert "'energie_native_mcp_runtime_v1' in tools" in post
    assert "'CRRetentionQuarantine' in retention" in post


def test_native_hotfix_transforms_436_crash_source_to_quarantine_and_compiles():
    import cr_standard_native_mcp_hotfix as hotfix

    source = '''from pathlib import Path\nimport os, json\nLEGACY_CRASH_NAME_SUFFIX = "CrashRecovery EnergieProject"\nCRASH_NAME_SUFFIX = "CR EnergieProject"\nCRASH_FILENAME_GLOB = f"* {CRASH_NAME_SUFFIX}*.zip"\nRETENTION_DEFAULT = 1\nCRASH_PREFIX = "EnergieProject_CRASH_RECOVERY"\ndef x():\n    for pattern in (CRASH_FILENAME_GLOB, f"* {LEGACY_CRASH_NAME_SUFFIX}*.zip", f"{CRASH_PREFIX}_*.zip"):\n        pass\ndef a(retention: int = 1,): pass\ndef b(retention: int = 1,): pass\ndef c():\n    version = "32.4.36"\n    base_stem = f"{_local_file_stamp()} {version} {CRASH_NAME_SUFFIX}"\ndef _apply_retention(crash_root: Path, retention: int):\n    retention = max(1, int(retention))\n    zips = sorted(_crash_zip_candidates(crash_root),\n                  key=lambda p: p.stat().st_mtime, reverse=True)\n    removed = []\n    for old_zip in zips[retention:]:\n        stem = old_zip.name[:-4]\n        for item in (\n            old_zip,\n            crash_root / f"{stem}.sha256",\n            crash_root / f"{stem}.manifest.json",\n            crash_root / f"{stem}.restore.txt",\n        ):\n            if item.exists():\n                item.unlink()\n        removed.append(old_zip.name)\n    return removed\n'''
    transformed = hotfix._crash_recovery(source)
    assert 'energie_cr_retention_quarantine_v1' in transformed
    assert '.unlink()' not in transformed[transformed.index('def _apply_retention'):]
    assert 'CRRetentionQuarantine' in transformed
    compile(transformed, 'crash_recovery.py', 'exec')


def test_native_hotfix_transforms_436_tools_source_to_runtime_marker_and_compiles():
    import cr_standard_native_mcp_hotfix as hotfix

    source = '''from __future__ import annotations\nfrom pathlib import Path\nfrom typing import Any\nretention=1,\nPATHS = RecoveryPaths(\n    project_root=PROJECT_ROOT,\n    report_root=REPORT_ROOT,\n    recovery_root=RECOVERY_ROOT,\n)\n'''
    transformed = hotfix._tools_recovery(source)
    assert 'energie_native_mcp_runtime_v1' in transformed
    assert 'runtime_fingerprint.json' in transformed
    compile(transformed, 'tools_recovery.py', 'exec')


def test_native_hotfix_transforms_436_nas_retention_to_quarantine_and_shell_syntax(tmp_path):
    import cr_standard_native_mcp_hotfix as hotfix
    import subprocess

    source = '''#!/bin/sh\nset -eu\nDIR=/tmp/x\nNEW_STEM=new\nfail(){ exit 1; }\nset_paths(){ STEM="$1"; ZIP="$DIR/$STEM.zip"; SHA="$DIR/$STEM.zip.sha256"; VERIFY="$DIR/$STEM VERIFY.txt"; }\nvalidate_set() {\n  STEM="$1"\n  REQUIRE_MAX1="${2:-0}"\n  set_paths "$STEM"\n  grep -q '^NAS_CONTAINER_CR_ACCEPTANCE_OK$' "$VERIFY" 2>/dev/null || return 1\n  grep -q '^PRODUCTION_CONTAINERS_CHANGED=NO$' "$VERIFY" 2>/dev/null || return 1\n  if [ "$REQUIRE_MAX1" -eq 1 ]; then grep -q '^NAS_CR_RETENTION_MAX1_OK$' "$VERIFY" 2>/dev/null || return 1; fi\n  return 0\n}\nvalidate_set "$NEW_STEM" 1 || fail "new"\nfor ZIP_PATH in "$DIR"/*" CrashRecovery NAS Containers"*.zip "$DIR"/*" CR NAS Containers"*.zip; do\n  [ -f "$ZIP_PATH" ] || continue\n  STEM="$(basename "$ZIP_PATH" .zip)"\n  BATCH="$DIR/.nas-cr-retention-delete.$$"\n  mkdir -p "$BATCH"\n  mv "$ZIP_PATH" "$BATCH/$STEM.zip"\n  : > "$BATCH/$STEM.zip.sha256"\n  : > "$BATCH/$STEM VERIFY.txt"\n  rm -f \\\n    "$BATCH/$STEM.zip" \\\n    "$BATCH/$STEM.zip.sha256" \\\n    "$BATCH/$STEM VERIFY.txt" || fail "oude set kon niet definitief worden verwijderd: $STEM"\n  rmdir "$BATCH" || fail "tijdelijke retentiemap bleef achter: $BATCH"\ndone\nvalidate_set "$NEW_STEM" 1 || fail "new-after"\n'''
    transformed = hotfix._nas_retention(source)
    assert 'energie_cr_retention_quarantine_v1' in transformed
    assert 'CRRetentionQuarantine/NAS Container' in transformed
    assert 'rm -f \\\n    "$BATCH/$STEM.zip"' not in transformed
    path = tmp_path / 'retention.sh'
    path.write_text(transformed)
    completed = subprocess.run(['sh', '-n', str(path)], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr


def test_production_restart_is_a_supported_protected_decision_kind(tmp_path):
    from projectmanager_v2.decision_queue import DecisionQueue, PROTECTED_DECISION_KINDS
    assert 'PRODUCTION_RESTART' in PROTECTED_DECISION_KINDS
    queue = DecisionQueue(tmp_path / 'decisions.json')
    decision = queue.request('PRODUCTION_RESTART', 'Reload native MCP?', fingerprint='reload-1')
    assert decision['kind'] == 'PRODUCTION_RESTART'
    assert decision['status'] == 'PENDING'


def test_self_audit_knows_native_mcp_reload_has_a_supported_executor():
    from projectmanager_v2.self_audit import SUPPORTED_EXECUTOR_ACTIONS
    assert 'native_mcp_reload' in SUPPORTED_EXECUTOR_ACTIONS


def test_protected_reload_stays_pending_until_matching_green_result(tmp_path):
    from projectmanager_v2.protected_action_executor import ProtectedActionExecutor

    class Store:
        def __init__(self): self.completed=[]
        def open_items(self): return [action]
        def complete(self, item_id, *, result): self.completed.append((item_id, result))

    class Commands:
        def __init__(self): self.completed=[]
        def get(self, item_id): return command
        def complete(self, item_id, *, result): self.completed.append((item_id, result))

    class Decisions:
        def get(self, item_id): return decision

    root = tmp_path / 'EnergieProject'
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.42\n')
    runtime = root / 'Inbox/native_mcp_runtime'
    runtime.mkdir(parents=True)
    runtime.joinpath('runtime_guard.json').write_text(json.dumps({
        'status':'RELOAD_REQUIRED','reload_required':True,'expected_fingerprint':'e'*64,
    }))
    action = {'id':'action-1','action':'native_mcp_reload','command_id':'cmd-1','decision_id':'dec-1'}
    command = {'id':'cmd-1','intent':'native_mcp_reload','release_version':'32.4.42','approval_decision_id':'dec-1'}
    decision = {
        'id':'dec-1','status':'APPROVED','approved_by':'Peter','kind':'PRODUCTION_RESTART',
        'context': {'command_id':'cmd-1','intent':'native_mcp_reload','release_version':'32.4.42'},
    }
    actions=Store(); commands=Commands(); decisions=Decisions()
    ex=ProtectedActionExecutor(root, actions, commands, decisions)
    pending=ex.run_once()
    assert pending[0]['awaiting_executor'] is True
    assert actions.completed == []
    assert commands.completed == []
    request_path=root/'Inbox/control_plane/requests/native_mcp_reload.json'
    request=json.loads(request_path.read_text())
    result_path=root/'Inbox/control_plane/results/native_mcp_reload.json'
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps({
        'schema':'energie_native_mcp_reload_result_v1','request_id':request['request_id'],
        'status':'GREEN','ok':True,'container':'energie-filesystem-mcp',
        'expected_fingerprint':'e'*64,'runtime_fingerprint':'e'*64,'restart_performed':True,
        'decision_id':'dec-1','command_id':'cmd-1','release_version':'32.4.42',
    }))
    final=ex.run_once()
    assert final[0]['restart_performed'] is True
    assert final[0]['runtime_green'] is True
    assert len(actions.completed) == 1
    assert len(commands.completed) == 1


def test_native_mcp_reload_is_protected_across_manager_and_conversation_front_door(tmp_path):
    from projectmanager_v2 import manager_core
    from projectmanager_v2.conversation_intake import protected_action_kind
    from projectmanager_v2.conversation_approval import ConversationApprovalCoordinator
    from projectmanager_v2.decision_queue import DecisionQueue

    assert manager_core.may_execute('native_mcp_reload', proven_safe=True, reversible=True, tested=True) is False
    assert protected_action_kind('Herstart native MCP voor de nieuwe runtime') == 'native_mcp_reload'
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    approval = ConversationApprovalCoordinator(tmp_path / 'challenges.json', decisions)
    result = approval.request(
        action='native_mcp_reload',
        parameters={'target':'energie-filesystem-mcp'},
        source_channel='chatgpt',
    )
    assert result['status'] == 'confirmation_required'
    decision = decisions.get(result['challenge']['decision_id'])
    assert decision['kind'] == 'PRODUCTION_RESTART'


def test_project_cr_hotfix_reports_quarantine_not_false_delete():
    source = (TOOLS / 'cr_standard_native_mcp_hotfix.py').read_text()
    assert 'retention_quarantined' in source
    assert 'retention_delete_performed' in source


def test_protected_reload_can_finalize_after_runtime_guard_already_green(tmp_path):
    from projectmanager_v2.protected_action_executor import ProtectedActionExecutor

    class Store:
        def __init__(self): self.completed=[]
        def open_items(self): return [action]
        def complete(self, item_id, *, result): self.completed.append((item_id, result))
    class Commands:
        def __init__(self): self.completed=[]
        def get(self, item_id): return command
        def complete(self, item_id, *, result): self.completed.append((item_id, result))
    class Decisions:
        def get(self, item_id): return decision

    root=tmp_path/'EnergieProject'
    (root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.4.42\n')
    runtime=root/'Inbox/native_mcp_runtime'; runtime.mkdir(parents=True)
    action={'id':'action-green','action':'native_mcp_reload','command_id':'cmd','decision_id':'dec'}
    command={'id':'cmd','intent':'native_mcp_reload','release_version':'32.4.42','approval_decision_id':'dec'}
    decision={
        'id':'dec','status':'APPROVED','approved_by':'Peter','kind':'PRODUCTION_RESTART',
        'context': {'command_id':'cmd','intent':'native_mcp_reload','release_version':'32.4.42'},
    }
    request_id=hashlib.sha256(action['id'].encode()).hexdigest()[:32]
    fingerprint='f'*64
    runtime.joinpath('runtime_guard.json').write_text(json.dumps({
        'status':'GREEN','ready':True,'reload_required':False,
        'expected_fingerprint':fingerprint,'runtime_fingerprint':fingerprint,
    }))
    runtime.joinpath('reload_result.json').write_text(json.dumps({
        'schema':'energie_native_mcp_reload_result_v1','request_id':request_id,
        'status':'GREEN','ok':True,'container':'energie-filesystem-mcp',
        'expected_fingerprint':fingerprint,'runtime_fingerprint':fingerprint,
        'restart_performed':True,
    }))
    actions=Store(); commands=Commands()
    result=ProtectedActionExecutor(root, actions, commands, Decisions()).run_once()
    assert result[0]['runtime_green'] is True
    assert len(actions.completed)==1 and len(commands.completed)==1


def test_native_mcp_reload_executor_rejects_request_without_peter_approval(tmp_path, monkeypatch):
    import native_mcp_reload_executor as executor
    root=tmp_path/'EnergieProject'
    request=root/'Inbox/native_mcp_runtime/reload_request.json'; request.parent.mkdir(parents=True)
    request.write_text(json.dumps({
        'schema':'energie_native_mcp_reload_request_v1','request_id':'a'*32,
        'expected_fingerprint':'b'*64,'operation':'restart_exact_energie_filesystem_mcp',
        'approved_by':'Mallory','decision_id':'decision',
    }))
    called={'restart':False}
    monkeypatch.setattr(executor,'_restart',lambda: called.__setitem__('restart',True))
    with pytest.raises(RuntimeError, match='approval'):
        executor.run(root,wait_seconds=1)
    assert called['restart'] is False
