from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
MAIN = APP / "main.py"
P2 = APP / "report_generators" / "Energierapport_Pagina2_Generator_v6_0" / "src" / "generate_p2.py"
P313 = APP / "report_generators" / "Energierapport_Pagina3_tm_13_Generator_v1_0" / "src" / "generate_pages_3_13.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_main():
    return load_module(MAIN, "main_v32332")


def _prepare_adapter(monkeypatch, tmp_path):
    m = load_main()
    service = tmp_path / "service"
    input_folder = tmp_path / "input" / "2026_08"
    input_folder.mkdir(parents=True)
    # Realistic partial Enphase coverage from the live August export.
    (input_folder / "Enphase.csv").write_text(
        "captured_at,entity_id,friendly_name,value,unit,device_class,state_class,last_updated\n"
        "2026-08-06T16:00:56.681534+02:00,sensor.envoy,Envoy,7372.792,kWh,energy,total_increasing,2026-08-06T13:56:58+00:00\n"
        "2026-08-31T23:48:28.852271+02:00,sensor.envoy,Envoy,7594.335,kWh,energy,total_increasing,2026-08-31T21:41:05+00:00\n",
        encoding="utf-8",
    )
    smp_dir = input_folder / "HomeAssistant" / "SlimmeMeterPortal"
    smp_dir.mkdir(parents=True)
    (smp_dir / "content_coverage_report.json").write_text(json.dumps({
        "status": "error",
        "month": "2026_08",
        "days_expected": 62,
        "days_with_measurements": 10,
        "empty_days": [f"x/{i}" for i in range(52)],
        "available_through": "2026-08-05",
    }), encoding="utf-8")

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
            "solar_production_kwh": 221.543,
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
            "production_source": "enphase",
            "solar_balance_status": "inconsistent_period_coverage",
            "boundary_bridge": {"status": "ready", "source": "smp_start_p1_end_boundary"},
        },
    })
    result = m.build_report_adapter_data(
        SimpleNamespace(report_service_root="unused"),
        {"month": "2026_08", "input_folder": str(input_folder)},
    )
    return m, input_folder, result


def test_partial_enphase_model_normalizes_to_full_calendar_month_before_array_ratio():
    m = load_main()
    result = m.report_solar_model_metrics(
        grid_import_kwh=193.83,
        grid_export_kwh=507.498,
        enphase_production_kwh=221.543,
        solar_balance_reliable=False,
        enphase_coverage_fraction=0.8169250936,
    )
    assert result["modelled"] is True
    assert result["enphase_full_month_estimate_kwh"] > 270
    assert result["total_production_kwh"] > 580
    assert result["direct_solar_use_kwh"] > 70
    assert 10 < result["self_use_pct"] < 20
    assert 20 < result["self_supply_pct"] < 40
    assert "tijd" in result["label"].lower()


def test_august_adapter_uses_enphase_time_coverage_and_no_zero_pv_artifact(monkeypatch, tmp_path):
    _m, _input, result = _prepare_adapter(monkeypatch, tmp_path)
    page1 = json.loads(Path(result["files"][0]).read_text(encoding="utf-8"))
    pages = json.loads(Path(result["files"][2]).read_text(encoding="utf-8"))

    assert result["measurements"]["production_kwh"] > 580
    assert result["measurements"]["direct_solar_kwh"] > 70
    assert result["measurements"]["house_use_kwh"] > 260
    assert result["measurements"]["self_use_pct"] > 10
    assert result["measurements"]["self_supply_pct"] > 20
    assert page1["efficientie"]["eigen_verbruik"] > 10
    assert page1["efficientie"]["zelfvoorziening"] > 20
    efficiency_score = dict(page1["score"]["onderdelen"])["Efficiëntie"]
    assert efficiency_score > 0
    assert pages["dashboard"]["house"] > 260
    assert pages["solar"]["production"] > 580


def test_pages_3_13_render_truthful_model_labels_gas_and_smp_detail(monkeypatch, tmp_path):
    _m, _input, result = _prepare_adapter(monkeypatch, tmp_path)
    data_path = Path(result["files"][2])
    generator = load_module(P313, "p313_v32332")
    out = tmp_path / "pages3_13.pdf"
    generator.generate(data_path, out)
    texts = [(page.extract_text() or "") for page in PdfReader(str(out)).pages]

    page3 = texts[0]
    assert "Geschatte totale PV-productie" in page3
    assert "Gemeten Enphase-productie" not in page3
    assert "P1-teruglevering" in page3
    assert "Netto teruglevering" not in page3

    page5 = texts[2]
    assert "Geschat totaal huisverbruik" in page5
    assert "Historische modelwaarde" in page5

    page8 = texts[5]
    assert "0,29 m³" in page8
    assert "14,7" in page8
    assert "0,62" in page8
    assert "Geen gevalideerde graaddagenbron" not in page8
    assert "n.b." not in page8

    page11 = texts[8]
    assert "historische juli-2026" in page11.lower()

    page12 = texts[9]
    assert "Recovery_Update" in page12
    assert "Data/01_Input" in page12 and "Data/02_Output" in page12

    page13 = texts[10]
    assert "10/62" in page13
    assert "52" in page13
    assert "metergrens" in page13.lower() or "boundary" in page13.lower()


