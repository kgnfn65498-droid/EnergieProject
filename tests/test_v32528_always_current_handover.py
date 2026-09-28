from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))


def _j(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _seed(root: Path) -> Path:
    (root / "App").mkdir(parents=True)
    (root / "App/VERSIE.txt").write_text("32.5.27\n", encoding="utf-8")
    cp = root / "Data/03_Systeem/Projectmanager/ClearUp/State/CHECKPOINT_32.5.28_TEST.json"
    _j(cp, {
        "schema": "test_checkpoint",
        "status": "TARGETED_GREEN_RELEASE_NOT_BUILT",
        "live_release": "32.5.27",
        "target_release": "32.5.28",
        "predecessor_artifact": "EnergieProject_v32.5.27.zip",
        "predecessor_sha256": "e" * 64,
        "completed": ["recovery targeted green", "release chain green"],
        "pending": ["full regression", "package"],
        "final_zip_exists": False,
        "live_cleanup_executed": False,
        "next_action": "implement automatic handover freshness",
    })
    return cp


def test_32528_sync_projects_checkpoint_to_one_generation_and_keeps_live_target_distinct(tmp_path):
    from development_context_enforcement import highest_checkpoint
    from development_handover_sync import sync_current_development_handover, evaluate_handover_freshness

    root = tmp_path / "p"
    _seed(root)
    cp = highest_checkpoint(root)
    result = sync_current_development_handover(root, {"release": {"version": "32.5.27"}}, checkpoint=cp)
    assert result["status"] == "GREEN"

    pointer = json.loads((root / "Data/03_Systeem/Projectmanager/Handover/CURRENT_CHAT_SWITCH_POINTER.json").read_text())
    handover = (root / "Data/03_Systeem/Projectmanager/Handover/CURRENT_DEVELOPMENT_HANDOVER.md").read_text()
    assert pointer["source_generation"] == result["source_generation"]
    assert pointer["live_release"] == "32.5.27"
    assert pointer["target_release"] == "32.5.28"
    assert pointer["release_ready"] is False
    assert "Live release: **32.5.27**" in handover
    assert "Target release: **32.5.28**" in handover
    assert f"HANDOVER_GENERATION:{result['source_generation']}" in handover
    assert evaluate_handover_freshness(root, checkpoint=highest_checkpoint(root))["status"] == "GREEN"


def test_32528_newer_checkpoint_makes_old_projection_red_until_resync(tmp_path):
    from development_context_enforcement import highest_checkpoint
    from development_handover_sync import sync_current_development_handover, evaluate_handover_freshness

    root = tmp_path / "p"
    first = _seed(root)
    sync_current_development_handover(root, {"release": {"version": "32.5.27"}}, checkpoint=highest_checkpoint(root))

    second = first.with_name("CHECKPOINT_32.5.28_NEWER.json")
    _j(second, {
        "schema": "test_checkpoint",
        "status": "REGRESSION_GREEN",
        "live_release": "32.5.27",
        "target_release": "32.5.28",
        "predecessor_artifact": "EnergieProject_v32.5.27.zip",
        "predecessor_sha256": "e" * 64,
        "completed": ["recovery", "release chain", "regression"],
        "pending": ["package"],
        "final_zip_exists": False,
        "live_cleanup_executed": False,
        "next_action": "package after remaining gates",
    })
    newer_ns = first.stat().st_mtime_ns + 2_000_000_000
    os.utime(second, ns=(newer_ns, newer_ns))

    stale = evaluate_handover_freshness(root, checkpoint=highest_checkpoint(root))
    assert stale["status"] == "RED"
    assert stale["fail_closed"] is True

    healed = sync_current_development_handover(root, {"release": {"version": "32.5.27"}}, checkpoint=highest_checkpoint(root))
    assert healed["status"] == "GREEN"
    assert evaluate_handover_freshness(root, checkpoint=highest_checkpoint(root))["status"] == "GREEN"


def test_32528_partial_generation_mismatch_is_red_and_next_sync_repairs_it(tmp_path):
    from development_context_enforcement import highest_checkpoint
    from development_handover_sync import sync_current_development_handover, evaluate_handover_freshness

    root = tmp_path / "p"
    _seed(root)
    cp = highest_checkpoint(root)
    sync_current_development_handover(root, {"release": {"version": "32.5.27"}}, checkpoint=cp)
    pointer_path = root / "Data/03_Systeem/Projectmanager/Handover/CURRENT_CHAT_SWITCH_POINTER.json"
    pointer = json.loads(pointer_path.read_text())
    pointer["source_generation"] = "0" * 64
    _j(pointer_path, pointer)

    broken = evaluate_handover_freshness(root, checkpoint=cp)
    assert broken["status"] == "RED"
    assert "pointer_generation_mismatch" in broken["reasons"]

    sync_current_development_handover(root, {"release": {"version": "32.5.27"}}, checkpoint=cp)
    assert evaluate_handover_freshness(root, checkpoint=cp)["status"] == "GREEN"


def test_32528_development_context_fail_closes_when_handover_is_stale(tmp_path):
    from development_context_enforcement import current_truth_reconciliation, highest_checkpoint

    root = tmp_path / "p"
    _seed(root)
    result = current_truth_reconciliation(root, {"release": {"version": "32.5.27"}})
    assert result["status"] == "RED"
    assert result["fail_closed"] is True
    assert any(row.get("kind") == "handover_freshness_conflict" for row in result["conflicts"])
    assert result["highest_checkpoint"] == highest_checkpoint(root)["path"]


def test_32528_manager_service_auto_syncs_static_handover_projection(tmp_path):
    from document_sync import ManagedDocumentSync
    from manager_service import ManagerService

    root = tmp_path / "p"
    _seed(root)
    runtime_root = root / "Data/03_Systeem/Projectmanager/RuntimeV2"
    runtime_root.mkdir(parents=True, exist_ok=True)

    class Config:
        project_root = str(root)
        reports_root = str(root / "Data/02_Output/Rapportages")

    service = ManagerService.__new__(ManagerService)
    service.config = Config()
    service.root = runtime_root
    service.document_sync = ManagedDocumentSync()
    service.issues = None
    service._sync_managed_documents = lambda _status: []
    service._sync_development_context_documents = lambda _status: []

    status = {
        "release": {"version": "32.5.27"},
        "development_build_contract": {"contract_version": "2026-09-11.v3", "process_rules": []},
    }
    result = service._sync_documents_best_effort(status)
    assert result["status"] == "GREEN"
    assert status["development_context"]["handover_sync"]["status"] == "GREEN"
    pointer = json.loads((root / "Data/03_Systeem/Projectmanager/Handover/CURRENT_CHAT_SWITCH_POINTER.json").read_text())
    assert pointer["target_release"] == "32.5.28"
    assert pointer["live_release"] == "32.5.27"
    assert pointer["release_ready"] is False
