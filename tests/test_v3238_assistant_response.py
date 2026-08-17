from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
MAIN = APP / "main.py"


def _load():
    path = APP / "assistant_response.py"
    spec = importlib.util.spec_from_file_location("assistant_response", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_renderer_current_gas_is_deterministic_and_partial():
    mod = _load()
    ctx = {
        "resolved": {"month": "2026_08", "domains": ["gas"]},
        "quality": {"status": "PARTIAL"},
        "evidence": {"metrics": {"gas_m3": 4.679}},
    }
    text = mod.render_assistant_response(ctx)
    assert "4,679" in text
    assert "augustus 2026" in text.lower()
    assert "partieel" in text.lower()


def test_renderer_finance_never_claims_invoice_actual_when_absent():
    mod = _load()
    ctx = {
        "resolved": {"month": "2026_08", "domains": ["finance"]},
        "quality": {"status": "PARTIAL", "financial_claim": "MODELED_OR_PARTIAL_NOT_INVOICE_ACTUAL"},
        "evidence": {"metrics": {}, "finance": {"supplier": "NextEnergy", "invoice_actuals_present": False, "invoice_actual_eur": None, "monthly_advance_eur": 150.0}},
    }
    text = mod.render_assistant_response(ctx).lower()
    assert "nextenergy" in text
    assert "geen officiële factuur" in text
    assert "150" in text


def test_renderer_apparatus_uses_kb_match():
    mod = _load()
    ctx = {
        "resolved": {"month": "2026_08", "domains": ["apparatus"]},
        "quality": {"status": "PARTIAL"},
        "evidence": {"metrics": {}, "knowledge": {"matches": [{"source": "Knowledge_Base.md", "line": 44, "text": "Mitsubishi woonkamerairco: WSH-AY50 VGK / MSZ-AY50 / MUZ-AY50."}] }},
    }
    text = mod.render_assistant_response(ctx)
    assert "Mitsubishi" in text
    assert "MSZ-AY50" in text


def test_main_exposes_strict_read_only_respond_route():
    source = MAIN.read_text(encoding="utf-8")
    assert "/api/assistant/respond" in source
    assert "render_assistant_response" in source
    assert 'set(payload) - {"query", "session_id"}' in source