def test_page2_battery_profile_is_labelled_as_offer_profile(monkeypatch, tmp_path):
    _m, _input, result = _prepare_adapter(monkeypatch, tmp_path)
    page2_data = Path(result["files"][1])
    generator = load_module(P2, "p2_v32332")
    out = tmp_path / "page2.pdf"
    generator.build(json.loads(page2_data.read_text(encoding="utf-8")), out)
    text = PdfReader(str(out)).pages[0].extract_text() or ""
    assert "Woningprofiel (NextEnergy-offerteprofiel)" in text
    assert "Eigen verbruik opwek" in text
    assert "14.0%" in text or "14,0%" in text


def test_pages_quality_payload_exposes_smp_detail_coverage(monkeypatch, tmp_path):
    _m, _input, result = _prepare_adapter(monkeypatch, tmp_path)
    pages = json.loads(Path(result["files"][2]).read_text(encoding="utf-8"))
    source_text = " ".join(" ".join(map(str, row)) for row in pages["quality"]["sources"])
    check_text = " ".join(" ".join(map(str, row)) for row in pages["quality"]["checks"])
    assert "10/62" in source_text + check_text
    assert "52" in source_text + check_text
    assert "smp_start_p1_end_boundary" in source_text + check_text


def test_pages_8_and_13_layout_reserve_non_overlapping_vertical_space():
    generator = load_module(P313, "p313_layout_v32332")
    gas = generator.page8_vertical_layout(5)
    assert gas["table_bottom"] > gas["conclusion_top"] + 8
    quality = generator.page13_vertical_layout(7, 7)
    assert quality["source_table_bottom"] > quality["checks_heading_y"]
    assert quality["last_check_y"] > quality["status_top"] + 12


def test_energy_score_cost_component_matches_financial_coverage(monkeypatch, tmp_path):
    _m, _input, result = _prepare_adapter(monkeypatch, tmp_path)
    page1 = json.loads(Path(result["files"][0]).read_text(encoding="utf-8"))
    parts = dict(page1["score"]["onderdelen"])
    assert parts["Kosten"] == 98
    assert page1["score"]["totaal"] == round(sum(parts.values()) / len(parts))


def test_page2_profile_distinguishes_offer_values_from_august_pv_model(monkeypatch, tmp_path):
    _m, _input, result = _prepare_adapter(monkeypatch, tmp_path)
    generator = load_module(P2, "p2_sources_v32332")
    out = tmp_path / "page2_sources.pdf"
    generator.build(json.loads(Path(result["files"][1]).read_text(encoding="utf-8")), out)
    text = PdfReader(str(out)).pages[0].extract_text() or ""
    assert "Teruglevering per jaar (offerte)" in text
    assert "Netto levering (offerte)" in text
    assert "Eigen verbruik opwek (aug-model)" in text
    assert "incl. buffer" not in text
    assert "Benodigde termijn" in text


def test_partial_socket_exports_are_not_labelled_as_full_month_measurements(monkeypatch, tmp_path):
    _m, input_folder, result = _prepare_adapter(monkeypatch, tmp_path)
    for file_name, start, end in [
        ("Airco Skt.csv", 6.5, 13.58),
        ("Heater woonkamer Skt.csv", 0.002, 0.002),
        ("Heater kantoor Skt.csv", 0.107, 0.307),
        ("Heater lounge Skt.csv", 2.382, 19.942),
        ("Mobiel Skt.csv", 10.006, 24.733),
    ]:
        (input_folder / file_name).write_text(
            "captured_at,total_power_import_kwh\n"
            f"2026-08-06T15:55:04+02:00,{start}\n"
            f"2026-08-31T23:48:28+02:00,{end}\n",
            encoding="utf-8",
        )
    # Rebuild after adding actual partial socket evidence.
    m = _m
    rebuilt = m.build_report_adapter_data(
        SimpleNamespace(report_service_root="unused"),
        {"month": "2026_08", "input_folder": str(input_folder)},
    )
    pages = json.loads(Path(rebuilt["files"][2]).read_text(encoding="utf-8"))
    assert pages["appliances"]["rows"]
    for row in pages["appliances"]["rows"]:
        assert "deelperiode" in row[2].lower()
        assert "6-31 aug" in row[2].lower()


def test_page13_enphase_source_shows_partial_time_coverage(monkeypatch, tmp_path):
    _m, _input, result = _prepare_adapter(monkeypatch, tmp_path)
    pages = json.loads(Path(result["files"][2]).read_text(encoding="utf-8"))
    enphase = next(row for row in pages["quality"]["sources"] if row[0] == "Enphase")
    joined = " ".join(map(str, enphase))
    assert "81,7%" in joined
    assert "221,5" in joined
    assert "partieel" in joined.lower()
