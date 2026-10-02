import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))

from self_audit import _stable_build_contract


def test_dynamic_elapsed_fields_do_not_create_handover_contract_mismatch():
    base = {
        "contract_version": "2026-09-11.v3",
        "thinking_level": "HOOG",
        "release_version": "32.5.30",
        "estimated_total_seconds": 7200,
        "estimated_test_verification_seconds": 1800,
        "step_estimates_seconds": [600, 1200, 1500, 1200, 900, 900, 900],
        "original_estimate_recorded_at": "2026-09-30T15:45:49+00:00",
        "required": True,
        "compliant": True,
        "missing": [],
        "terminal_compliant": True,
        "step": 1,
        "steps_total": 7,
    }
    status = dict(base, elapsed_seconds=100, estimated_remaining_seconds=7100)
    handover = dict(base, elapsed_seconds=101, estimated_remaining_seconds=7099)
    assert _stable_build_contract(status) == _stable_build_contract(handover)


def test_semantic_contract_change_is_detected():
    status = {
        "contract_version": "2026-09-11.v3",
        "thinking_level": "HOOG",
        "release_version": "32.5.30",
        "estimated_total_seconds": 7200,
        "estimated_test_verification_seconds": 1800,
        "step_estimates_seconds": [600, 1200],
        "original_estimate_recorded_at": "2026-09-30T15:45:49+00:00",
        "required": True,
        "compliant": True,
        "missing": [],
        "terminal_compliant": True,
        "step": 1,
        "steps_total": 2,
    }
    handover = dict(status, release_version="32.5.31")
    assert _stable_build_contract(status) != _stable_build_contract(handover)
