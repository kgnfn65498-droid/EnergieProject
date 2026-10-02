from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
PM = APP / "projectmanager_v2"
TOOLS = ROOT / "tools"
for value in (str(APP), str(PM), str(TOOLS)):
    if value not in sys.path:
        sys.path.insert(0, value)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_32531_shared_pm_writer_directories_are_sticky_not_world_replaceable(tmp_path):
    from pm_shared_writer_contract import normalize_pm_shared_writer_contract

    result = normalize_pm_shared_writer_contract(tmp_path)
    assert result["status"] == "GREEN"
    assert result["directory_mode"] == "1777"
    for relative in result["directories"]:
        assert (tmp_path / relative).stat().st_mode & 0o7777 == 0o1777


def _seed_live_acceptance(root: Path) -> tuple[dict, str]:
    (root / "App").mkdir(parents=True)
    (root / "App/VERSIE.txt").write_text("32.5.31\n", encoding="utf-8")
    artifact = root / "Data/03_Systeem/Projectmanager/ReleaseArtifacts/EnergieProject_v32.5.31.zip"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"exact-32531-artifact")
    digest = _sha(artifact)
    _write_json(root / "Data/03_Systeem/Projectmanager/ReleaseController/current.json", {
        "status": "COMPLETE", "phase": "COMPLETE", "step": 9, "total": 9,
        "to_version": "32.5.31", "from_version": "32.5.30",
        "release_id": "32.5.31:test", "generation": "g31",
        "artifact_name": artifact.name, "artifact_sha256": digest,
    })
    _write_json(root / "Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json", {
        "state": "ACCEPTED", "from_version": "32.5.30", "to_version": "32.5.31",
        "artifact_sha256": digest, "rollback_path": "App.__rollback_32.5.30",
    })
    _write_json(root / "Inbox/ha_runtime/current.json", {
        "schema": "energie_ha_runtime_v1", "version": "32.5.31",
    })
    status = {"release": {"version": "32.5.31", "active_verified": True}}
    return status, digest


def test_32531_accepted_live_requires_exact_release_atomic_ha_and_artifact_truth(tmp_path):
    from development_handover_sync import reconcile_accepted_live

    status, digest = _seed_live_acceptance(tmp_path)
    accepted = reconcile_accepted_live(tmp_path, status)
    assert accepted is not None
    payload = accepted["payload"]
    assert payload["schema"] == "energie_accepted_live_checkpoint_v1"
    assert payload["status"] == "ACCEPTED_LIVE"
    assert payload["live_release"] == payload["target_release"] == "32.5.31"
    assert payload["from_version"] == "32.5.30"
    assert payload["artifact_sha256"] == digest
    assert payload["ha_runtime_version"] == "32.5.31"
    checkpoint = tmp_path / accepted["path"]
    assert checkpoint.stat().st_mode & 0o777 == 0o644

    first_sha = _sha(checkpoint)
    again = reconcile_accepted_live(tmp_path, status)
    assert again is not None and again["path"] == accepted["path"]
    assert _sha(checkpoint) == first_sha

    (tmp_path / "Inbox/ha_runtime/current.json").unlink()
    assert reconcile_accepted_live(tmp_path, status) is None


def test_32531_current_pointer_fails_closed_instead_of_promoting_history(tmp_path):
    from development_context_enforcement import highest_checkpoint

    (tmp_path / "App").mkdir()
    (tmp_path / "App/VERSIE.txt").write_text("32.5.31\n", encoding="utf-8")
    historical = tmp_path / "Data/03_Systeem/Projectmanager/ClearUp/State/CHECKPOINT_HISTORY.json"
    _write_json(historical, {
        "schema": "history", "checkpoint_sequence": 9999999, "status": "READY_FOR_NEW_CHAT",
        "live_release": "32.5.30", "target_release": "32.5.31",
    })
    missing = highest_checkpoint(tmp_path)
    assert missing["status"] == "RED"
    assert missing["path"] == ""
    assert "current_pointer_missing_corrupt_or_stale" in missing["reasons"]

    current = tmp_path / "Data/03_Systeem/Projectmanager/ClearUp/State/CHECKPOINT_32.5.31_ACCEPTED_LIVE.json"
    _write_json(current, {
        "schema": "energie_accepted_live_checkpoint_v1",
        "checkpoint_sequence": 3253199, "status": "ACCEPTED_LIVE",
        "live_release": "32.5.31", "target_release": "32.5.31",
    })
    raw = current.read_bytes()
    pointer = tmp_path / "Data/03_Systeem/Projectmanager/Handover/CURRENT_CHAT_SWITCH_POINTER.json"
    _write_json(pointer, {
        "schema": "energie_current_chat_switch_pointer_v2",
        "checkpoint": current.relative_to(tmp_path).as_posix(),
        "checkpoint_sha256": hashlib.sha256(raw).hexdigest(),
    })
    pointed = highest_checkpoint(tmp_path)
    assert pointed["status"] == "GREEN"
    assert pointed["path"] == current.relative_to(tmp_path).as_posix()
    assert pointed["ranking_basis"] == "current_chat_switch_pointer"


