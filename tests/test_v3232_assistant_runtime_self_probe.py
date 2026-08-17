import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "slimmemeterportal_import/rootfs/app/assistant_runtime_probe.py"
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_module(name="assistant_runtime_probe_test"):
    spec = importlib.util.spec_from_file_location(name, MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def passing_calls():
    return {
        "health": {
            "http_status": 200,
            "json": {"status": "ready", "version": "32.3.13", "read_only": True},
        },
        "august_gas": {
            "http_status": 200,
            "json": {
                "resolved": {"month": "2026_08", "domains": ["gas"]},
                "quality": {
                    "status": "PARTIAL",
                    "source_quality": {
                        "gas_source": "home_assistant_quarter_hour_primary",
                        "quarter_hour": {
                            "available": True,
                            "coverage_status": "partial_current_month",
                            "sample_count": 1032,
                        },
                    },
                },
                "evidence": {
                    "metrics": {"gas_m3": 4.6},
                    "sources": {"gas": "home_assistant_quarter_hour_primary"},
                },
            },
        },
        "previous_month": {
            "http_status": 200,
            "json": {
                "resolved": {"month": "2026_07", "domains": ["gas"]},
                "quality": {"status": "COMPLETE"},
                "evidence": {"metrics": {"gas_m3": 33.89}},
            },
        },
        "finance": {
            "http_status": 200,
            "json": {
                "resolved": {"month": "2026_08", "domains": ["finance"]},
                "quality": {"financial_claim": "MODELED_OR_PARTIAL_NOT_INVOICE_ACTUAL"},
                "evidence": {
                    "finance": {
                        "contract_components_ready": True,
                        "invoice_actuals_present": False,
                        "invoice_actual_eur": None,
                    }
                },
            },
        },
        "apparatus": {
            "http_status": 200,
            "json": {
                "resolved": {"domains": ["apparatus"]},
                "evidence": {
                    "knowledge": {
                        "matches": [
                            {"source": "Knowledge_Base.md", "text": "Airco 5 kW"}
                        ]
                    }
                },
            },
        },
        "negative_path": {"http_status": 404, "json": None},
        "negative_payload": {"http_status": 400, "json": {"status": "error"}},
    }


def test_acceptance_evaluation_requires_all_runtime_evidence():
    m = load_module("probe_acceptance")
    result = m.evaluate_assistant_runtime_acceptance(passing_calls(), expected_version="32.3.13")
    assert result["status"] == "PASS"
    assert result["voice_gate"] == "OPEN_FOR_NEXT_ACCEPTANCE_STEP"
    assert all(item["passed"] for item in result["checks"].values())


def test_acceptance_fails_if_august_is_not_quarter_hour_partial():
    m = load_module("probe_partial")
    calls = passing_calls()
    calls["august_gas"]["json"]["quality"]["status"] = "COMPLETE"
    result = m.evaluate_assistant_runtime_acceptance(calls, expected_version="32.3.13")
    assert result["status"] == "FAIL"
    assert result["voice_gate"] == "CLOSED"
    assert result["checks"]["august_partial_quarter_hour"]["passed"] is False


def test_probe_transport_has_no_arbitrary_host_or_path_input():
    m = load_module("probe_fixed_transport")
    assert m.PROBE_ORIGIN == "http://127.0.0.1:8099"
    assert set(m.PROBE_ROUTES) == {"health", "context", "negative_path"}
    assert m.PROBE_ROUTES["health"] == ("GET", "/api/assistant/health")
    assert m.PROBE_ROUTES["context"] == ("POST", "/api/assistant/context")
    assert m.PROBE_ROUTES["negative_path"] == ("POST", "/api/assistant/not-allowed-probe")
    assert m.MAX_RESPONSE_BYTES == 256 * 1024
    assert m.MAX_REQUEST_BYTES == 32 * 1024


def test_main_wires_one_startup_probe_and_rejects_extra_assistant_payload_fields():
    source = MAIN.read_text(encoding="utf-8")
    assert "assistant_runtime_probe" in source
    assert "startup_assistant_runtime_self_probe" in source
    assert "resolve_runtime_acceptance_path" in source
    assert "unsupported assistant payload fields" in source
    assert "MAX_ASSISTANT_REQUEST_BYTES" in source


def test_release_identity_and_changelog_are_v3232():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.16"
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    addon_changelog = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert 'version: "32.3.16"' in config
    assert 'APP_VERSION = "32.3.16"' in main
    assert changelog.startswith("## 32.3.16 — Crash Recovery Maintenance integration")
    assert addon_changelog.startswith("# Changelog\n\n## 32.3.16")

