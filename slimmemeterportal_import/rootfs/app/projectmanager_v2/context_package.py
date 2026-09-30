from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA = "energie_pm_context_package_v2"
COMPILER_VERSION = "2"
_ALWAYS = {
    "HARD_REQUIREMENT_NEW_CHAT_IMMEDIATE_RESUME.md",
    "HARD_REQUIREMENT_STABLE_DEVELOPMENT_METHOD.md",
    "HARD_REQUIREMENT_SILENT_DEVELOPMENT_MODE_20260913.md",
    "HARD_REQUIREMENT_UNIFIED_DEVELOPMENT_LEDGER.md",
    "HARD_REQUIREMENT_PROACTIVE_PM_KB_HANDOVER_TRUTH.md",
    "HARD_REQUIREMENT_NO_USER_TERMINAL.md",
}
_SCOPE_RULES = {
    "clearup": ("CLEARUP", "CAPABILITY_CONTINUITY", "DANGEROUS_COMMAND", "COMMAND_PROOF"),
    "cleanup": ("CLEARUP", "CAPABILITY_CONTINUITY", "DANGEROUS_COMMAND", "COMMAND_PROOF"),
    "capability": ("CAPABILITY_CONTINUITY", "MCP_TOOL_EXPOSURE"),
    "mcp": ("MCP_TOOL_EXPOSURE", "CAPABILITY_CONTINUITY"),
    "handover": ("ALWAYS_CURRENT_HANDOVER", "NEW_CHAT", "LIVE_HANDOVER"),
    "verder": ("NEW_CHAT", "ALWAYS_CURRENT_HANDOVER", "DEVELOPMENT_CONTINUITY"),
    "resume": ("NEW_CHAT", "ALWAYS_CURRENT_HANDOVER", "DEVELOPMENT_CONTINUITY"),
    "release": ("LIVE_RUNTIME_ACTIVATION", "NO_SPLIT_STATE", "RELEASE"),
    "recovery": ("RECOVERY", "DANGEROUS_COMMAND", "NO_USER_TERMINAL"),
}

def _canonical_sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _read_meta(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    if not path.is_file() or path.is_symlink():
        return {"path": relative, "status": "MISSING", "sha256": "", "bytes": 0}
    try:
        data = path.read_bytes()
    except OSError as exc:
        return {"path": relative, "status": "UNREADABLE", "sha256": "", "bytes": 0, "error": type(exc).__name__}
    return {"path": relative, "status": "GREEN" if data.strip() else "EMPTY", "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}

def _words(value: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", value.lower()) if len(w) >= 4}

def _required_names(task_text: str) -> set[str]:
    upper = task_text.upper()
    needles: set[str] = set()
    for key, scopes in _SCOPE_RULES.items():
        if key in task_text.lower():
            needles.update(scopes)
    return needles

def _select_requirements(root: Path, requirements: list[str], task_text: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    discovered = {Path(p).name: p for p in requirements}
    missing_always = sorted(name for name in _ALWAYS if name not in discovered)
    scopes = _required_names(task_text)
    task_words = _words(task_text)
    mandatory, deferred = [], []
    for name, relative in sorted(discovered.items()):
        meta = _read_meta(root, relative)
        upper = name.upper()
        scope_match = any(scope in upper for scope in scopes)
        lexical_match = bool(task_words.intersection(_words(name)))
        if name in _ALWAYS or scope_match or lexical_match:
            mandatory.append(meta)
        else:
            deferred.append(meta)
    return mandatory, deferred, missing_always

def build_context_package(project_root: Path | str, *, status: dict[str, Any], source_paths: dict[str, str], requirements: list[str], full_kb: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    root = Path(project_root)
    active = status.get("active_task") if isinstance(status.get("active_task"), dict) else {}
    task_text = " ".join(str(active.get(k) or "") for k in ("title", "goal", "next_action"))
    mandatory_requirements, deferred_requirements, missing_registry = _select_requirements(root, requirements, task_text)

    core_names = ("master_index", "active_context", "ledger_current_truth", "spock_context", "current_handover")
    missing_source_keys = [name for name in core_names if not source_paths.get(name)]
    core_sources = [_read_meta(root, source_paths[name]) for name in core_names if source_paths.get(name)]
    invalid = [x["path"] for x in core_sources + mandatory_requirements if x.get("status") != "GREEN"]
    invalid.extend("requirement:" + name for name in missing_registry)
    invalid.extend("source_key:" + name for name in missing_source_keys)

    conflicts = list(truth.get("conflicts") or [])
    first_action = str(active.get("next_action") or status.get("next_action") or "").strip()
    if not active or not first_action:
        invalid.append("active_task:first_unproven_action")

    self_audit = status.get("self_audit") if isinstance(status.get("self_audit"), dict) else {}
    blocking_audit = self_audit.get("status") == "RED"
    if blocking_audit:
        conflicts.append({"kind": "projectmanager_self_audit_red", "reasons": list(self_audit.get("reasons") or [])})

    complete = bool(
        full_kb.get("complete") is True
        and not invalid
        and not conflicts
        and truth.get("status") == "GREEN"
        and truth.get("fail_closed") is not True
    )
    checkpoint = full_kb.get("checkpoint") if isinstance(full_kb.get("checkpoint"), dict) else {}

    package = {
        "schema": SCHEMA,
        "compiler_version": COMPILER_VERSION,
        "inventory_complete": full_kb.get("complete") is True,
        "mandatory_context_complete": complete,
        "current_truth": {
            "live_release": truth.get("live_release") or str((status.get("release") or {}).get("version") or ""),
            "highest_checkpoint": checkpoint.get("path") or truth.get("highest_checkpoint") or "",
            "truth_status": truth.get("status"),
        },
        "active_task": {
            "id": active.get("id"), "title": active.get("title"), "status": active.get("status"),
            "step": active.get("step"), "steps_total": active.get("steps_total"),
            "first_unproven_action": first_action, "blockers": list(active.get("blockers") or []),
        },
        "mandatory_source_refs": core_sources,
        "mandatory_requirement_refs": mandatory_requirements,
        "task_evidence_refs": deferred_requirements,
        "conflicts_missing_evidence": {"conflicts": conflicts, "missing": sorted(set(invalid))},
        "resume_contract": {
            "command": "verder", "deterministic": complete,
            "first_unproven_action": first_action, "broad_history_scan_default": False,
            "fail_closed": not complete,
        },
    }
    package["package_sha256"] = _canonical_sha(package)
    return package
