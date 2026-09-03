from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
MAIN = APP / "main.py"
P1_DIR = APP / "report_generators" / "Energierapport_Pagina1_Echte_Generator_v7"
VALIDATOR = P1_DIR / "validate_maanddata.py"
GENERATOR = P1_DIR / "generate_energierapport_pagina1.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_main():
    return load_module(MAIN, "main_v32331")


def test_page1_validator_accepts_model_provenance_fields():
    validator = load_module(VALIDATOR, "validator_v32331")
    payload = json.loads((P1_DIR / "maanddata_voorbeeld.json").read_text(encoding="utf-8"))
    payload["efficientie"].update({
        "modelled": True,
        "model_label": "modelwaarde uit bronvaste historische PV-verhouding",
    })
    validator.validate(payload)


def test_august_adapter_page1_validates_and_renders_end_to_end(monkeypatch, tmp_path):
    m = load_main()
    service = tmp_path / "service"
    input_folder = tmp_path / "input" / "2026_08"
    input_folder.mkdir(parents=True)
    monkeypatch.setattr(m, "BUNDLED_REPORT_GENERATORS", APP / "report_generators")
    monkeypatch.setattr(m, "report_service_paths", lambda _options: {
        "root": service,
        "generators": service / "generators",
        "work": service / "work",
        "output": service / "output",
        "logs": service / "logs",
    })
    monkeypatch.setattr(m, "update_state", lambda **_changes: None)
    monkeypatch.setattr(m, "_month_energy_metrics", lambda *_args, **_kwargs: {
        "metrics": {
            "grid_import_kwh": 193.83,
            "grid_export_kwh": 507.498,
            "gas_m3": 9.074,
            "solar_production_kwh": 375.0,
            "direct_solar_use_kwh": None,
            "house_use_kwh": None,
            "self_use_pct": None,
            "self_supply_pct": None,
        },
        "quality": {
            "measurement_period": {"complete": True, "source": "smp_start_p1_end_boundary"},
            "grid_import_source": "smp_start_p1_end_boundary",
            "grid_export_source": "smp_start_p1_end_boundary",
            "gas_source": "smp_start_p1_end_boundary",
            "production_source": "enphase_partial",
            "solar_balance_status": "incomplete",
        },
    })
    options = SimpleNamespace(report_service_root="unused")
    handoff = {"month": "2026_08", "input_folder": str(input_folder)}
    result = m.build_report_adapter_data(options, handoff)
    page1 = Path(result["files"][0])
    validator = load_module(VALIDATOR, "validator_v32331_e2e")
    validator.load_and_validate(page1)

    out = tmp_path / "augustus-p1.pdf"
    old_path = list(sys.path)
    try:
        sys.path.insert(0, str(P1_DIR))
        generator = load_module(GENERATOR, "generator_v32331_e2e")
        generator.generate(page1, out, P1_DIR / "assets")
    finally:
        sys.path[:] = old_path
    assert out.is_file() and out.stat().st_size > 10000


def test_solar_model_factor_is_derived_from_historical_seed_not_hardcoded():
    m = load_main()
    assert not hasattr(m, "PV_SET_TOTAL_TO_ENPHASE_RATIO")
    model = m.historical_pv_model_basis()
    assert model["available"] is True
    assert model["factor"] > 2.0
    assert "historical_energy_seed" in model["source"]
    result = m.report_solar_model_metrics(
        grid_import_kwh=193.83,
        grid_export_kwh=507.498,
        enphase_production_kwh=375.0,
        solar_balance_reliable=False,
    )
    assert result["modelled"] is True
    assert result["model_basis"]["factor"] == model["factor"]
    assert "historische" in result["label"].lower()


def test_adapter_top_energy_score_matches_numeric_report_score(monkeypatch, tmp_path):
    m = load_main()
    service = tmp_path / "service"
    input_folder = tmp_path / "input" / "2026_08"
    input_folder.mkdir(parents=True)
    monkeypatch.setattr(m, "BUNDLED_REPORT_GENERATORS", APP / "report_generators")
    monkeypatch.setattr(m, "report_service_paths", lambda _options: {
        "root": service, "generators": service / "generators", "work": service / "work", "output": service / "output", "logs": service / "logs"
    })
    monkeypatch.setattr(m, "update_state", lambda **_changes: None)
    monkeypatch.setattr(m, "_month_energy_metrics", lambda *_args, **_kwargs: {
        "metrics": {"grid_import_kwh": 193.83, "grid_export_kwh": 507.498, "gas_m3": 9.074, "solar_production_kwh": 375.0},
        "quality": {"measurement_period": {"complete": True, "source": "smp_start_p1_end_boundary"}, "solar_balance_status": "incomplete"},
    })
    result = m.build_report_adapter_data(SimpleNamespace(report_service_root="unused"), {"month": "2026_08", "input_folder": str(input_folder)})
    payload = json.loads(Path(result["files"][0]).read_text(encoding="utf-8"))
    top_score = payload["kpi_boven"][6]
    assert top_score["waarde"] == str(payload["score"]["totaal"])
    assert top_score["eenheid"] == "/100"
    assert top_score["delta"] in {"voorlopig", "model"}


