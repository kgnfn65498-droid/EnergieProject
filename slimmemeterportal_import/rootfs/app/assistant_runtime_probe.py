from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable


PROBE_ORIGIN = "http://127.0.0.1:8099"
PROBE_ROUTES = {
    "health": ("GET", "/api/assistant/health"),
    "context": ("POST", "/api/assistant/context"),
    "negative_path": ("POST", "/api/assistant/not-allowed-probe"),
}
MAX_RESPONSE_BYTES = 256 * 1024
MAX_REQUEST_BYTES = 32 * 1024
REQUEST_TIMEOUT_SECONDS = 5.0
ASSISTANT_RUNTIME_ACCEPTANCE_RELATIVE = Path("Inbox/logs/assistant_runtime_acceptance.json")


def resolve_runtime_acceptance_path(
    wait_for_roots: Callable[..., tuple[Path, Path]],
) -> Path:
    _, live_nas_layout_root = wait_for_roots(attempts=60, delay_seconds=5.0)
    return live_nas_layout_root / ASSISTANT_RUNTIME_ACCEPTANCE_RELATIVE


def _decode_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None


def _read_limited(handle: Any) -> bytes:
    raw = handle.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("assistant probe response exceeds 256 KiB")
    return raw


def _call_fixed_route(route_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    if route_key not in PROBE_ROUTES:
        raise ValueError("unsupported fixed probe route")
    method, path = PROBE_ROUTES[route_key]
    raw_request = b""
    headers = {"Accept": "application/json"}
    if payload is not None:
        raw_request = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(raw_request) > MAX_REQUEST_BYTES:
            raise ValueError("assistant probe request exceeds 32 KiB")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        PROBE_ORIGIN + path,
        data=raw_request if method == "POST" else None,
        headers=headers,
        method=method,
    )
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw = _read_limited(response)
            return {
                "http_status": int(response.status),
                "json": _decode_json(raw),
                "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
                "error": None,
            }
    except urllib.error.HTTPError as exc:
        raw = _read_limited(exc)
        return {
            "http_status": int(exc.code),
            "json": _decode_json(raw),
            "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
            "error": None,
        }
    except Exception as exc:
        return {
            "http_status": None,
            "json": None,
            "elapsed_ms": round((time.monotonic() - started) * 1000.0, 1),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _check(passed: bool, detail: str) -> dict[str, Any]:
    return {"passed": bool(passed), "detail": detail}


def evaluate_assistant_runtime_acceptance(
    calls: dict[str, dict[str, Any]], *, expected_version: str
) -> dict[str, Any]:
    health = (calls.get("health") or {}).get("json") or {}
    august = (calls.get("august_gas") or {}).get("json") or {}
    previous = (calls.get("previous_month") or {}).get("json") or {}
    finance = (calls.get("finance") or {}).get("json") or {}
    apparatus = (calls.get("apparatus") or {}).get("json") or {}

    august_quality = august.get("quality") or {}
    august_source_quality = august_quality.get("source_quality") or {}
    quarter = august_source_quality.get("quarter_hour") or {}
    boundary = august_source_quality.get("boundary_bridge") or {}
    measurement = august_source_quality.get("measurement_period") or {}
    august_evidence = august.get("evidence") or {}
    finance_evidence = (finance.get("evidence") or {}).get("finance") or {}
    knowledge = (apparatus.get("evidence") or {}).get("knowledge") or {}
    matches = knowledge.get("matches") or []

    checks = {
        "health_ready_read_only": _check(
            (calls.get("health") or {}).get("http_status") == 200
            and health.get("status") == "ready"
            and health.get("read_only") is True
            and str(health.get("version")) == str(expected_version),
            "health moet ready/read-only zijn en exact de releaseversie melden",
        ),
        "august_reconciled_full_month": _check(
            (calls.get("august_gas") or {}).get("http_status") == 200
            and (august.get("resolved") or {}).get("month") == "2026_08"
            and "gas" in ((august.get("resolved") or {}).get("domains") or [])
            and august_quality.get("status") == "COMPLETE"
            and boundary.get("status") == "ready"
            and boundary.get("source") == "smp_start_p1_end_boundary"
            and measurement.get("complete") is True
            and measurement.get("source") == "smp_start_p1_end_boundary"
            and august_source_quality.get("gas_source") == "smp_start_p1_end_boundary"
            and (august_evidence.get("sources") or {}).get("gas") == "smp_start_p1_end_boundary"
            and ((august_evidence.get("metrics") or {}).get("gas_m3") is not None),
            "augustus 2026 moet COMPLETE zijn via de gevalideerde SMP-start/P1-eind metergrensbrug",
        ),
        "session_previous_month": _check(
            (calls.get("previous_month") or {}).get("http_status") == 200
            and (previous.get("resolved") or {}).get("month") == "2026_07"
            and "gas" in ((previous.get("resolved") or {}).get("domains") or [])
            and ((previous.get("evidence") or {}).get("metrics") or {}).get("gas_m3") is not None,
            "dezelfde sessie moet 'vorige maand' naar juli 2026 met gascontext routeren",
        ),
        "finance_modeled_not_invoice_actual": _check(
            (calls.get("finance") or {}).get("http_status") == 200
            and finance_evidence.get("contract_components_ready") is True
            and finance_evidence.get("invoice_actuals_present") is False
            and finance_evidence.get("invoice_actual_eur") is None
            and (finance.get("quality") or {}).get("financial_claim") == "MODELED_OR_PARTIAL_NOT_INVOICE_ACTUAL",
            "NextEnergy mag contractmatig gemodelleerd zijn maar geen factuuractual claimen",
        ),
        "apparatus_knowledge_provenance": _check(
            (calls.get("apparatus") or {}).get("http_status") == 200
            and "apparatus" in ((apparatus.get("resolved") or {}).get("domains") or [])
            and bool(matches)
            and all(bool(item.get("source")) for item in matches if isinstance(item, dict)),
            "apparaatantwoord moet Knowledge Base-bewijs met bronvermelding bevatten",
        ),
        "negative_path_rejected": _check(
            (calls.get("negative_path") or {}).get("http_status") == 404,
            "een niet-toegestane assistant-route moet 404 geven",
        ),
        "negative_payload_rejected": _check(
            (calls.get("negative_payload") or {}).get("http_status") == 400,
            "extra write/action-velden in assistant-context moeten worden geweigerd",
        ),
    }
    passed = all(item["passed"] for item in checks.values())
    return {
        "schema": "assistant_runtime_acceptance_v1",
        "status": "PASS" if passed else "FAIL",
        "voice_gate": "OPEN_FOR_NEXT_ACCEPTANCE_STEP" if passed else "CLOSED",
        "expected_version": str(expected_version),
        "checks": checks,
    }


def run_assistant_runtime_probe(*, app_version: str) -> dict[str, Any]:
    session_id = "runtime-acceptance-v3232"
    calls = {
        "health": _call_fixed_route("health"),
        "august_gas": _call_fixed_route(
            "context",
            {"query": "Hoeveel gas heb ik in 2026-08 gebruikt?", "session_id": session_id},
        ),
        "previous_month": _call_fixed_route(
            "context",
            {"query": "En vorige maand?", "session_id": session_id},
        ),
        "finance": _call_fixed_route(
            "context",
            {"query": "Wat kosten we in 2026-08 bij NextEnergy?", "session_id": "runtime-finance-v3232"},
        ),
        "apparatus": _call_fixed_route(
            "context",
            {"query": "Wat weet je van mijn airco?", "session_id": "runtime-apparatus-v3232"},
        ),
        "negative_path": _call_fixed_route("negative_path"),
        "negative_payload": _call_fixed_route(
            "context",
            {"query": "gas", "session_id": "runtime-negative-v3232", "write": True},
        ),
    }
    result = evaluate_assistant_runtime_acceptance(calls, expected_version=app_version)
    result["calls"] = calls
    return result
