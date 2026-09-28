from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
for p in (str(TOOLS), str(APP), str(PM)):
    if p not in sys.path:
        sys.path.insert(0, p)


def _w(path: Path, text: str = "x\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _j(path: Path, payload: dict):
    _w(path, json.dumps(payload, sort_keys=True) + "\n")


def _controller_complete(root: Path):
    _j(root / "Data/03_Systeem/Projectmanager/ReleaseController/current.json", {
        "status": "COMPLETE", "phase": "COMPLETE", "to_version": "32.5.26"
    })


def test_32526_failed_runtime_writers_are_flat(tmp_path):
    import release_controller_service as rcs
    import release_ingress_recovery as rir

    root = tmp_path / "p"
    _w(root / "App/VERSIE.txt", "32.5.26\n")
    (root / "Inbox/incoming").mkdir(parents=True)
    (root / "Inbox/failed").mkdir(parents=True)
    a = root / "Inbox/incoming/EnergieProject_v32.5.26.zip"
    b = root / "Inbox/incoming/EnergieProject_v32.5.26-copy.zip"
    a.write_bytes(b"a"); b.write_bytes(b"b")
    service = rcs.ReleaseControllerService(root, adapter=None)
    q = service._quarantine(a, "rejected", "preflight-rejected")
    assert q.parent == root / "Inbox/failed"
    assert ".preflight-rejected." in q.name
    service._deduplicate([b], selected_name="none")
    assert not any(p.is_dir() for p in (root / "Inbox/failed").iterdir())
    assert any(".duplicate." in p.name for p in (root / "Inbox/failed").iterdir())

    corrupt = root / "Inbox/incoming/EnergieProject_v32.5.27.zip"
    corrupt.write_bytes(b"not-a-zip")
    os.utime(corrupt, (1, 1))
    result = rir.quarantine_corrupt(root, corrupt.name, stale_seconds=30, now=1000)
    assert Path(result["quarantined"]).parent.as_posix() == "Inbox/failed"
    assert not (root / "Inbox/failed/corrupt").exists()


def test_32526_rolled_back_archive_is_flat(tmp_path):
    import release_controller_service as rcs
    root = tmp_path / "p"
    p = root / "Inbox/processing/EnergieProject_v32.5.26.zip"
    p.parent.mkdir(parents=True); p.write_bytes(b"z")
    service = rcs.ReleaseControllerService(root, adapter=None)
    service._settle_rolled_back(SimpleNamespace(artifact_name=p.name,to_version='32.5.26'))
    assert not p.exists()
    assert (root / "Inbox/failed/EnergieProject_v32.5.26.rolled_back.zip").is_file()
    assert not any(x.is_dir() for x in (root / "Inbox/failed").iterdir())
    assert (root / "Inbox/processing").is_dir()
    assert not any((root / "Inbox/processing").iterdir())


def test_32527_processing_is_permanent_and_empty_after_archive(tmp_path):
    import release_controller_service as rcs
    import release_ingress_recovery as rir
    from ha_delivery_adapter import HADelivery

    root = tmp_path / "p"
    (root / "Inbox/incoming").mkdir(parents=True)
    (root / "Inbox/failed").mkdir(parents=True)
    service = rcs.ReleaseControllerService(root, adapter=None)
    assert service._reconcile_idle_processing() is None
    assert (root / "Inbox/processing").is_dir()
    assert not any((root / "Inbox/processing").iterdir())

    rir.reconcile(root, stale_seconds=30, now=time.time())
    assert (root / "Inbox/processing").is_dir()
    assert not any((root / "Inbox/processing").iterdir())

    src = root / "Inbox/processing/EnergieProject_v32.5.26.zip"
    src.parent.mkdir(parents=True, exist_ok=True); src.write_bytes(b"owned")
    import hashlib
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    s = SimpleNamespace(artifact_name=src.name, artifact_sha256=sha)
    dst = HADelivery(root)._archive_complete(s)
    assert dst.is_file()
    assert (root / "Inbox/processing").is_dir()
    assert not any((root / "Inbox/processing").iterdir())

    publisher = (ROOT / "tools/nas_github_publisher.sh").read_text(encoding="utf-8")
    assert 'mkdir -p "$ROOT/Inbox" "$PROCESSING"' not in publisher


def test_32526_crash_cleanup_protocol_is_canonical_not_inbox():
    main = (APP / "main.py").read_text(encoding="utf-8")
    operating = (APP / "operating_mode_crash_recovery.py").read_text(encoding="utf-8")
    assert 'CRASH_RECOVERY_CLEANUP_ROOT = NAS_DATA_ROOT / "03_Systeem/Projectmanager/CrashRecovery/Cleanup"' in main
    assert 'CRASH_RECOVERY_CLEANUP_REQUEST_PATH = CRASH_RECOVERY_CLEANUP_ROOT / "request.json"' in main
    assert 'CRASH_RECOVERY_CLEANUP_RESULT_PATH = CRASH_RECOVERY_CLEANUP_ROOT / "result.json"' in main
    assert 'project_root / "Inbox/crash_recovery_cleanup_result.json"' not in operating
    assert 'Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup/result.json' in operating


def test_32526_publisher_lock_is_canonical_and_idle_does_not_create_processing():
    source = (ROOT / "tools/nas_github_publisher.sh").read_text(encoding="utf-8")
    assert 'LOCK="$ROOT/Data/03_Systeem/Projectmanager/Runtime/Locks/github-publisher.lock"' in source
    assert 'LOCK="$ROOT/Inbox/.github_publisher.lock"' not in source
    assert 'mkdir -p "$ROOT/Inbox" "$PROCESSING"' not in source


def _seed_final_cleanup(root: Path, *, unconsumed=False):
    _w(root / "App/VERSIE.txt", "32.5.26\n")
    _controller_complete(root)
    (root / "Inbox/incoming").mkdir(parents=True)
    (root / "Inbox/processed").mkdir(parents=True)
    (root / "Inbox/failed/corrupt").mkdir(parents=True)
    (root / "Inbox/failed/rejected").mkdir(parents=True)
    (root / "Inbox/failed/rolled_back").mkdir(parents=True)
    (root / "Inbox/failed/withdrawn").mkdir(parents=True)
    _w(root / "Inbox/failed/corrupt/a.corrupt.zip")
    _w(root / "Inbox/failed/rejected/b.preflight-rejected.zip")
    _w(root / "Inbox/failed/rolled_back/c.rolled_back.zip")
    _w(root / "Inbox/failed/withdrawn/d.superseded.zip")
    (root / "Inbox/release_hold_tmp").mkdir(parents=True)
    (root / "Inbox/processing").mkdir(parents=True)
    _j(root / "Inbox/crash_recovery_cleanup_result.json", {"schema": 1, "request_id": "old", "status": "ok"})
    _j(root / "Inbox/github_publication_state.pre_59_recovery.json", {"old": True})
    _j(root / "Inbox/ha_publication_required.json.corrective.22616", {"old": True})
    _j(root / "Inbox/ha_publication_required.json.settled.10928", {"old": True})
    (root / "Inbox/.github_publisher.lock").mkdir(parents=True)
    legacy_pm = root / "Inbox/projectmanager_v2"
    (legacy_pm / ".hold_32_4_11").mkdir(parents=True)
    _w(legacy_pm / "EnergieProject_v32.4.11_READY.zip")
    _w(legacy_pm / "EnergieProject_v32.4.11_READY.zip.sha256")
    _j(legacy_pm / "ApprovalIngress/abc.json", {"id": "abc"})
    receipts = {} if unconsumed else {"abc": {"status": "APPLIED"}}
    _j(root / "Data/03_Systeem/Projectmanager/RuntimeV2/decisions/approval_ingress_receipts.json", {"schema": 1, "items": receipts})
    (root / "Data/03_Systeem/Projectmanager/ApprovalIngress").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/Runtime/Locks").mkdir(parents=True)


def test_32526_final_inbox_cleanup_flattens_and_projectmanager_is_last(tmp_path, monkeypatch):
    import inbox_cleanup_32526 as cleanup
    import project_clearup_move_executor as executor
    from datetime import datetime, timedelta, timezone

    root = tmp_path / "p"
    _seed_final_cleanup(root)
    monkeypatch.setattr(cleanup, "_binding_contract", lambda _root: [])
    monkeypatch.setattr(executor, "_load_inbox_cleanup_service", lambda _root: cleanup)
    monkeypatch.setenv("ENERGIE_INBOX_CLEANUP_SOAK_SECONDS", "0")
    inv = cleanup.inventory_final_inbox_cleanup(root)
    assert inv["status"] == "READY"
    assert inv["projectmanager_v2_last"] is True
    plan = cleanup.build_cleanup_plan(root)
    assert plan["actions"][-1]["source"] == "Inbox/projectmanager_v2"
    request = {
        "schema": cleanup.SCOPED_REQUEST_SCHEMA,
        "request_id": "a" * 32,
        "operation": "scoped_apply",
        "release_version": "32.5.26",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        "explicit_user_approval": True,
        "plan": plan,
        "plan_sha256": plan["plan_sha256"],
    }
    _id, out = executor.execute_scoped_cleanup(root, request)
    assert out["status"] == "GREEN"
    failed = root / "Inbox/failed"
    assert sorted(p.name for p in failed.iterdir()) == [
        "a.corrupt.zip", "b.preflight-rejected.zip", "c.rolled_back.zip", "d.superseded.zip"
    ]
    assert not any(p.is_dir() for p in failed.iterdir())
    for rel in (
        "Inbox/release_hold_tmp", "Inbox/crash_recovery_cleanup_result.json",
        "Inbox/github_publication_state.pre_59_recovery.json",
        "Inbox/ha_publication_required.json.corrective.22616",
        "Inbox/ha_publication_required.json.settled.10928",
        "Inbox/.github_publisher.lock", "Inbox/projectmanager_v2",
    ):
        assert not (root / rel).exists(), rel
    assert (root / "Inbox/processing").is_dir()
    assert not any((root / "Inbox/processing").iterdir())
    assert out["processing_directory_present_and_empty"] is True
    assert out["projectmanager_v2_removed_last"] is True
    assert out["legacy_reappearance_proof"] == "GREEN"
    assert (root / out["manifest"]).is_file()
    assert out["privileged_executor"] == "project_clearup_move_executor.py"
    assert out["transport"] == "32.5.x request-scoped sideband"


def test_32526_embedded_cleanup_service_delegates_mutation_to_sideband(tmp_path, monkeypatch):
    import inbox_cleanup_32526 as cleanup
    root = tmp_path / "p"
    _seed_final_cleanup(root)
    monkeypatch.setattr(cleanup, "_binding_contract", lambda _root: [])
    plan = cleanup.build_cleanup_plan(root)
    called = {}
    def fake_call(_root, **kwargs):
        called.update(kwargs)
        return {"status": "GREEN", "run_id": "delegated", "delete_performed": False}
    monkeypatch.setattr(cleanup, "_watcher_call", fake_call)
    out = cleanup.apply_final_inbox_cleanup(
        root, explicit_user_text=plan["confirmation_required"], source="mcp_remote"
    )
    assert out["status"] == "GREEN"
    assert called["operation"] == "scoped_apply"
    assert called["explicit_approval"] is True
    assert called["plan"]["plan_sha256"] == plan["plan_sha256"]
    # The PM service itself must not have touched live Inbox paths.
    assert (root / "Inbox/projectmanager_v2").is_dir()
    assert (root / "Inbox/failed/corrupt").is_dir()


def test_32526_final_inbox_cleanup_blocks_unconsumed_legacy_approval(tmp_path, monkeypatch):
    import inbox_cleanup_32526 as cleanup
    root = tmp_path / "p"
    _seed_final_cleanup(root, unconsumed=True)
    monkeypatch.setattr(cleanup, "_binding_contract", lambda _root: [])
    inv = cleanup.inventory_final_inbox_cleanup(root)
    assert inv["status"] == "BLOCKED"
    assert inv["unconsumed_legacy_approvals"] == ["abc"]


def test_32526_projectmanager_writes_only_canonical_approval_ingress():
    web = (PM / "projectmanager_web.py").read_text(encoding="utf-8")
    cfg = (PM / "embedded_config.py").read_text(encoding="utf-8")
    assert "Data/03_Systeem/Projectmanager/ApprovalIngress" in web
    assert "Inbox/projectmanager_v2/ApprovalIngress" not in web
    assert "Inbox/projectmanager_v2/ApprovalIngress" not in cfg
    assert "Data/03_Systeem/Projectmanager/ApprovalIngress" in cfg


def test_32526_type3_is_original_rubric_not_generic_hygiene(tmp_path):
    import clearup_type3_service as type3
    root = tmp_path / "p"
    _w(root / "App/VERSIE.txt", "32.5.26\n")
    _controller_complete(root)
    # All Type-2 destinations except the remaining historical crash-result are present.
    for rel in (
        "Data/03_Systeem/Projectmanager/Runtime/Locks/nas-container-cr.operation.lock",
        "Data/03_Systeem/Projectmanager/Runtime/Locks/release-controller.lock",
        "Data/03_Systeem/Projectmanager/Runtime/Locks/release-transition.operation.lock",
        "Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher_heartbeat.v2",
        "Data/03_Systeem/Projectmanager/RuntimeEvidence/watcher.heartbeat.legacy",
        "Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json",
        "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publication_state.json",
        "Data/03_Systeem/Projectmanager/ReleaseController/Publication/github_publisher_state.json",
        "Data/03_Systeem/Projectmanager/CrashRecovery/ProjectLocal/result.json",
        "Data/03_Systeem/Projectmanager/CrashRecovery/NASContainerLocal/result.json",
        "Data/03_Systeem/Projectmanager/Runtime/Process/process_map.json",
    ):
        _w(root / rel)
    _w(root / "Inbox/crash_recovery_cleanup_result.json")
    inv = type3.inventory_type3(root)
    assert inv["classification"] == "TYPE3_ORIGINAL_RUBRIC"
    assert inv["item_count"] == 13
    assert inv["pending_legacy_sources"] == ["Inbox/crash_recovery_cleanup_result.json"]
    assert "unreviewed_hygiene_debt" not in json.dumps(inv)


def test_32526_command_processor_exposes_bounded_final_inbox_cleanup():
    source=(PM/'command_processor.py').read_text(encoding='utf-8')
    assert "inbox_cleanup_inventory" in source
    assert "inbox_cleanup_apply" in source
    assert "inbox_cleanup_restore" in source
    assert "apply_final_inbox_cleanup" in source
    assert "restore_final_inbox_cleanup" in source


def test_32527_post_live_audit_requires_processing_mailbox_present_and_empty():
    source=(ROOT/'tools/release_controller_service.py').read_text(encoding='utf-8')
    assert "'processing_directory_present_and_empty':" in source
    assert "'processing_directory_absent'" not in source


def test_32526_flat_failed_archive_is_not_generic_hygiene_debt(tmp_path):
    import project_hygiene
    import project_clearup
    root=tmp_path/'p'
    _w(root/'App/VERSIE.txt','32.5.26\n')
    (root/'Inbox/failed').mkdir(parents=True)
    _w(root/'Inbox/failed/old.preflight-rejected.zip')
    check=project_hygiene.project_hygiene_check(root,keep_rollbacks=3)
    assert 'Inbox/failed/old.preflight-rejected.zip' not in (check['details'].get('unreviewed_hygiene_debt') or [])
    plan=project_clearup.build_clearup_plan(root,current_version='32.5.26',keep_rollbacks=3)
    assert 'Inbox/failed/old.preflight-rejected.zip' not in {x['source_path'] for x in plan['items']}
    (root/'Inbox/failed/rejected').mkdir()
    check2=project_hygiene.project_hygiene_check(root,keep_rollbacks=3)
    assert 'Inbox/failed/rejected' in (check2['details'].get('unreviewed_hygiene_debt') or [])


def test_32526_sideband_accepts_request_scoped_type3_result_contract():
    source = (ROOT / "tools/sideband_bridge.py").read_text(encoding="utf-8")
    assert "energie_clearup_scoped_request_v1" in source
    assert "_REQUEST_SCOPED_SCHEMAS" in source
    assert "Data/03_Systeem/Projectmanager/ClearUp/Runtime/results" in source


def test_32526_scoped_executor_has_no_parallel_executor_path():
    executor = (ROOT / "tools/project_clearup_move_executor.py").read_text(encoding="utf-8")
    service = (PM / "inbox_cleanup_32526.py").read_text(encoding="utf-8")
    assert "SCOPED_CLEANUP_SCHEMA" in executor
    assert "execute_scoped_cleanup" in executor
    assert "project_clearup_move_request.json" in service
    assert "os.replace(source,target)" not in service.replace(" ", "")
    assert "shutil.rmtree" not in service


def test_32526_capability_registry_preserves_5series_provenance_and_forbids_32_4(tmp_path):
    from capability_registry import discover_capabilities
    root = tmp_path / "p"
    for rel in (
        "App/slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_chat_service.py",
        "App/slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_type2_service.py",
        "App/slimmemeterportal_import/rootfs/app/projectmanager_v2/clearup_type3_service.py",
        "App/slimmemeterportal_import/rootfs/app/projectmanager_v2/inbox_cleanup_32526.py",
        "App/slimmemeterportal_import/rootfs/app/project_clearup_auto.py",
        "App/tools/project_clearup_move_executor.py",
        "App/tools/sideband_bridge.py",
    ):
        _w(root / rel)
    reg = discover_capabilities(root)
    by_key = {row["key"]: row for row in reg["capabilities"]}
    assert by_key["clearup_type1"]["first_proven_release"] == "32.5.3"
    assert by_key["clearup_type2_002_012"]["request_scoped_from"] == "32.5.18/32.5.19"
    assert by_key["clearup_type3_final_inbox"]["status"] == "ACTIVE"
    assert by_key["project_clearup_auto_32_4"]["status"] == "FORBIDDEN_HISTORICAL"
    assert reg["must_consult_before_unavailable_conclusion"] is True
