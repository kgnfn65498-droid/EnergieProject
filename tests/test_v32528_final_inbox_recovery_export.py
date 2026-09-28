from __future__ import annotations

import base64
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

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


def _seed(root: Path):
    _w(root / "App/VERSIE.txt", "32.5.28\n")
    _j(root / "Data/03_Systeem/Projectmanager/ReleaseController/current.json", {
        "status": "COMPLETE", "phase": "COMPLETE", "to_version": "32.5.28"
    })
    for rel in (
        "Inbox/incoming", "Inbox/processing", "Inbox/processed",
        "Data/03_Systeem/Projectmanager/ApprovalIngress",
        "Data/03_Systeem/Projectmanager/CrashRecovery/Cleanup",
        "Data/03_Systeem/Projectmanager/Runtime/Locks",
        "Data/03_Systeem/Projectmanager/RuntimeV2",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)
    for bucket, name in (
        ("corrupt", "a.corrupt.zip"), ("rejected", "b.preflight-rejected.zip"),
        ("rolled_back", "c.rolled_back.zip"), ("withdrawn", "d.superseded.zip"),
    ):
        _w(root / f"Inbox/failed/{bucket}/{name}", f"payload-{bucket}\n")
    (root / "Inbox/release_hold_tmp").mkdir(parents=True)
    _j(root / "Inbox/crash_recovery_cleanup_result.json", {"schema": 1, "status": "old"})
    _j(root / "Inbox/github_publication_state.pre_59_recovery.json", {"old": True})
    _j(root / "Inbox/ha_publication_required.json.corrective.22616", {"old": True})
    _j(root / "Inbox/ha_publication_required.json.settled.10928", {"old": True})
    (root / "Inbox/.github_publisher.lock").mkdir(parents=True)
    _w(root / "Inbox/projectmanager_v2/legacy.bin", "legacy-pm\n")
    _j(root / "Data/03_Systeem/Projectmanager/RuntimeV2/decisions/approval_ingress_receipts.json", {
        "schema": 1, "items": {}
    })


def test_32528_prepare_recovery_is_non_destructive_and_chunk_reconstructs(tmp_path, monkeypatch):
    import inbox_cleanup_32526 as cleanup

    root = tmp_path / "p"
    _seed(root)
    monkeypatch.setattr(cleanup, "_binding_contract", lambda _root: [])
    before = cleanup.build_cleanup_plan(root)
    source = root / "Inbox/failed/corrupt/a.corrupt.zip"
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()

    prepared = cleanup.prepare_final_inbox_recovery(root, source="mcp_remote")
    assert prepared["status"] == "GREEN"
    assert prepared["plan_sha256"] == before["plan_sha256"]
    assert prepared["deletion_performed"] is False
    assert source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == source_sha
    assert (root / "Inbox/projectmanager_v2").is_dir()
    assert (root / "Inbox/processing").is_dir() and not any((root / "Inbox/processing").iterdir())

    info = cleanup.final_inbox_recovery_export_info(root)
    assert info["status"] == "GREEN"
    assert info["plan_sha256"] == before["plan_sha256"]
    assert info["sha256"] == prepared["sha256"]

    chunks = []
    offset = 0
    while True:
        row = cleanup.final_inbox_recovery_export_chunk(root, offset=offset, max_bytes=97)
        raw = base64.b64decode(row["base64"])
        assert hashlib.sha256(raw).hexdigest() == row["chunk_sha256"]
        chunks.append(raw)
        offset = row["next_offset"]
        if row["eof"]:
            break
    archive = b"".join(chunks)
    assert hashlib.sha256(archive).hexdigest() == info["sha256"]
    copy = tmp_path / "copy.zip"
    copy.write_bytes(archive)
    with zipfile.ZipFile(copy) as zf:
        assert zf.testzip() is None
        manifest = json.loads(zf.read("RECOVERY_MANIFEST.json"))
    assert manifest["plan_sha256"] == before["plan_sha256"]
    assert manifest["deletion_performed"] is False