def test_32531_terminal_instruction_is_capability_blocked_even_with_old_proof_fields():
    from development_build_contract import evaluate_build_contract

    task = {
        "build_contract_required": True,
        "steps_total": 1,
        "build_metadata": {
            "thinking_level": "HOOG",
            "release_version": "32.5.31",
            "estimated_total_seconds": 60,
            "estimated_test_verification_seconds": 30,
            "step_estimates_seconds": [60],
            "original_estimate_recorded_at": "2026-10-02T00:00:00Z",
            "terminal_instruction": {
                "required": True,
                "terminal": "QNAP host",
                "step_label": "Stap 1/1",
                "expected_duration_seconds": 10,
                "max_wait_seconds": 60,
                "success_marker": "GREEN",
                "stop_marker": "RED",
                "return_required": "output",
                "reason": "missing capability",
                "rollback": "none",
                "reversible": True,
                "side_effects": [],
                "command_sha256": "a" * 64,
            },
        },
    }
    result = evaluate_build_contract(task, {})
    assert result["compliant"] is False
    assert result["terminal_compliant"] is False
    assert result["terminal_instruction"]["capability_status"] == "CAPABILITY_BLOCKED"
    assert "user_terminal_forbidden" in result["terminal_instruction"]["proof_missing"]


def test_32531_runtime_rollback_uses_current_atomic_transaction(tmp_path):
    from runtime_sources import RuntimeCollector

    (tmp_path / "App").mkdir()
    (tmp_path / "App/VERSIE.txt").write_text("32.5.31\n", encoding="utf-8")
    for version in ("32.4.52", "32.5.30"):
        rollback = tmp_path / f"App.__rollback_{version}"
        rollback.mkdir()
        (rollback / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    _write_json(tmp_path / "Inbox/atomic_app_swap_state.json", {
        "state": "ACCEPTED", "from_version": "32.5.30", "to_version": "32.5.31",
        "rollback_path": "App.__rollback_32.5.30", "artifact_sha256": "a" * 64,
    })
    result = RuntimeCollector(tmp_path, running_release_version="32.5.31").collect()
    assert result["release"]["rollback_version"] == "32.5.30"
    assert result["release"]["rollback_version_source"] == "atomic_accepted_transaction"
    assert "32.4.52" in result["release"]["rollback_versions"]


def test_32531_context_content_is_independent_from_self_audit_and_delivery_is_bounded(tmp_path):
    from context_package import MAX_PACKAGE_BYTES, build_context_package

    source_paths = {
        "master_index": "kb/master.md",
        "active_context": "kb/active.md",
        "manifest": "kb/manifest.md",
        "ledger_current_truth": "kb/ledger.md",
        "spock_context": "kb/spock.md",
        "current_handover": "kb/handover.md",
    }
    long_text = "mandatory current truth " + ("x" * 3800)
    for relative in source_paths.values():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(long_text, encoding="utf-8")
    requirements = [
        "requirements/HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md",
        "requirements/HARD_REQUIREMENT_STABLE_DEVELOPMENT_METHOD.md",
        "requirements/HARD_REQUIREMENT_SILENT_DEVELOPMENT_MODE_20260913.md",
        "requirements/HARD_REQUIREMENT_UNIFIED_DEVELOPMENT_LEDGER.md",
        "requirements/HARD_REQUIREMENT_PROACTIVE_PM_KB_HANDOVER_TRUTH.md",
        "requirements/HARD_REQUIREMENT_NO_USER_TERMINAL.md",
    ]
    for relative in requirements:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(long_text, encoding="utf-8")
    artifact = tmp_path / "artifact.zip"
    artifact.write_bytes(b"artifact-identity")
    status = {
        "release": {"version": "32.5.31"},
        "active_task": {
            "id": "t31", "title": "resume 32.5.31", "goal": "deterministic context",
            "status": "ACTIVE", "step": 1, "steps_total": 3,
            "next_action": "clean new-chat/verder acceptance", "blockers": [],
        },
        "self_audit": {"status": "RED", "invalid": [{"reason": "independent downstream audit"}]},
    }
    full = {"complete": True, "checkpoint": {"path": "checkpoint.json"}}
    truth = {
        "status": "GREEN", "fail_closed": False, "live_release": "32.5.31",
        "highest_checkpoint": "checkpoint.json",
        "first_unproven_action": "clean new-chat/verder acceptance",
        "governing_claims": {
            "target_release": "32.5.31", "artifact": "artifact.zip",
            "artifact_sha256": _sha(artifact), "artifact_size": artifact.stat().st_size,
            "first_unproven_action": "clean new-chat/verder acceptance",
        },
        "conflicts": [],
    }
    package = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    assert package["mandatory_context_complete"] is True
    assert package["resume_contract"]["fail_closed"] is False
    assert package["delivery_within_budget"] is True
    assert package["package_bytes"] <= MAX_PACKAGE_BYTES
    canonical = json.dumps(package, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert len(canonical) == package["package_bytes"]
