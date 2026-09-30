from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "energie_pm_context_delivery_receipt_v1"

def _sha(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def build_delivery_receipt(
    package: dict[str, Any],
    *,
    invocation_id: str,
    final_input_sha256: str,
    consumer: str,
) -> dict[str, Any]:
    invocation_id = str(invocation_id or "").strip()
    final_input_sha256 = str(final_input_sha256 or "").strip().lower()
    consumer = str(consumer or "").strip()
    package_sha = str(package.get("package_sha256") or "").strip().lower()
    ready = bool(
        invocation_id
        and consumer
        and len(final_input_sha256) == 64
        and all(ch in "0123456789abcdef" for ch in final_input_sha256)
        and len(package_sha) == 64
        and package.get("mandatory_context_complete") is True
        and (package.get("resume_contract") or {}).get("fail_closed") is not True
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
