import importlib.util
import json
from datetime import datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_main(name: str):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_quarter(data_root: Path, stamp: str, *, imp: float, exp: float, gas: float, market: float = 0.05, supplier: float = 0.1827):
    month_key = f"{stamp[:4]}_{stamp[4:6]}"
    folder = data_root / "01_Input" / month_key / "HomeAssistant" / "QuarterHour"
    folder.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "created_at": datetime.strptime(stamp, "%Y%m%dT%H%M%SZ").isoformat() + "+00:00",
        "entities": [
            {"entity_id": "sensor.p1_meter_energie_import", "state": str(imp), "unit_of_measurement": "kWh"},
            {"entity_id": "sensor.p1_meter_energie_export", "state": str(exp), "unit_of_measurement": "kWh"},
            {"entity_id": "sensor.gas_meter_gas", "state": str(gas), "unit_of_measurement": "m³"},
            {"entity_id": "sensor.nordpool_kwh_nl_eur_3_10_021", "state": str(market), "unit_of_measurement": "EUR/kWh"},
            {"entity_id": "sensor.nextenergy_actuele_stroomprijs", "state": str(supplier), "unit_of_measurement": "EUR/kWh"},
        ],
        "collector": {"type": "quarter_hour", "quarter_key": stamp},
    }
    (folder / f"home_assistant_quarter_{stamp}.json").write_text(json.dumps(payload), encoding="utf-8")


def write_p1(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "P1e.csv").write_text(
        "total_power_import_kwh,total_power_export_kwh\n100,20\n101,20.5\n",
        encoding="utf-8",
    )
    (folder / "P1g.csv").write_text("total_gas_m3\n50\n50.1\n", encoding="utf-8")


def official_contract_payload():
    return {
        "supplier": "NextEnergy",
        "effective_from": "2026-07-16",
        "supplier_fixed_costs_eur_per_month": 5.99,
        "supplier_markup_eur_per_kwh": 0.0219,
        "export_compensation_eur_per_kwh": None,
        "export_compensation_formula": {
            "type": "market_price_minus_markup",
            "markup_eur_per_kwh": 0.0,
        },
        "gas_supplier_formula": {
            "type": "market_price_plus_markup",
            "markup_eur_per_m3": 0.0799,
        },
        "electricity_fixed_delivery_eur_per_month": 5.99,
        "gas_fixed_delivery_eur_per_month": 5.99,
        "electricity_energy_tax_eur_per_kwh": 0.1108,
        "gas_energy_tax_eur_per_m3": 0.7268,
        "energy_tax_reduction_eur_per_year": 628.96,
        "distribution_electricity_eur_per_year": 475.83,
        "distribution_gas_eur_per_year": 266.36,
        "contract_advance_eur_per_month": 118.0,
        "solar_bonus": {
            "percentage": 0.50,
            "start_hour_local": 6,
            "end_hour_local": 22,
            "positive_market_price_only": True,
            "annual_eligible_export_cap_kwh": 6000.0,
            "solar_export_source_mode": "solar_only_current_installation",
        },
    }


