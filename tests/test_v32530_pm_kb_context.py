import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))

from context_delivery import build_delivery_receipt
from context_package import build_context_package
from projectmanager_api import ProjectmanagerAPI


def _write(root, relative, text="verplicht current"):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _fixture(tmp_path):
    source_paths = {
        "master_index": "kb/00_MASTER_DEVELOPMENT_INDEX.md",
        "active_context": "kb/00_ACTIVE_DEVELOPMENT_CONTEXT.md",
        "manifest": "kb/00_DEVELOPMENT_MANIFEST.md",
        "ledger_current_truth": "kb/01A_LEDGER_CURRENT_TRUTH.md",
        "spock_context": "kb/04_SPOCK_CONTEXT.md",
        "current_handover": "handover/CURRENT_DEVELOPMENT_HANDOVER.md",
    }
    for path in source_paths.values():
        _write(tmp_path, path)
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
        _write(tmp_path, path, "harde regel verplicht " + path)
    _write(
        tmp_path,
        "Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/23_context_hot.md",
        "# HOT context lesson\nStatus: HOT totdat E2E bewezen is\n\nProjectmanager knowledge index verplicht current preventieregel.",
    )
    status = {
        "release": {"version": "32.5.29"},
        "active_task": {
            "id": "t1",
            "title": "Projectmanager knowledge index",
            "goal": "deterministische context",
            "status": "ACTIVE",
            "step": 1,
            "steps_total": 3,
            "next_action": "continue index context",
            "blockers": [],
        },
        "self_audit": {"status": "GREEN", "invalid": []},
    }
    full = {"complete": True, "checkpoint": {"path": "checkpoint.json"}}
    truth = {
        "status": "GREEN",
        "fail_closed": False,
        "live_release": "32.5.29",
        "highest_checkpoint": "checkpoint.json",
        "first_unproven_action": "continue index context",
        "governing_claims": {"first_unproven_action": "continue index context"},
        "conflicts": [],
    }
    return source_paths, requirements, status, full, truth


