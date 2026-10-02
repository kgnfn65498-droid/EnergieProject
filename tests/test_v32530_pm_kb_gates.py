import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))

from command_processor import CommandProcessor
from orchestrator import build_new_chat_preflight


def _development_context(*, mandatory=True):
    return {
        "full_kb": {
            "status": "COMPLETE",
            "complete": True,
            "checkpoint": {"path": "Data/03_Systeem/checkpoint.json"},
        },
        "truth_reconciliation": {"status": "GREEN", "fail_closed": False},
        "context_package": {
            "inventory_complete": True,
            "mandatory_context_complete": bool(mandatory),
            "package_sha256": "a" * 64,
            "resume_contract": {"fail_closed": not bool(mandatory)},
        },
        "master_index": "master.md",
        "active_context": "active.md",
        "ledger": "ledger.md",
        "ledger_current_truth": "truth.md",
        "decision_log": "decision.md",
        "development_changelog": "changes.md",
        "spock_context": "spock.md",
        "ticket_issue_index": "issues.md",
        "knowledgebase_inventory": "inventory.md",
        "requirements_count": 46,
    }


def test_new_chat_preflight_cannot_be_green_when_self_audit_is_red():
    status = {"release": {"version": "32.5.29"}, "self_audit": {"status": "RED"}}
    active = {"next_action": "continue first unproven action"}
    preflight = build_new_chat_preflight(status, _development_context(), active, [])
    assert preflight["ready"] is False
    assert preflight["manual_reexplanation_required"] is True
    assert preflight["self_audit_status"] == "RED"


def test_new_chat_preflight_requires_mandatory_context_package():
    status = {"release": {"version": "32.5.29"}, "self_audit": {"status": "GREEN"}}
    active = {"next_action": "continue first unproven action"}
    preflight = build_new_chat_preflight(status, _development_context(mandatory=False), active, [])
    assert preflight["ready"] is False
    assert preflight["mandatory_context_complete"] is False
    assert preflight["resume_fail_closed"] is True


def test_new_chat_preflight_green_when_all_independent_gates_are_green():
    status = {"release": {"version": "32.5.29"}, "self_audit": {"status": "GREEN"}}
    active = {"next_action": "continue first unproven action"}
    preflight = build_new_chat_preflight(status, _development_context(), active, [])
    assert preflight["ready"] is True
    assert preflight["manual_reexplanation_required"] is False


def test_32530_development_task_rejects_missing_build_contract():
    processor = CommandProcessor.__new__(CommandProcessor)
    item = {"release_version": "32.5.30", "steps_total": 7}
    with pytest.raises(RuntimeError, match="development_build_contract_required"):
        processor._build_metadata_for_task(item, mode="DEVELOPMENT")


def test_32530_development_task_accepts_complete_build_contract():
    processor = CommandProcessor.__new__(CommandProcessor)
    report = {
        "development_build_contract": {
            "thinking_level": "HOOG",
            "release_version": "32.5.30",
            "estimated_total_seconds": 7200,
            "estimated_test_verification_seconds": 1800,
            "step_estimates_seconds": [600, 1200, 1500, 1200, 900, 900, 900],
            "original_estimate_recorded_at": "2026-09-30T15:45:49+00:00",
            "terminal_instruction": {"required": False},
        }
    }
    item = {
        "release_version": "32.5.30",
        "steps_total": 7,
        "verification_report": json.dumps(report),
    }
    metadata = processor._build_metadata_for_task(item, mode="DEVELOPMENT")
    assert metadata["thinking_level"] == "HOOG"
    assert metadata["estimated_total_seconds"] == 7200
    assert len(metadata["step_estimates_seconds"]) == 7


def test_pre_32530_command_keeps_backward_compatibility():
    processor = CommandProcessor.__new__(CommandProcessor)
    item = {"release_version": "32.5.29", "steps_total": 1}
    assert processor._build_metadata_for_task(item, mode="DEVELOPMENT") is not None
