import importlib.util
from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "slimmemeterportal_import/rootfs/app/energy_conversation.py"
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
TZ = ZoneInfo("Europe/Amsterdam")


def load_module(name="energy_conversation_test"):
    spec = importlib.util.spec_from_file_location(name, MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def analysis_fixture():
    return {
        "schema": "energy_analysis_context_v1",
        "version": "32.3.9",
        "months": [
            {
                "month": "2026_07",
                "metrics": {"grid_import_kwh": 156.32, "grid_export_kwh": 603.97, "gas_m3": 33.89},
                "quality": {
                    "grid_import_source": "slimmemeterportal_fallback",
                    "grid_export_source": "slimmemeterportal_fallback",
                    "gas_source": "slimmemeterportal_fallback",
                    "smp": {"coverage_status": "ok"},
                },
                "financial_context": {"status": "partial"},
            },
            {
                "month": "2026_08",
                "metrics": {"grid_import_kwh": 65.942, "grid_export_kwh": 212.908, "gas_m3": 4.556},
                "quality": {
                    "grid_import_source": "home_assistant_quarter_hour_primary",
                    "grid_export_source": "home_assistant_quarter_hour_primary",
                    "gas_source": "home_assistant_quarter_hour_primary",
                    "quarter_hour": {
                        "available": True,
                        "coverage_status": "partial_current_month",
                        "sample_count": 1023,
                        "first_snapshot": "20260805T143000Z",
                        "last_snapshot": "20260816T163000Z",
                    },
                },
                "financial_context": {
                    "status": "partial_observed",
                    "observed_variable_electricity_cost_eur": 15.3,
                    "limitations": ["invoice actuals unavailable"],
                },
            },
        ],
        "supplier_context": {
            "contract": {"supplier": "NextEnergy", "monthly_advance_eur": 150.0},
            "contract_validation": {
                "modeled_contract_components_ready": True,
                "invoice_actuals_present": False,
            },
        },
    }


def test_conversation_module_exists_red_gate():
    assert MODULE.is_file()


def test_current_month_gas_query_returns_partial_evidence():
    m = load_module("conversation_current")
    engine = m.EnergyConversationEngine(
        app_version="32.3.9",
        analysis_provider=lambda year=None: analysis_fixture(),
        knowledge_provider=lambda query, domains: {"matches": []},
        now_provider=lambda: datetime(2026, 8, 16, 18, 0, tzinfo=TZ),
    )
    result = engine.context("Hoeveel gas heb ik deze maand gebruikt?")
    assert result["schema"] == "energie_conversation_context_v1"
    assert result["resolved"]["month"] == "2026_08"
    assert result["resolved"]["domains"] == ["gas"]
    assert result["quality"]["status"] == "PARTIAL"
    assert result["evidence"]["metrics"]["gas_m3"] == 4.556
    assert result["evidence"]["sources"]["gas"] == "home_assistant_quarter_hour_primary"
    assert len(result["proactive_observations"]) <= 3


def test_followup_inherits_domain_and_moves_to_previous_month():
    m = load_module("conversation_followup")
    engine = m.EnergyConversationEngine(
        app_version="32.3.9",
        analysis_provider=lambda year=None: analysis_fixture(),
        knowledge_provider=lambda query, domains: {"matches": []},
        now_provider=lambda: datetime(2026, 8, 16, 18, 0, tzinfo=TZ),
    )
    first = engine.context("Hoeveel gas heb ik deze maand gebruikt?", session_id="abc")
    second = engine.context("En vorige maand?", session_id="abc")
    assert first["session_id"] == "abc"
    assert second["session_id"] == "abc"
    assert second["resolved"]["domains"] == ["gas"]
    assert second["resolved"]["month"] == "2026_07"
    assert second["evidence"]["metrics"]["gas_m3"] == 33.89


def test_finance_query_exposes_contract_quality_without_invoice_claim():
    m = load_module("conversation_finance")
    engine = m.EnergyConversationEngine(
        app_version="32.3.9",
        analysis_provider=lambda year=None: analysis_fixture(),
        knowledge_provider=lambda query, domains: {"matches": []},
        now_provider=lambda: datetime(2026, 8, 16, 18, 0, tzinfo=TZ),
    )
    result = engine.context("Wat kosten we deze maand bij NextEnergy?")
    assert "finance" in result["resolved"]["domains"]
    finance = result["evidence"]["finance"]
    assert finance["contract_components_ready"] is True
    assert finance["invoice_actuals_present"] is False
    assert finance["invoice_actual_eur"] is None
    assert result["quality"]["financial_claim"] == "MODELED_OR_PARTIAL_NOT_INVOICE_ACTUAL"


def test_apparatus_query_uses_read_only_knowledge_provider():
    m = load_module("conversation_apparatus")
    calls = []
    def knowledge(query, domains):
        calls.append((query, tuple(domains)))
        return {"matches": [{"source": "Apparatuur_index.md", "text": "Airco Mitsubishi"}]}
    engine = m.EnergyConversationEngine(
        app_version="32.3.9",
        analysis_provider=lambda year=None: analysis_fixture(),
        knowledge_provider=knowledge,
        now_provider=lambda: datetime(2026, 8, 16, 18, 0, tzinfo=TZ),
    )
    result = engine.context("Wat weet je van mijn airco?")
    assert "apparatus" in result["resolved"]["domains"]
    assert calls
    assert result["evidence"]["knowledge"]["matches"][0]["source"] == "Apparatuur_index.md"


def test_engine_safety_has_no_write_or_external_action_primitives():
    source = MODULE.read_text(encoding="utf-8")
    forbidden = ["write_text(", "write_bytes(", "requests.", "urllib.request", "finalize_month", "subprocess", "os.system"]
    for token in forbidden:
        assert token not in source


def test_main_exposes_read_only_assistant_http_contract():
    source = MAIN.read_text(encoding="utf-8")
    assert 'path.endswith("/api/assistant/health")' in source
    assert 'path.endswith("/api/assistant/context")' in source
    assert "EnergyConversationEngine" in source
    assert '"query"' in source
    assert '"session_id"' in source
    assert "json.JSONDecodeError" in source


def test_expired_session_does_not_inherit_old_domain(monkeypatch):
    m = load_module("conversation_ttl")
    clock = {"value": 1000.0}
    monkeypatch.setattr(m.time, "monotonic", lambda: clock["value"])
    engine = m.EnergyConversationEngine(
        app_version="32.3.9",
        analysis_provider=lambda year=None: analysis_fixture(),
        knowledge_provider=lambda query, domains: {"matches": []},
        now_provider=lambda: datetime(2026, 8, 16, 18, 0, tzinfo=TZ),
        session_ttl_seconds=60,
    )
    engine.context("Hoeveel gas heb ik deze maand gebruikt?", session_id="ttl")
    clock["value"] += 61.0
    result = engine.context("En vorige maand?", session_id="ttl")
    assert result["resolved"]["domains"] == ["energy"]
    assert result["resolved"]["month"] == "2026_07"


def test_session_cache_is_bounded_and_health_is_read_only():
    m = load_module("conversation_bounded")
    engine = m.EnergyConversationEngine(
        app_version="32.3.9",
        analysis_provider=lambda year=None: analysis_fixture(),
        knowledge_provider=lambda query, domains: {"matches": []},
        now_provider=lambda: datetime(2026, 8, 16, 18, 0, tzinfo=TZ),
        max_sessions=2,
    )
    engine.context("gas deze maand", session_id="one")
    engine.context("gas deze maand", session_id="two")
    engine.context("gas deze maand", session_id="three")
    health = engine.health()
    assert health["read_only"] is True
    assert health["active_sessions"] == 2
    assert list(engine._sessions) == ["two", "three"]


def test_unknown_month_remains_unknown_instead_of_inventing_values():
    m = load_module("conversation_unknown")
    engine = m.EnergyConversationEngine(
        app_version="32.3.9",
        analysis_provider=lambda year=None: analysis_fixture(),
        knowledge_provider=lambda query, domains: {"matches": []},
        now_provider=lambda: datetime(2026, 8, 16, 18, 0, tzinfo=TZ),
    )
    result = engine.context("Hoeveel gas in 2025-01?")
    assert result["resolved"]["month"] == "2025_01"
    assert result["quality"]["status"] == "UNKNOWN"
    assert result["evidence"]["metrics"]["gas_m3"] is None


def test_invalid_session_id_is_rejected():
    m = load_module("conversation_session_guard")
    engine = m.EnergyConversationEngine(
        app_version="32.3.9",
        analysis_provider=lambda year=None: analysis_fixture(),
        knowledge_provider=lambda query, domains: {"matches": []},
        now_provider=lambda: datetime(2026, 8, 16, 18, 0, tzinfo=TZ),
    )
    import pytest
    with pytest.raises(ValueError):
        engine.context("gas", session_id="bad session/id")
