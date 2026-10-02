import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))

from context_package import build_context_package
from development_build_contract import evaluate_build_contract
from development_context_enforcement import highest_checkpoint
from development_handover_sync import reconcile_accepted_live


def _write(root, relative, text):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_32531_missing_pointer_fails_closed_without_historical_fallback(tmp_path):
    _write(tmp_path, "App/VERSIE.txt", "32.5.31\n")
    cp = {
        "schema": "energie_chat_switch_checkpoint_v2",
        "status": "READY_FOR_NEW_CHAT",
        "checkpoint_sequence": 3253101,
        "live_release": "32.5.31",
        "target_release": "32.5.31",
    }
    _write(
        tmp_path,
        "Data/03_Systeem/Projectmanager/ClearUp/State/CHECKPOINT_OLD.json",
        json.dumps(cp),
    )
    result = highest_checkpoint(tmp_path)
    assert result["status"] == "RED"
    assert result["path"] == ""
    assert "current_pointer_missing_corrupt_or_stale" in result["reasons"]


def test_32531_context_validity_does_not_depend_on_self_audit(tmp_path):
    source_paths = {
        "master_index": "kb/00_MASTER_DEVELOPMENT_INDEX.md",
        "active_context": "kb/00_ACTIVE_DEVELOPMENT_CONTEXT.md",
        "manifest": "kb/00_DEVELOPMENT_MANIFEST.md",
        "ledger_current_truth": "kb/01A_LEDGER_CURRENT_TRUTH.md",
        "spock_context": "kb/04_SPOCK_CONTEXT.md",
        "current_handover": "handover/CURRENT_DEVELOPMENT_HANDOVER.md",
    }
    for path in source_paths.values():
        _write(tmp_path, path, "mandatory current context")
    requirements = [
        "requirements/HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md",
        "requirements/HARD_REQUIREMENT_STABLE_DEVELOPMENT_METHOD.md",
        "requirements/HARD_REQUIREMENT_SILENT_DEVELOPMENT_MODE_20260913.md",
        "requirements/HARD_REQUIREMENT_UNIFIED_DEVELOPMENT_LEDGER.md",
        "requirements/HARD_REQUIREMENT_PROACTIVE_PM_KB_HANDOVER_TRUTH.md",
        "requirements/HARD_REQUIREMENT_NO_USER_TERMINAL.md",
        "requirements/HARD_REQUIREMENT_CLEARUP_END_TO_END_EXECUTION_PROOF.md",
    ]
    for path in requirements:
        _write(tmp_path, path, "binding requirement " + path)
    _write(
        tmp_path,
        "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/23_context_hot.md",
        "# HOT\nStatus: HOT totdat E2E bewezen is\npreventieregel current",
    )
    status = {
        "release": {"version": "32.5.31"},
        "active_task": {
            "id": "t1",
            "title": "closure",
            "goal": "deterministic context",
            "status": "ACTIVE",
            "step": 1,
            "steps_total": 3,
            "next_action": "continue",
            "blockers": [],
        },
        "self_audit": {"status": "RED", "invalid": [{"reason": "separate gate"}]},
    }
    full = {"complete": True, "checkpoint": {"path": "checkpoint.json"}}
    truth = {
        "status": "GREEN",
        "fail_closed": False,
        "live_release": "32.5.31",
        "highest_checkpoint": "checkpoint.json",
        "first_unproven_action": "continue",
        "governing_claims": {"first_unproven_action": "continue"},
        "conflicts": [],
    }
    pkg = build_context_package(
        tmp_path,
        status=status,
        source_paths=source_paths,
        requirements=requirements,
        full_kb=full,
        truth=truth,
        capabilities={},
    )
    assert pkg["mandatory_context_complete"] is True
    assert pkg["delivery_within_budget"] is True
    assert pkg["package_bytes"] <= 48000
    assert not any(
        item.get("kind") == "projectmanager_self_audit_red"
        for item in pkg["conflicts_missing_evidence"]["conflicts"]
    )


def test_32531_user_terminal_is_capability_blocked():
    result = evaluate_build_contract(
        {
            "release_version": "32.5.31",
            "terminal_instruction": {
                "required": True,
                "command": "sudo something",
                "risk": "manual",
                "why_needed": "missing capability",
                "expected_output": "ok",
                "success_criteria": "green",
            },
        }
    )
    terminal = result["terminal_instruction"]
    assert result["status"] == "RED"
    assert terminal["capability_status"] == "CAPABILITY_BLOCKED"
    assert terminal["proof_compliant"] is False
    assert terminal["compliant"] is False
    assert "user_terminal_forbidden" in terminal["proof_missing"]


def test_32531_accepted_live_requires_exact_ha_runtime(tmp_path):
    _write(tmp_path, "App/VERSIE.txt", "32.5.31\n")
    artifact = _write(
        tmp_path,
        "Data/03_Systeem/Projectmanager/ReleaseArtifacts/EnergieProject_v32.5.31.zip",
        "artifact-bytes",
    )
    import hashlib
    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    rc = {
        "status": "COMPLETE",
        "phase": "COMPLETE",
        "step": 9,
        "total": 9,
        "to_version": "32.5.31",
        "from_version": "32.5.30",
        "release_id": "r-1",
        "generation": "g-1",
        "artifact_name": artifact.name,
        "artifact_sha256": digest,
    }
    atomic = {
        "state": "ACCEPTED",
        "to_version": "32.5.31",
        "from_version": "32.5.30",
        "rollback_path": "App.__rollback_32.5.30",
        "artifact_sha256": digest,
    }
    _write(
        tmp_path,
        "Data/03_Systeem/Projectmanager/ReleaseController/current.json",
        json.dumps(rc),
    )
    _write(
        tmp_path,
        "Data/03_Systeem/Projectmanager/ReleaseController/State/atomic_app_swap_state.json",
        json.dumps(atomic),
    )
    _write(
        tmp_path,
        "Data/03_Systeem/Projectmanager/RuntimeEvidence/ha_runtime/current.json",
        json.dumps({"version": "32.5.30"}),
    )
    status = {"release": {"version": "32.5.31", "active_verified": True}}
    assert reconcile_accepted_live(tmp_path, status) is None