def test_current_month_quarter_hour_cumulative_metrics_override_sparse_p1(monkeypatch, tmp_path):
    m = load_main("v3230_quarter_primary")
    month_key = datetime.now(m.TZ).strftime("%Y_%m")
    data_root = tmp_path / "Data"
    monkeypatch.setattr(m, "NAS_DATA_ROOT", data_root)
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    monkeypatch.setattr(m, "load_smp_month_metrics", lambda key: {"status": "not_available"})
    monkeypatch.setattr(m, "_epex_month_context", lambda key: {})

    day = month_key.replace("_", "") + "05"
    write_quarter(data_root, f"{day}T120000Z", imp=100.0, exp=20.0, gas=50.0)
    write_quarter(data_root, f"{day}T121500Z", imp=101.5, exp=20.7, gas=50.1)
    write_quarter(data_root, f"{day}T123000Z", imp=104.0, exp=22.0, gas=50.2)
    p1_folder = tmp_path / "month_input" / month_key
    write_p1(p1_folder)

    result = m._month_energy_metrics(month_key, input_folder=p1_folder)

    assert result["metrics"]["grid_import_kwh"] == 4.0
    assert result["metrics"]["grid_export_kwh"] == 2.0
    assert result["metrics"]["gas_m3"] == 0.2
    assert result["quality"]["grid_import_source"] == "home_assistant_quarter_hour_primary"
    assert result["quality"]["grid_export_source"] == "home_assistant_quarter_hour_primary"
    assert result["quality"]["gas_source"] == "home_assistant_quarter_hour_primary"
    q = result["quality"]["quarter_hour"]
    assert q["sample_count"] == 3
    assert q["expected_slot_count"] == 3
    assert q["missing_slot_count"] == 0
    assert q["coverage_status"] == "partial_current_month"
    assert q["first_snapshot"].endswith("T120000Z")
    assert q["last_snapshot"].endswith("T123000Z")


def test_quarter_hour_meter_reset_is_rejected_not_summed(monkeypatch, tmp_path):
    m = load_main("v3230_quarter_reset")
    month_key = datetime.now(m.TZ).strftime("%Y_%m")
    data_root = tmp_path / "Data"
    monkeypatch.setattr(m, "NAS_DATA_ROOT", data_root)
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    day = month_key.replace("_", "") + "06"
    write_quarter(data_root, f"{day}T120000Z", imp=100.0, exp=20.0, gas=50.0)
    write_quarter(data_root, f"{day}T121500Z", imp=99.0, exp=21.0, gas=50.1)

    result = m._quarter_hour_month_metrics(month_key)

    assert result["available"] is False
    assert result["metrics"]["grid_import_kwh"] is None
    assert "sensor.p1_meter_energie_import" in result["invalid_cumulative_entities"]


def test_closed_month_keeps_existing_p1_precedence(monkeypatch, tmp_path):
    m = load_main("v3230_closed_month")
    data_root = tmp_path / "Data"
    monkeypatch.setattr(m, "NAS_DATA_ROOT", data_root)
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    monkeypatch.setattr(m, "load_smp_month_metrics", lambda key: {"status": "not_available"})
    monkeypatch.setattr(m, "_epex_month_context", lambda key: {})
    month_key = "2026_07"
    write_quarter(data_root, "20260705T120000Z", imp=100.0, exp=20.0, gas=50.0)
    write_quarter(data_root, "20260705T121500Z", imp=120.0, exp=30.0, gas=60.0)
    p1_folder = tmp_path / "month_input" / month_key
    write_p1(p1_folder)

    result = m._month_energy_metrics(month_key, input_folder=p1_folder)

    assert result["metrics"]["grid_import_kwh"] == 1.0
    assert result["metrics"]["grid_export_kwh"] == 0.5
    assert result["metrics"]["gas_m3"] == 0.1
    assert result["quality"]["grid_import_source"] == "p1"


def test_extended_official_contract_schema_is_valid(monkeypatch, tmp_path):
    m = load_main("v3230_contract_schema")
    path = tmp_path / "nextenergy_contract_costs.json"
    path.write_text(json.dumps(official_contract_payload()), encoding="utf-8")
    monkeypatch.setattr(m, "CONTRACT_COSTS_FILE", path)

    result = m.load_nextenergy_contract_costs()

    assert result["valid"] is True
    assert result["effective_from"] == "2026-07-16"
    assert result["electricity_fixed_delivery_eur_per_month"] == 5.99
    assert result["gas_fixed_delivery_eur_per_month"] == 5.99
    assert result["electricity_energy_tax_eur_per_kwh"] == 0.1108
    assert result["gas_energy_tax_eur_per_m3"] == 0.7268
    assert result["energy_tax_reduction_eur_per_year"] == 628.96
    assert result["solar_bonus"]["percentage"] == 0.5