def test_closed_month_closes_open_retry(monkeypatch, tmp_path):
    m = load_main()
    retry_path = tmp_path / "automatic_retry_state.json"
    state_path = tmp_path / "state.json"
    monkeypatch.setattr(m, "AUTOMATIC_RETRY_STATE_PATH", retry_path)
    monkeypatch.setattr(m, "STATE_PATH", state_path)
    monkeypatch.setattr(m, "AUTOMATIC_RUN_LEDGER_PATH", tmp_path / "none.jsonl")
    monkeypatch.setattr(m, "AUTOMATIC_COMPLETION_MARKERS_PATH", tmp_path / "none.json")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "output")
    monkeypatch.setattr(m, "append_retry_debug", lambda *_a, **_k: None)
    monkeypatch.setattr(m, "recovery_month_closure_proof", lambda month: {
        "closed": month == "2026_08",
        "evidence": "RecoveryManager MonthClosure_2026_08=CLOSED",
    })
    m.write_automatic_retry_state(
        state="OPEN", month="2026_08", reason="workflow_or_finalization_failed",
        origin="automatic", next_retry="2026-09-03T22:04:00+02:00", evidence="old failure",
    )
    state_path.write_text(json.dumps(m.default_state()), encoding="utf-8")
    state, retry = m.reconcile_automatic_retry_state(m.load_state())
    assert retry["state"] == "COMPLETED"
    assert retry["next_retry"] is None
    assert "CLOSED" in retry["evidence"]


def test_release_health_risks_block_failed_historical_rebuild_and_open_retry():
    m = load_main()
    risks = m.release_health_risk_checks(
        {"historical_report_rebuild_last_status": "failed", "historical_report_rebuild_last_month": "2026_08"},
        {"state": "OPEN", "month": "2026_08", "reason": "workflow_or_finalization_failed"},
    )
    assert risks["historical_report_rebuild_ok"] is False
    assert risks["automatic_retry_clear"] is False
    assert any("historisch" in item.lower() for item in risks["issues"])
    assert any("retry" in item.lower() for item in risks["issues"])


def test_diagnostic_package_has_explicit_report_and_retry_gates():
    source = MAIN.read_text(encoding="utf-8")
    block = source[source.index("def build_test_package"):source.index("def github_publication_ui_snapshot")]
    assert '"historical_report_rebuild_ok"' in block
    assert '"automatic_retry_clear"' in block
    assert "release_health_risk_checks" in block


def test_pages_3_13_use_numeric_score_and_label_modelled_solar_truthfully(monkeypatch, tmp_path):
    m = load_main()
    service = tmp_path / "service"
    input_folder = tmp_path / "input" / "2026_08"
    input_folder.mkdir(parents=True)
    monkeypatch.setattr(m, "BUNDLED_REPORT_GENERATORS", APP / "report_generators")
    monkeypatch.setattr(m, "report_service_paths", lambda _options: {
        "root": service, "generators": service / "generators", "work": service / "work", "output": service / "output", "logs": service / "logs"
    })
    monkeypatch.setattr(m, "update_state", lambda **_changes: None)
    monkeypatch.setattr(m, "_month_energy_metrics", lambda *_args, **_kwargs: {
        "metrics": {"grid_import_kwh": 193.83, "grid_export_kwh": 507.498, "gas_m3": 9.074, "solar_production_kwh": 375.0},
        "quality": {"measurement_period": {"complete": True, "source": "smp_start_p1_end_boundary"}, "solar_balance_status": "incomplete", "production_source": "Enphase.csv"},
    })
    result = m.build_report_adapter_data(SimpleNamespace(report_service_root="unused"), {"month": "2026_08", "input_folder": str(input_folder)})
    pages = json.loads(Path(result["files"][2]).read_text(encoding="utf-8"))
    assert isinstance(pages["dashboard"]["score"], (int, float))
    assert pages["solar"]["modelled"] is True
    assert "historische" in pages["solar"]["limitation"].lower()
    generator = (APP / "report_generators" / "Energierapport_Pagina3_tm_13_Generator_v1_0" / "src" / "generate_pages_3_13.py").read_text(encoding="utf-8")
    assert "dash.get('score')" in generator
    assert "Geschatte totale PV-productie" in generator
