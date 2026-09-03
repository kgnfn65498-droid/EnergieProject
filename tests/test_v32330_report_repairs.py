from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import' / 'rootfs' / 'app'
MAIN = APP / 'main.py'
P1 = APP / 'report_generators' / 'Energierapport_Pagina1_Echte_Generator_v7' / 'generate_energierapport_pagina1.py'
P2 = APP / 'report_generators' / 'Energierapport_Pagina2_Generator_v6_0' / 'src' / 'generate_p2.py'


def load_main():
    spec = importlib.util.spec_from_file_location('main_v32330', MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_term_remains_150_and_offer_projection_153():
    m = load_main()
    f = m.nextenergy_offer_financial_summary()
    assert f['current_monthly_advance_eur'] == 150.0
    assert f['offer_monthly_projection_eur'] == 153.0
    assert f['offer_annual_projection_eur'] == 1836.0


def test_august_degree_day_model_is_numeric():
    m = load_main()
    g = m.report_gas_weather_metrics(2026, 8, 9.074, previous_gas_m3=30.0)
    assert g['degree_days_available'] is True
    assert g['per_day'] == 0.293
    assert g['degree_days'] == 14.7
    assert g['previous_degree_days'] == 19.1
    assert g['per_degree_day'] == 0.617
    assert 'Eindhoven' in g['coverage_note']


def test_solar_model_produces_numeric_kpis_when_enphase_coverage_is_partial():
    m = load_main()
    r = m.report_solar_model_metrics(
        grid_import_kwh=193.83,
        grid_export_kwh=507.498,
        enphase_production_kwh=375.0,
        solar_balance_reliable=False,
    )
    assert r['modelled'] is True
    assert r['total_production_kwh'] >= 507.498
    assert 0 < r['self_use_pct'] < 100
    assert 0 < r['self_supply_pct'] < 100
    assert 'model' in r['label'].lower()


def test_page1_is_cumulative_waterfall_and_battery_is_historical_reference():
    source = P1.read_text(encoding='utf-8')
    assert 'cumulative' in source
    assert 'Historische referentie - herijking nodig' in source
    assert 'Historisch model t/m juli 2026' in source


def test_page2_uses_nice_dynamic_y_axis():
    source = P2.read_text(encoding='utf-8')
    assert 'nice_axis_step' in source
    assert 'range(0, axis_max+1, 10)' not in source


def test_historical_report_button_has_visible_feedback():
    source = MAIN.read_text(encoding='utf-8')
    assert 'Rapport wordt gemaakt…' in source
    assert 'Rapport succesvol herbouwd' in source