def test_package_keeps_document_history_evidence_only(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    assert pkg["mandatory_context_complete"] is True
    assert pkg["authority_contract"]["documents"] == "supporting_evidence_only"
    assert all(item["authority"] == "supporting_evidence" for item in pkg["mandatory_sources"])
    assert all(item["authority"] == "binding_requirement" for item in pkg["mandatory_requirements"])


def test_missing_always_requirement_fails_closed(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    requirements = [p for p in requirements if not p.endswith("HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md")]
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    assert pkg["mandatory_context_complete"] is False
    assert pkg["resume_contract"]["fail_closed"] is True


def test_red_self_audit_blocks_resume(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    status["self_audit"] = {"status": "RED", "invalid": [{"reason": "broken"}]}
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    assert pkg["mandatory_context_complete"] is False
    assert pkg["resume_contract"]["fail_closed"] is True


def test_delivery_receipt_is_invocation_response_and_source_bound(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    delivered = {"schema": "test", "context_package": pkg, "state": "READY"}
    receipt = build_delivery_receipt(
        pkg, invocation_id="inv-1", consumer="chatgpt_mcp",
        project_root=tmp_path, delivered_payload=delivered
    )
    assert receipt["delivery_recorded"] is True
    assert receipt["mcp_response_boundary_verified"] is True
    assert receipt["boundary_proof_level"] == "MCP_RESPONSE_BOUND"
    (tmp_path / source_paths["master_index"]).write_text("changed", encoding="utf-8")
    changed = build_delivery_receipt(
        pkg, invocation_id="inv-2", consumer="chatgpt_mcp",
        project_root=tmp_path, delivered_payload=delivered
    )
    assert changed["delivery_recorded"] is False
    assert any(x.get("reason") == "source_hash_changed" for x in changed["source_validation"]["mismatches"])


def test_api_blocks_false_positive_preflight(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "status").mkdir(parents=True)
    (runtime / "handover").mkdir(parents=True)
    payload = {
        "new_chat_preflight": {"ready": True},
        "development_context": {
            "context_package": {
                "inventory_complete": True,
                "mandatory_context_complete": False,
                "resume_contract": {"fail_closed": True},
            }
        },
    }
    (runtime / "status/current.json").write_text(json.dumps(payload), encoding="utf-8")
    (runtime / "handover/current.json").write_text("{}", encoding="utf-8")
    api = ProjectmanagerAPI(runtime, project_root=tmp_path)
    result = api.resume_context()
    assert result["state"] == "BLOCKED"
    assert result["context_gate"]["preflight_ready"] is True
    assert result["context_gate"]["ready"] is False


def test_relevant_binding_hot_lesson_bypasses_optional_retrieval(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    assert pkg["mandatory_context_complete"] is True
    assert pkg["binding_hot_lessons"]
    assert all(item["authority"] == "binding_hot_lesson" for item in pkg["binding_hot_lessons"])


def test_supersession_cycle_fails_closed(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    truth["supersession_edges"] = [
        {"source": "current-A", "supersedes": "old-B"},
        {"source": "old-B", "supersedes": "current-A"},
    ]
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    assert pkg["mandatory_context_complete"] is False
    assert pkg["resume_contract"]["fail_closed"] is True
    assert any(x.get("kind") == "supersession_cycle" for x in pkg["conflicts_missing_evidence"]["conflicts"])


def test_caller_asserted_input_hash_never_claims_independent_delivery(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    receipt = build_delivery_receipt(
        pkg, invocation_id="inv-boundary", final_input_sha256="f" * 64,
        consumer="chatgpt", project_root=tmp_path
    )
    assert receipt["delivery_recorded"] is False
    assert receipt["actual_model_boundary_verified"] is False
    assert receipt["boundary_proof_level"] == "CALLER_ASSERTED_INPUT_HASH_UNPROVEN"
    assert receipt["reason"] == "caller_asserted_input_hash_is_not_independent_delivery_proof"
    assert len(receipt["truth_snapshot_sha256"]) == 64
    assert receipt["recorded_at"]
    assert "acceptance_note" in receipt


def test_api_delivery_receipt_is_blocked_when_context_gate_is_not_ready(tmp_path):
    runtime = tmp_path / "runtime"
    (runtime / "status").mkdir(parents=True)
    (runtime / "handover").mkdir(parents=True)
    payload = {
        "self_audit": {"status": "RED"},
        "new_chat_preflight": {"ready": True},
        "development_context": {
            "context_package": {
                "package_sha256": "a" * 64,
                "inventory_complete": True,
                "mandatory_context_complete": True,
                "resume_contract": {"fail_closed": False},
            }
        },
    }
    (runtime / "status/current.json").write_text(json.dumps(payload), encoding="utf-8")
    (runtime / "handover/current.json").write_text("{}", encoding="utf-8")
    api = ProjectmanagerAPI(runtime, project_root=tmp_path)
    receipt = api.delivery_receipt(
        invocation_id="inv-1", final_input_sha256="d" * 64, consumer="chatgpt"
    )
    assert receipt["delivery_recorded"] is False
    assert receipt["reason"] == "context_gate_not_ready"


def test_32530_artifact_identity_is_mandatory_and_size_bound(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    artifact = _write(tmp_path, "Inbox/processed/EnergieProject_v32.5.29.zip", "exact predecessor")
    raw = artifact.read_bytes()
    truth["governing_claims"].update({
        "target_release": "32.5.30",
        "artifact": "Inbox/processed/EnergieProject_v32.5.29.zip",
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "artifact_size": len(raw),
    })
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    assert pkg["mandatory_context_complete"] is True
    assert pkg["artifact_identity"]["bytes"] == len(raw)

    truth["governing_claims"]["artifact_size"] = len(raw) + 1
    bad = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    assert bad["mandatory_context_complete"] is False
    assert "artifact_identity:size_mismatch" in bad["conflicts_missing_evidence"]["missing"]


def test_delivery_receipt_revalidates_governing_artifact_bytes(tmp_path):
    source_paths, requirements, status, full, truth = _fixture(tmp_path)
    artifact = _write(tmp_path, "Inbox/processed/EnergieProject_v32.5.29.zip", "exact predecessor")
    raw = artifact.read_bytes()
    truth["governing_claims"].update({
        "target_release": "32.5.30",
        "artifact": "Inbox/processed/EnergieProject_v32.5.29.zip",
        "artifact_sha256": hashlib.sha256(raw).hexdigest(),
        "artifact_size": len(raw),
    })
    pkg = build_context_package(
        tmp_path, status=status, source_paths=source_paths, requirements=requirements,
        full_kb=full, truth=truth, capabilities={}
    )
    artifact.write_text("mutated predecessor", encoding="utf-8")
    receipt = build_delivery_receipt(
        pkg, invocation_id="inv-artifact", final_input_sha256="a" * 64,
        consumer="chatgpt", project_root=tmp_path
    )
    assert receipt["delivery_recorded"] is False
    assert any(
        x.get("path") == "Inbox/processed/EnergieProject_v32.5.29.zip"
        and x.get("reason") == "source_hash_changed"
        for x in receipt["source_validation"]["mismatches"]
    )
