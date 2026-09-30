from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "energie_pm_context_delivery_receipt_v2"

def _sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _validate_sources(package: dict[str, Any], project_root: Path | str | None) -> dict[str, Any]:
    if project_root is None:
        return {"status": "UNPROVEN", "current": False, "mismatches": [{"reason": "project_root_not_bound"}]}
    root = Path(project_root)
    rows = list(package.get("mandatory_sources") or []) + list(package.get("mandatory_requirements") or [])
    mismatches = []
    checked = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        relative = str(item.get("path") or "").strip()
        expected = str(item.get("sha256") or "").strip().lower()
        if not relative or len(expected) != 64:
            mismatches.append({"path": relative, "reason": "source_identity_incomplete"})
            continue
        path = root / relative
        if path.is_symlink() or not path.is_file():
            mismatches.append({"path": relative, "reason": "source_missing_or_unsafe"})
            continue
        try:
            current = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as exc:
            mismatches.append({"path": relative, "reason": type(exc).__name__})
            continue
        checked.append({"path": relative, "sha256": current})
        if current != expected:
            mismatches.append({"path": relative, "reason": "source_hash_changed", "expected": expected, "actual": current})
    return {
        "status": "GREEN" if rows and not mismatches and len(checked) == len(rows) else "RED",
        "current": bool(rows and not mismatches and len(checked) == len(rows)),
        "checked": checked,
        "mismatches": mismatches,
    }

def build_delivery_receipt(
    package: dict[str, Any],
    *,
    invocation_id: str,
    final_input_sha256: str,
    consumer: str,
    project_root: Path | str | None = None,
) -> dict[str, Any]:
    invocation_id = str(invocation_id or "").strip()
    final_input_sha256 = str(final_input_sha256 or "").strip().lower()
    consumer = str(consumer or "").strip()
    package_sha = str(package.get("package_sha256") or "").strip().lower()
    source_validation = _validate_sources(package, project_root)
    ready = bool(
        invocation_id
        and consumer
        and len(final_input_sha256) == 64
        and all(ch in "0123456789abcdef" for ch in final_input_sha256)
        and len(package_sha) == 64
        and package.get("mandatory_context_complete") is True
        and (package.get("resume_contract") or {}).get("fail_closed") is not True
        and source_validation.get("current") is True
    )
    receipt = {
        "schema": SCHEMA,
        "delivery_recorded": ready,
        "invocation_id": invocation_id,
        "consumer": consumer,
        "package_sha256": package_sha,
        "final_input_sha256": final_input_sha256,
        "compiler_version": package.get("compiler_version"),
        "mandatory_context_complete": package.get("mandatory_context_complete") is True,
        "source_validation": source_validation,
        "source_hashes": sorted(
            [
                {"path": x.get("path"), "sha256": x.get("sha256")}
                for x in list(package.get("mandatory_sources") or []) + list(package.get("mandatory_requirements") or [])
                if isinstance(x, dict) and x.get("path") and x.get("sha256")
            ],
            key=lambda x: str(x.get("path") or ""),
        ),
        "excluded_or_deferred": {
            "deferred_requirements": [x.get("path") for x in package.get("deferred_requirement_refs") or [] if isinstance(x, dict)],
            "optional_evidence_errors": list(package.get("optional_evidence_errors") or []),
        },
    }
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt
