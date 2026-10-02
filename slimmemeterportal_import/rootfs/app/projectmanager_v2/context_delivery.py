from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "energie_pm_context_delivery_receipt_v3"


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _valid_sha256(value: str) -> bool:
    value = str(value or "").strip().lower()
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def _delivery_sources(package: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    artifact = package.get("artifact_identity") if isinstance(package.get("artifact_identity"), dict) else {}
    collections = {
        "artifact_identity": [artifact] if artifact else [],
        "mandatory_sources": package.get("mandatory_sources") or [],
        "mandatory_requirements": package.get("mandatory_requirements") or [],
        "binding_hot_lessons": package.get("binding_hot_lessons") or [],
        "task_evidence": package.get("task_evidence") or [],
    }
    for collection, items in collections.items():
        for item in items:
            if not isinstance(item, dict):
                continue
            relative = str(item.get("path") or "").strip()
            expected = str(item.get("sha256") or "").strip().lower()
            if not relative or not expected:
                continue
            key = (relative, expected)
            if key in seen:
                continue
            seen.add(key)
            rows.append({"path": relative, "sha256": expected, "collection": collection})
    return rows


def validate_sources(package: dict[str, Any], project_root: Path | str | None) -> dict[str, Any]:
    if project_root is None:
        return {"status": "UNPROVEN", "current": False, "mismatches": [{"reason": "project_root_not_bound"}]}
    root = Path(project_root)
    rows = _delivery_sources(package)
    mismatches: list[dict[str, Any]] = []
    checked: list[dict[str, Any]] = []
    for item in rows:
        relative = str(item.get("path") or "").strip()
        expected = str(item.get("sha256") or "").strip().lower()
        if not relative or not _valid_sha256(expected):
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
            mismatches.append({
                "path": relative,
                "reason": "source_hash_changed",
                "expected": expected,
                "actual": current,
            })
    return {
        "status": "GREEN" if rows and not mismatches and len(checked) == len(rows) else "RED",
        "current": bool(rows and not mismatches and len(checked) == len(rows)),
        "checked": checked,
        "mismatches": mismatches,
    }


def _embedded_package_sha(delivered_payload: dict[str, Any] | None) -> str:
    if not isinstance(delivered_payload, dict):
        return ""
    package = delivered_payload.get("context_package")
    if isinstance(package, dict):
        return str(package.get("package_sha256") or "").strip().lower()
    context = delivered_payload.get("context")
    if isinstance(context, dict):
        package = context.get("context_package")
        if isinstance(package, dict):
            return str(package.get("package_sha256") or "").strip().lower()
    return ""


def build_delivery_receipt(
    package: dict[str, Any],
    *,
    invocation_id: str,
    consumer: str,
    project_root: Path | str | None = None,
    delivered_payload: dict[str, Any] | None = None,
    final_input_sha256: str = "",
) -> dict[str, Any]:
    """Build derived delivery evidence.

    A caller-supplied input hash is never enough to claim delivery. GREEN
    delivery evidence requires a server-bound semantic MCP response payload,
    a server-generated invocation identity, an exact embedded package identity
    and current source revalidation. Actual model behavior remains a separate
    behavioral-E2E gate.
    """
    invocation_id = str(invocation_id or "").strip()
    consumer = str(consumer or "").strip()
    package_sha = str(package.get("package_sha256") or "").strip().lower()
    final_input_sha256 = str(final_input_sha256 or "").strip().lower()
    source_validation = validate_sources(package, project_root)
    budget_ready = package.get("delivery_within_budget") is True if package.get("schema") == "energie_pm_context_package_v5" else True

    response_bound = isinstance(delivered_payload, dict)
    delivered_payload_sha256 = _sha(delivered_payload) if response_bound else ""
    embedded_package_sha = _embedded_package_sha(delivered_payload)
    package_bound = response_bound and embedded_package_sha == package_sha

    ready = bool(
        invocation_id
        and consumer
        and _valid_sha256(package_sha)
        and package_bound
        and package.get("mandatory_context_complete") is True
        and budget_ready
        and (package.get("resume_contract") or {}).get("fail_closed") is not True
        and source_validation.get("current") is True
    )

    current_truth = package.get("current_truth") if isinstance(package.get("current_truth"), dict) else {}
    governing_claims = current_truth.get("governing_claims") if isinstance(current_truth.get("governing_claims"), dict) else {}
    evidence_snapshot = {
        "known_issue_evidence": package.get("known_issue_evidence") or [],
        "capability_evidence": package.get("capability_evidence") or [],
    }
    proof_level = "MCP_RESPONSE_BOUND" if response_bound else "CALLER_ASSERTED_INPUT_HASH_UNPROVEN"
    receipt = {
        "schema": SCHEMA,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "delivery_recorded": ready,
        "mcp_response_boundary_verified": bool(ready and response_bound),
        "actual_model_boundary_verified": False,
        "boundary_proof_level": proof_level,
        "invocation_id": invocation_id,
        "consumer": consumer,
        "package_sha256": package_sha,
        "embedded_package_sha256": embedded_package_sha,
        "delivered_payload_sha256": delivered_payload_sha256,
        "caller_asserted_final_input_sha256": final_input_sha256,
        "compiler_version": package.get("compiler_version"),
        "mandatory_context_complete": package.get("mandatory_context_complete") is True,
        "delivery_within_budget": package.get("delivery_within_budget"),
        "truth_snapshot_sha256": _sha(current_truth),
        "checkpoint_identity": governing_claims.get("checkpoint") or current_truth.get("highest_checkpoint") or "",
        "first_unproven_action": (package.get("resume_contract") or {}).get("first_unproven_action") or "",
        "source_validation": source_validation,
        "source_hashes": sorted(
            _delivery_sources(package),
            key=lambda x: (str(x.get("collection") or ""), str(x.get("path") or "")),
        ),
        "nonfile_evidence_snapshot_sha256": _sha(evidence_snapshot),
        "excluded_or_deferred": {
            "deferred_requirements": [
                x.get("path") for x in package.get("deferred_requirement_refs") or [] if isinstance(x, dict)
            ],
            "deferred_evidence": list(package.get("deferred_evidence") or []),
            "optional_evidence_errors": list(package.get("optional_evidence_errors") or []),
        },
        "acceptance_note": (
            "GREEN proves the exact Projectmanager semantic MCP response payload, package identity "
            "and source hashes at the MCP response boundary. Model compliance/behavior remains a "
            "separate clean-context behavioral-E2E gate."
        ),
    }
    if not response_bound:
        receipt["reason"] = "caller_asserted_input_hash_is_not_independent_delivery_proof"
    elif not package_bound:
        receipt["reason"] = "delivered_payload_package_identity_mismatch"
    elif not ready:
        receipt["reason"] = "delivery_preconditions_not_green"
    receipt["receipt_sha256"] = _sha(receipt)
    return receipt


def verify_delivery_receipt(
    receipt: dict[str, Any],
    *,
    delivered_payload: dict[str, Any],
    package: dict[str, Any],
    project_root: Path | str | None,
) -> dict[str, Any]:
    reasons: list[str] = []
    expected_payload = _sha(delivered_payload)
    source_validation = validate_sources(package, project_root)
    if receipt.get("delivery_recorded") is not True:
        reasons.append("delivery_not_recorded")
    if receipt.get("mcp_response_boundary_verified") is not True:
        reasons.append("mcp_response_boundary_not_verified")
    if receipt.get("delivered_payload_sha256") != expected_payload:
        reasons.append("payload_hash_mismatch")
    if receipt.get("package_sha256") != package.get("package_sha256"):
        reasons.append("package_hash_mismatch")
    if _embedded_package_sha(delivered_payload) != package.get("package_sha256"):
        reasons.append("embedded_package_hash_mismatch")
    if source_validation.get("current") is not True:
        reasons.append("source_changed")
    return {
        "status": "GREEN" if not reasons else "RED",
        "valid": not reasons,
        "reasons": reasons,
        "source_validation": source_validation,
    }