def test_contract_period_model_applies_energy_tax_reduction_once():
    m = load_main("v3230_contract_model")
    costs = official_contract_payload()

    result = m.calculate_nextenergy_modeled_period_cost(
        grid_import_kwh=1000.0,
        grid_export_kwh=0.0,
        gas_m3=100.0,
        electricity_market_import_cost_eur=50.0,
        electricity_market_export_value_eur=0.0,
        gas_market_cost_eur=40.0,
        solar_bonus_eur=0.0,
        coverage_days=365.0,
        days_in_month=30,
        contract_costs=costs,
    )

    assert result["available"] is True
    assert result["energy_tax_reduction_eur"] == 628.96
    # A second per-product reduction would be 1257.92 and must never appear.
    assert result["energy_tax_reduction_eur"] != 1257.92
    expected = (
        50.0 + 1000 * 0.0219 + 1000 * 0.1108
        + 40.0 + 100 * 0.0799 + 100 * 0.7268
        + (5.99 + 5.99) * (365 / 30)
        + 475.83 + 266.36 - 628.96
    )
    assert result["modeled_contract_cost_eur"] == round(expected, 2)
    assert result["invoice_actual_eur"] is None


def test_solar_bonus_is_conditional_and_capped():
    m = load_main("v3230_solar_bonus")
    costs = official_contract_payload()

    eligible = m.calculate_solar_bonus_interval(
        export_kwh=2.0,
        market_price_eur_per_kwh=0.10,
        timestamp_utc="20260816T120000Z",  # 14:00 Europe/Amsterdam
        contract_costs=costs,
        solar_origin_confirmed=True,
        meter_data_complete=True,
        annual_export_before_interval_kwh=5999.0,
    )
    assert eligible["available"] is True
    assert eligible["eligible_export_kwh"] == 1.0
    assert eligible["bonus_eur"] == 0.05

    night = m.calculate_solar_bonus_interval(
        export_kwh=1.0,
        market_price_eur_per_kwh=0.10,
        timestamp_utc="20260816T230000Z",  # 01:00 local next day
        contract_costs=costs,
        solar_origin_confirmed=True,
        meter_data_complete=True,
        annual_export_before_interval_kwh=100.0,
    )
    assert night["available"] is True
    assert night["bonus_eur"] == 0.0
    assert night["reason"] == "outside_bonus_hours"

    unknown_origin = m.calculate_solar_bonus_interval(
        export_kwh=1.0,
        market_price_eur_per_kwh=0.10,
        timestamp_utc="20260816T120000Z",
        contract_costs=costs,
        solar_origin_confirmed=False,
        meter_data_complete=True,
        annual_export_before_interval_kwh=100.0,
    )
    assert unknown_origin["available"] is False
    assert unknown_origin["reason"] == "solar_origin_not_confirmed"


def test_supplier_contract_context_uses_current_price_ceiling_contract(monkeypatch):
    m = load_main("v3230_contract_context")
    monkeypatch.setattr(m, "home_assistant_entity", lambda entity_id: {"state": "0.2", "attributes": {"unit_of_measurement": "EUR/kWh"}, "last_updated": "x"})
    context = m._supplier_contract_context()
    assert context["contract"]["contract_start"] == "2026-09-03"
    assert context["contract"]["contract_end"] == "2027-09-03"
    assert context["contract"]["gas_pricing"] == "price_ceiling"
    assert context["contract"]["gas_price_ceiling_eur_per_m3"] == 0.8558


def test_observed_nextenergy_price_cost_does_not_add_markup_twice():
    m = load_main("v3230_no_double_markup")
    costs = official_contract_payload()
    result = m.calculate_observed_nextenergy_electricity_cost(
        observed_variable_cost_eur=13.77,
        observed_import_kwh=100.0,
        coverage_days=15.0,
        days_in_month=30,
        contract_costs=costs,
    )
    # NextEnergy live price already reflects market + 0.0219 markup + 0.1108 energy tax.
    assert result["supplier_markup_included_in_observed_price"] is True
    assert result["energy_tax_included_in_observed_price"] is True
    assert result["fixed_delivery_cost_prorated_eur"] == 3.0
    assert result["observed_supplier_electricity_cost_eur"] == 16.77