def test_32528_apply_requires_confirmed_external_recovery(tmp_path, monkeypatch):
    import inbox_cleanup_32526 as cleanup

    root = tmp_path / "p"
    _seed(root)
    monkeypatch.setattr(cleanup, "_binding_contract", lambda _root: [])
    prepared = cleanup.prepare_final_inbox_recovery(root, source="mcp_remote")
    plan = cleanup.build_cleanup_plan(root)

    blocked = cleanup.apply_final_inbox_cleanup(
        root, explicit_user_text=plan["confirmation_required"], source="mcp_remote"
    )
    assert blocked["status"] == "RECOVERY_CONFIRMATION_REQUIRED"
    assert blocked["executed"] is False

    confirmed = cleanup.confirm_final_inbox_recovery(
        root, explicit_user_text=prepared["external_confirmation_required"], source="mcp_remote"
    )
    assert confirmed["status"] == "GREEN"
    called = {}
    monkeypatch.setattr(cleanup, "_watcher_call", lambda _root, **kw: called.update(kw) or {"status": "GREEN", "run_id": "delegated"})
    out = cleanup.apply_final_inbox_cleanup(
        root, explicit_user_text=plan["confirmation_required"], source="mcp_remote"
    )
    assert out["status"] == "GREEN"
    assert called["operation"] == "scoped_apply"
    assert called["recovery"]["sha256"] == prepared["sha256"]
    assert called["recovery"]["plan_sha256"] == plan["plan_sha256"]


def test_32528_apply_blocks_source_mutation_after_recovery(tmp_path, monkeypatch):
    import inbox_cleanup_32526 as cleanup

    root = tmp_path / "p"
    _seed(root)
    monkeypatch.setattr(cleanup, "_binding_contract", lambda _root: [])
    prepared = cleanup.prepare_final_inbox_recovery(root, source="mcp_remote")
    cleanup.confirm_final_inbox_recovery(
        root, explicit_user_text=prepared["external_confirmation_required"], source="mcp_remote"
    )
    plan = cleanup.build_cleanup_plan(root)
    _w(root / "Inbox/failed/corrupt/a.corrupt.zip", "mutated-after-recovery\n")
    out = cleanup.apply_final_inbox_cleanup(
        root, explicit_user_text=plan["confirmation_required"], source="mcp_remote"
    )
    assert out["status"] == "RECOVERY_STALE"
    assert out["executed"] is False


def test_32528_scoped_executor_requires_matching_recovery_proof(tmp_path, monkeypatch):
    import inbox_cleanup_32526 as cleanup
    import project_clearup_move_executor as executor

    root = tmp_path / "p"
    _seed(root)
    monkeypatch.setattr(cleanup, "_binding_contract", lambda _root: [])
    monkeypatch.setattr(executor, "_load_inbox_cleanup_service", lambda _root: cleanup)
    prepared = cleanup.prepare_final_inbox_recovery(root, source="mcp_remote")
    cleanup.confirm_final_inbox_recovery(
        root, explicit_user_text=prepared["external_confirmation_required"], source="mcp_remote"
    )
    plan = cleanup.build_cleanup_plan(root)
    request = {
        "schema": cleanup.SCOPED_REQUEST_SCHEMA,
        "request_id": "a" * 32,
        "operation": "scoped_apply",
        "release_version": "32.5.28",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        "explicit_user_approval": True,
        "plan": plan,
        "plan_sha256": plan["plan_sha256"],
        "recovery": {"plan_sha256": plan["plan_sha256"], "sha256": "0" * 64},
    }
    with pytest.raises(executor.RequestRejected, match="recovery"):
        executor._scoped_cleanup_validate(root, request)


def test_32528_command_processor_routes_recovery_export_without_new_mcp_surface():
    source = (PM / "command_processor.py").read_text(encoding="utf-8")
    for token in (
        "inbox_cleanup_prepare_recovery", "inbox_cleanup_export_info",
        "inbox_cleanup_export_chunk", "inbox_cleanup_external_recovery_confirm",
    ):
        assert token in source
