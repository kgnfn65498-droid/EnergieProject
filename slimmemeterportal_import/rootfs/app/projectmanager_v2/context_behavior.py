from __future__ import annotations

from typing import Any

SCHEMA = "energie_pm_context_behavior_evaluation_v1"

def evaluate_behavior(package: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
    expected_truth = package.get("current_truth") if isinstance(package.get("current_truth"), dict) else {}
    expected_task = package.get("active_task") if isinstance(package.get("active_task"), dict) else {}
    expected_resume = package.get("resume_contract") if isinstance(package.get("resume_contract"), dict) else {}
    checks = []

    def check(name: str, expected, actual):
        ok = expected == actual
        checks.append({"name": name, "status": "GREEN" if ok else "RED", "expected": expected, "actual": actual})
        return ok

    check("live_release", expected_truth.get("live_release"), observed.get("live_release"))
    check("highest_checkpoint", expected_truth.get("highest_checkpoint"), observed.get("highest_checkpoint"))
    check("first_unproven_action", expected_resume.get("first_unproven_action"), observed.get("first_unproven_action"))

    expected_blockers = list(expected_task.get("blockers") or [])
    actual_blockers = list(observed.get("blockers") or [])
    check("blockers", expected_blockers, actual_blockers)

    repeated = list(observed.get("repeated_proven_actions") or [])
    forbidden = list(observed.get("forbidden_actions") or [])
    checks.append({"name": "no_repeated_proven_work", "status": "GREEN" if not repeated else "RED", "actual": repeated})
    checks.append({"name": "no_forbidden_route", "status": "GREEN" if not forbidden else "RED", "actual": forbidden})

    if expected_resume.get("fail_closed") is True:
        blocked = observed.get("blocked") is True
        checks.append({"name": "fail_closed_observed", "status": "GREEN" if blocked else "RED", "actual": blocked})

    green = all(item.get("status") == "GREEN" for item in checks)
    return {
        "schema": SCHEMA,
        "behavior_evaluation_passed": green,
        "package_sha256": package.get("package_sha256") or "",
        "invocation_id": observed.get("invocation_id") or "",
        "checks": checks,
    }
