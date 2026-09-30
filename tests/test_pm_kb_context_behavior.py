import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
sys.path.insert(0, str(PM))

from context_behavior import evaluate_behavior


def _package():
    return {
        "package_sha256": "a" * 64,
        "current_truth": {"live_release": "1.2.3", "highest_checkpoint": "cp.json"},
        "active_task": {"blockers": ["b1"]},
        "resume_contract": {"first_unproven_action": "do next", "fail_closed": False},
    }


def test_behavior_green_only_on_exact_resume_and_safe_trace():
    observed = {
        "invocation_id": "inv-1",
        "live_release": "1.2.3",
        "highest_checkpoint": "cp.json",
        "first_unproven_action": "do next",
        "blockers": ["b1"],
        "repeated_proven_actions": [],
        "forbidden_actions": [],
    }
    result = evaluate_behavior(_package(), observed)
    assert result["behavior_evaluation_passed"] is True


def test_behavior_red_when_model_repeats_proven_work():
    observed = {
        "invocation_id": "inv-1",
        "live_release": "1.2.3",
        "highest_checkpoint": "cp.json",
        "first_unproven_action": "do next",
        "blockers": ["b1"],
        "repeated_proven_actions": ["old green step"],
        "forbidden_actions": [],
    }
    result = evaluate_behavior(_package(), observed)
    assert result["behavior_evaluation_passed"] is False


def test_fail_closed_package_requires_blocked_behavior():
    package = _package()
    package["resume_contract"]["fail_closed"] = True
    observed = {
        "invocation_id": "inv-1",
        "live_release": "1.2.3",
        "highest_checkpoint": "cp.json",
        "first_unproven_action": "do next",
        "blockers": ["b1"],
        "repeated_proven_actions": [],
        "forbidden_actions": [],
        "blocked": False,
    }
    assert evaluate_behavior(package, observed)["behavior_evaluation_passed"] is False
