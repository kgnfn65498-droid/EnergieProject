from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
for value in (str(TOOLS), str(APP), str(PM)):
    if value not in sys.path:
        sys.path.insert(0, value)

import root_cleanup_32530 as root_cleanup
import root_cleanup_executor_32530 as root_executor
from atomic_app_swap import SwapPaths


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _seed_release(root: Path) -> None:
    for rel in (
        "App/slimmemeterportal_import/rootfs/app/projectmanager_v2",
        "Backups", "Data", "Inbox/processing", "Inbox/incoming", "Inbox/processed", "Inbox/failed", "Infra",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)
    (root / "App/VERSIE.txt").write_text("32.5.30\n", encoding="utf-8")
    _write_json(root / "Inbox/release_controller/current.json", {
        "status": "COMPLETE", "phase": "COMPLETE", "to_version": "32.5.30",
    })
    _write_json(root / "Inbox/atomic_app_swap_state.json", {
        "state": "ACCEPTED",
        "from_version": "32.5.29",
        "to_version": "32.5.30",
        "rollback_path": "App.__rollback_32.5.29",
    })
    _write_json(root / "Inbox/ha_runtime/current.json", {"version": "32.5.30"})


def _rollback(root: Path, version: str) -> Path:
    path = root / f"App.__rollback_{version}"
    path.mkdir()
    (path / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    (path / "payload.txt").write_text("rollback-" + version, encoding="utf-8")
    return path


def _apply_request(plan: dict, recovery: dict) -> dict:
    return {
        "schema": root_cleanup.REQUEST_SCHEMA,
        "request_id": "a" * 32,
        "operation": "root_apply",
        "release_version": "32.5.30",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "explicit_user_approval": True,
        "plan": plan,
        "plan_sha256": plan["plan_sha256"],
        "recovery": recovery,
    }


def test_32530_atomic_swap_uses_canonical_rollback_only_for_new_contract():
    old = SwapPaths.for_release(Path("/energy"), "32.5.28", "32.5.29")
    new = SwapPaths.for_release(Path("/energy"), "32.5.29", "32.5.30")
    assert old.rollback == Path("/energy/App.__rollback_32.5.28")
    assert new.rollback == Path("/energy/Rollback/App.__rollback_32.5.29")


def test_32530_root_plan_migrates_keep_three_and_quarantines_excess(tmp_path: Path):
    root = tmp_path / "EnergieProject"
    _seed_release(root)
    for version in ("32.5.29", "32.5.28", "32.5.27", "32.5.26"):
        _rollback(root, version)
    legacy_clearup = root / "CLEARUP/old-run"
    legacy_clearup.mkdir(parents=True)
    (legacy_clearup / "manifest.json").write_text("{}\n", encoding="utf-8")
    (root / "EnergieProject_v32.5.28-old.zip").write_bytes(b"old-release")

    plan = root_cleanup.build_root_cleanup_plan(root)

    assert plan["status"] == "READY"
    assert plan["review_count"] == 0
    migrations = {x["source"]: x["target"] for x in plan["actions"] if x["kind"] == "migrate_rollback"}
    assert migrations == {
        "App.__rollback_32.5.29": "Rollback/App.__rollback_32.5.29",
        "App.__rollback_32.5.28": "Rollback/App.__rollback_32.5.28",
        "App.__rollback_32.5.27": "Rollback/App.__rollback_32.5.27",
    }
    quarantine = {x["source"] for x in plan["actions"] if x["kind"] == "quarantine"}
    assert "App.__rollback_32.5.26" in quarantine
    assert "EnergieProject_v32.5.28-old.zip" in quarantine
    assert any(x["kind"] == "migrate_legacy_clearup" and x["source"] == "CLEARUP" for x in plan["actions"])


def test_32530_root_apply_updates_atomic_path_and_restore_roundtrips(tmp_path: Path):
    root = tmp_path / "EnergieProject"
    _seed_release(root)
    for version in ("32.5.29", "32.5.28", "32.5.27", "32.5.26"):
        _rollback(root, version)
    legacy_clearup = root / "CLEARUP/old-run"
    legacy_clearup.mkdir(parents=True)
    (legacy_clearup / "manifest.json").write_text("{}\n", encoding="utf-8")

    plan = root_cleanup.build_root_cleanup_plan(root)
    recovery = {"required": False, "confirmed": True, "rollback_waiver": True}
    request_id, result = root_executor.execute(root, _apply_request(plan, recovery))

    assert request_id == "a" * 32
    assert result["status"] == "GREEN"
    run_id = result["run_id"]
    assert not list(root.glob("App.__rollback_*"))
    assert [p.name for p in sorted((root / "Rollback").glob("App.__rollback_*"))] == [
        "App.__rollback_32.5.27", "App.__rollback_32.5.28", "App.__rollback_32.5.29"
    ]
    assert not (root / "CLEARUP").exists()
    assert (root / root_cleanup.LEGACY_CLEARUP_TARGET_REL / "old-run/manifest.json").is_file()
    atomic = json.loads((root / "Inbox/atomic_app_swap_state.json").read_text(encoding="utf-8"))
    assert atomic["rollback_path"] == "Rollback/App.__rollback_32.5.29"

    restore_request = {
        "schema": root_cleanup.REQUEST_SCHEMA,
        "request_id": "b" * 32,
        "operation": "root_restore",
        "release_version": "32.5.30",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "explicit_user_approval": True,
        "run_id": run_id,
    }
    _rid, restored = root_executor.execute(root, restore_request)
    assert restored["status"] == "GREEN"
    assert all((root / f"App.__rollback_{v}").is_dir() for v in ("32.5.29", "32.5.28", "32.5.27", "32.5.26"))
    assert (root / "CLEARUP/old-run/manifest.json").is_file()
    atomic = json.loads((root / "Inbox/atomic_app_swap_state.json").read_text(encoding="utf-8"))
    assert atomic["rollback_path"] == "App.__rollback_32.5.29"


def test_32530_root_finalize_requires_recovery_for_nonrollback_debt(tmp_path: Path):
    root = tmp_path / "EnergieProject"
    _seed_release(root)
    for version in ("32.5.29", "32.5.28", "32.5.27", "32.5.26"):
        _rollback(root, version)
    recognized = root / "EnergieProject_v32.5.20-old.zip"
    recognized.write_bytes(b"release-debt")

    plan = root_cleanup.build_root_cleanup_plan(root)
    assert plan["recovery_required_count"] >= 1
    recovery_state = root_cleanup.prepare_root_recovery(root)
    assert recovery_state["status"] == "GREEN"
    confirm = root_cleanup.confirm_root_recovery(
        root,
        explicit_user_text=recovery_state["external_confirmation_required"],
        source="mcp_remote",
    )
    assert confirm["status"] == "GREEN"
    recovery = root_cleanup._recovery_proof(root, plan)
    _rid, applied = root_executor.execute(root, _apply_request(plan, recovery))

    finalize_request = {
        "schema": root_cleanup.REQUEST_SCHEMA,
        "request_id": "c" * 32,
        "operation": "root_finalize",
        "release_version": "32.5.30",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        "explicit_user_approval": True,
        "run_id": applied["run_id"],
    }
    _rid, final = root_executor.execute(root, finalize_request)
    assert final["status"] == "GREEN"
    assert final["delete_performed"] is True
    assert not recognized.exists()


def test_32530_root_plan_includes_failed_and_candidate_release_debt(tmp_path: Path):
    root = tmp_path / "EnergieProject"
    _seed_release(root)
    for version in ("32.5.29", "32.5.28", "32.5.27"):
        _rollback(root, version)
    failed = root / "App.__failed_32.5.25"
    candidate = root / "App.__candidate_32.5.31"
    failed.mkdir()
    candidate.mkdir()
    (failed / "payload.txt").write_text("failed", encoding="utf-8")
    (candidate / "payload.txt").write_text("candidate", encoding="utf-8")

    plan = root_cleanup.build_root_cleanup_plan(root)
    assert plan["status"] == "READY"
    by_source = {item["source"]: item for item in plan["actions"]}
    assert by_source["App.__failed_32.5.25"]["kind"] == "quarantine"
    assert by_source["App.__failed_32.5.25"]["recovery_required"] is True
    assert by_source["App.__candidate_32.5.31"]["kind"] == "quarantine"
    assert by_source["App.__candidate_32.5.31"]["recovery_required"] is True


def test_32530_root_plan_fails_closed_on_unclassified_root_item(tmp_path: Path):
    root = tmp_path / "EnergieProject"
    _seed_release(root)
    for version in ("32.5.29", "32.5.28", "32.5.27"):
        _rollback(root, version)
    (root / "mystery").mkdir()

    plan = root_cleanup.build_root_cleanup_plan(root)
    assert plan["status"] == "REVIEW_REQUIRED"
    assert any(
        item.get("kind") == "unclassified_root_item" and item.get("source") == "mystery"
        for item in plan["review"]
    )