def test_report_coverage_metadata_for_quarter_hour_is_partial():
    m = load_main("v3230_report_period")
    quality = {
        "quarter_hour": {
            "available": True,
            "sample_count": 1022,
            "first_snapshot": "20260805T143000Z",
            "last_snapshot": "20260816T163000Z",
            "coverage_status": "partial_current_month",
            "missing_slot_count": 0,
        }
    }
    result = m._report_period_from_resolved_quality("2026_08", quality)
    assert result["completeness"] == "PARTIAL"
    assert result["source"] == "home_assistant_quarter_hour_primary"
    assert result["sample_count"] == 1022
    assert result["period_start_date"] == "2026-08-05"
    assert result["period_end_date"] == "2026-08-16"
    assert "5 t/m 16" in result["period_label"]


def test_release_contains_non_secret_official_nextenergy_contract_config():
    path = ROOT / "00_Config" / "nextenergy_contract_costs.json"
    assert path.is_file()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["effective_from"] == "2026-07-16"
    assert raw["supplier_markup_eur_per_kwh"] == 0.0219
    assert raw["gas_supplier_formula"]["markup_eur_per_m3"] == 0.0799
    assert raw["electricity_fixed_delivery_eur_per_month"] == 5.99
    assert raw["gas_fixed_delivery_eur_per_month"] == 5.99
    assert raw["electricity_energy_tax_eur_per_kwh"] == 0.1108
    assert raw["gas_energy_tax_eur_per_m3"] == 0.7268
    assert raw["energy_tax_reduction_eur_per_year"] == 628.96
    assert raw["distribution_electricity_eur_per_year"] == 475.83
    assert raw["distribution_gas_eur_per_year"] == 266.36
    assert raw["contract_advance_eur_per_month"] == 118.0
    text = path.read_text(encoding="utf-8").lower()
    for forbidden in ("iban", "klantnummer", "contractnummer", "geboortedatum", "@icloud.com", "van den boomstraat"):
        assert forbidden not in text


def test_contract_validation_distinguishes_modeled_components_from_invoice_actual(monkeypatch, tmp_path):
    m = load_main("v3230_contract_validation_extended")
    path = tmp_path / "nextenergy_contract_costs.json"
    path.write_text(json.dumps(official_contract_payload()), encoding="utf-8")
    monkeypatch.setattr(m, "CONTRACT_COSTS_FILE", path)
    costs = m.load_nextenergy_contract_costs()
    status = m.build_contract_validation_status(costs)
    assert status["all_required_components_present"] is True
    assert status["modeled_contract_components_ready"] is True
    assert status["invoice_actuals_present"] is False
    assert status["invoice_actuals_required_for_invoice_actual_claim"] is True
    assert status["components"]["solar_bonus"] is True
    assert status["components"]["energy_tax_reduction"] is True


def test_apply_contract_preserves_project_150_and_records_original_118(monkeypatch, tmp_path):
    m = load_main("v3230_contract_advance")
    path = tmp_path / "nextenergy_contract_costs.json"
    path.write_text(json.dumps(official_contract_payload()), encoding="utf-8")
    monkeypatch.setattr(m, "CONTRACT_COSTS_FILE", path)
    ctx = m._supplier_contract_context()
    m.apply_nextenergy_contract_costs(ctx)
    assert ctx["contract"]["monthly_advance_eur"] == 150.0
    assert ctx["contract"]["original_contract_advance_eur"] == 118.0
    assert ctx["cost_model"]["modeled_contract_components_ready"] is True
    assert ctx["cost_model"]["invoice_actuals_known"] is False
