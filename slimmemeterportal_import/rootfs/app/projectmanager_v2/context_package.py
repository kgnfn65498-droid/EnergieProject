from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

_ALWAYS_REQUIREMENTS = (
    "HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md",
    "HARD_REQUIREMENT_STABLE_DEVELOPMENT_METHOD.md",
    "HARD_REQUIREMENT_SILENT_DEVELOPMENT_MODE_20260913.md",
    "HARD_REQUIREMENT_UNIFIED_DEVELOPMENT_LEDGER.md",
    "HARD_REQUIREMENT_PROACTIVE_PM_KB_HANDOVER_TRUTH.md",
)

def _read(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file() or path.is_symlink():
        return {"path": relative, "status": "MISSING", "sha256": "", "content": ""}
    data = path.read_bytes()
    try:
        content = data.decode("utf-8")
    except UnicodeDecodeError:
        return {"path": relative, "status": "UNREADABLE", "sha256": hashlib.sha256(data).hexdigest(), "content": ""}
    return {"path": relative, "status": "GREEN", "sha256": hashlib.sha256(data).hexdigest(), "content": content}

def _tokens(value: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9_.-]{4,}", value.lower()) if not t.isdigit()}

def _select_requirements(root: Path, requirements: list[str], task_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    task_tokens = _tokens(task_text)
    mandatory: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for relative in requirements:
        name = Path(relative).name
        item = _read(root, relative)
        name_tokens = _tokens(name.replace("hard_requirement_", ""))
        always = name in _ALWAYS_REQUIREMENTS
        relevant = bool(task_tokens.intersection(name_tokens))
        if always or relevant:
            mandatory.append(item)
        else:
            evidence.append({"path": relative, "status": item["status"], "sha256": item["sha256"]})
    return mandatory, evidence

def build_context_package(
    project_root: Path | str,
    *,
    status: dict[str, Any],
    source_paths: dict[str, str],
    requirements: list[str],
    full_kb: dict[str, Any],
    truth: dict[str, Any],
) -> dict[str, Any]:
    root = Path(project_root)
    active = status.get("active_task") if isinstance(status.get("active_task"), dict) else {}
    task_text = " ".join(str(active.get(k) or "") for k in ("title", "goal", "next_action"))
    mandatory_requirements, deferred_requirements = _select_requirements(root, requirements, task_text)

    core_names = ("master_index", "active_context", "ledger_current_truth", "spock_context", "current_handover")
    core_sources = [_read(root, source_paths[name]) for name in core_names if source_paths.get(name)]
    missing = [item["path"] for item in core_sources + mandatory_requirements if item["status"] != "GREEN"]

    checkpoint = full_kb.get("checkpoint") if isinstance(full_kb.get("checkpoint"), dict) else {}
    conflicts = list(truth.get("conflicts") or [])
    complete = not missing and truth.get("status") == "GREEN" and truth.get("fail_closed") is not True

    package = {
        "schema": "energie_pm_context_package_v1",
        "inventory_complete": full_kb.get("complete") is True,
        "mandatory_context_complete": complete,
        "delivery_recorded": False,
        "behavior_evaluation_passed": False,
        "current_truth": {
            "live_release": truth.get("live_release") or str((status.get("release") or {}).get("version") or ""),
            "highest_checkpoint": checkpoint.get("path") or truth.get("highest_checkpoint") or "",
            "truth_status": truth.get("status"),
        },
        "active_task": {
            "id": active.get("id"),
            "title": active.get("title"),
            "status": active.get("status"),
            "step": active.get("step"),
            "steps_total": active.get("steps_total"),
            "first_unproven_action": active.get("next_action") or status.get("next_action") or "",
            "blockers": list(active.get("blockers") or []),
        },
        "mandatory_sources": core_sources,
        "mandatory_requirements": mandatory_requirements,
        "task_evidence": deferred_requirements,
        "forbidden_shortcuts": [
            "do_not_treat_history_as_current_truth",
            "do_not_repeat_proven_work_without_invalidating_evidence",
            "do_not_replace_mandatory_core_with_retrieval",
            "do_not_create_parallel_truth_store",
        ],
        "conflicts_missing_evidence": {"conflicts": conflicts, "missing": missing},
        "resume_contract": {
            "command": "verder",
            "deterministic": True,
            "first_unproven_action": active.get("next_action") or status.get("next_action") or "",
            "broad_history_scan_default": False,
            "fail_closed": not complete,
        },
    }
    digest_material = repr(package).encode("utf-8")
    package["package_sha256"] = hashlib.sha256(digest_material).hexdigest()
    return package
