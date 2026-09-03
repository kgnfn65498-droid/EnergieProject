import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'slimmemeterportal_import/rootfs/app/main.py'
P1 = ROOT / 'slimmemeterportal_import/rootfs/app/report_generators/Energierapport_Pagina1_Echte_Generator_v7/generate_energierapport_pagina1.py'
P2 = ROOT / 'slimmemeterportal_import/rootfs/app/report_generators/Energierapport_Pagina2_Generator_v6_0/src/generate_p2.py'
P313 = ROOT / 'slimmemeterportal_import/rootfs/app/report_generators/Energierapport_Pagina3_tm_13_Generator_v1_0/src/generate_pages_3_13.py'


def load_main(name='v32322_main'):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_release_identity_32322():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.3.29'
    assert 'APP_VERSION = "32.3.29"' in MAIN.read_text(encoding='utf-8')
    assert 'version: "32.3.29"' in (ROOT/'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')


def test_offer_summary_carries_report_profile_and_contract_period_context():
    m = load_main('v32322_offer')
    offer = m.nextenergy_offer_financial_summary()
    assert offer['current_monthly_advance_eur'] == 150.0
    assert offer['offer_monthly_projection_eur'] == 153.0
    assert offer['offer_annual_projection_eur'] == 1836.0
    assert offer['expected_annual_payments_eur'] == 1800.0
    assert offer['expected_balance_eur'] == -36.0
    assert offer['offer_profile_import_kwh'] == 4900.0
    assert offer['offer_profile_export_kwh'] == 4250.0
    assert offer['offer_profile_gas_m3'] == 700.0
    aug = m.report_contract_context(2026, 8)
    assert aug['start'] == '15 juli 2026'
    assert 'Dynamisch' in aug['type'] and 'gasplafond' not in aug['type'].lower()
    sep = m.report_contract_context(2026, 9)
    assert sep['start'] == '3 september 2026'
    assert 'gasplafond' in sep['type'].lower()


def test_smp_coverage_accepts_month_summary_daily_aggregate_when_raw_interval_file_missing(tmp_path):
    m = load_main('v32322_coverage')
    month = '2026_08'
    (tmp_path/'connections.json').write_text(json.dumps([
        {'meter_identifier':'E1','connection_type':'elektriciteit'},
        {'meter_identifier':'G1','connection_type':'gas'},
    ]), encoding='utf-8')
    days = [{'date': f'2026-08-{day:02d}', 'records': 1, 'expected_records':[1], 'status':'ok'} for day in range(1,32)]
    (tmp_path/'month_summary.json').write_text(json.dumps({'target_month':'2026-08','connections':[
        {'connection_id':'E1','connection_type':'elektriciteit','days':days},
        {'connection_id':'G1','connection_type':'gas','days':days},
    ]}), encoding='utf-8')
    result = m.validate_smp_content_coverage(tmp_path, month)
    assert result['status'] == 'ok'
    assert result['days_with_measurements'] == 62
    assert result['errors'] == []


def test_page1_has_no_stale_partial_july_copy_and_dynamic_page_count():
    s = P1.read_text(encoding='utf-8')
    assert 'Pagina 1 van 7' not in s
    assert 'slechts 8 meetdagen' not in s
    assert '15 t/m 22 juli 2026' not in s
    assert "d['rapport']['paginas']" in s
    assert 'score_beschikbaar' in s


def test_page2_finance_and_forecast_use_known_offer_values_not_blank_wall():
    s = P2.read_text(encoding='utf-8')
    assert 'Offerteprognose per maand' in s
    assert 'Verwachte betalingen per jaar' in s
    assert 'NextEnergy-offerteprofiel' in s
    assert 'Het gasverbruik is beïnvloed door het weer' not in s
    assert 'degree_days_available' in s


def test_pages_3_13_have_no_demo_july_or_fake_appliance_semantics():
    s = P313.read_text(encoding='utf-8')
    banned = [
        'bronwaarden deels zijn verzonnen',
        'overgenomen uit juli 2025',
        'Sterke julimaand',
        'EPEX gekoppeld',
        'Begin augustus',
        'Echte juli-data',
        '8,6',
        '225,5',
        '€ 39,63',
        '€ 170,00',
        '11,6 jaar',
    ]
    for phrase in banned:
        assert phrase not in s
    assert "d['appliances']['rows']" in s
    assert "d['quality']['checks']" in s
    assert "d['finance']['rows']" in s
    assert "d['forecast']['rows']" in s


def test_adapter_has_source_safe_solar_and_unified_battery_and_contract_years():
    s = MAIN.read_text(encoding='utf-8')
    assert 'solar_metrics_reliable' in s
    assert 'battery_report_summary()' in s
    assert '_historical_contract_year_rows()' in s
    assert 'offer_profile_import_kwh' in s
    assert 'page2["forecast"].update({' in s
    assert 'pages["finance"]' in s
    assert 'pages["quality"]' in s


def test_canonical_output_guard_remains_and_wrong_nested_output_not_reintroduced():
    s = MAIN.read_text(encoding='utf-8')
    block=s.split('def publish_month_output(',1)[1].split('def publish_durable_report_package(',1)[0]
    assert 'NAS_DATA_ROOT / "02_Output" / "Rapportages" / month_key' in block
    assert 'transfer_folder.parent / "02_Output"' not in block
    assert '01_Input/02_Output' not in block


def test_adapter_clears_remaining_page1_page2_fixture_values_and_does_not_seed_pages313_from_demo():
    s = MAIN.read_text(encoding='utf-8')
    assert 'top[6].update({' in s
    assert '"titel": "Energiescore"' in s
    assert '"waarde": "n.b."' in s
    assert 'page2["costs"]["trend_previous"] = [None] * 12' in s
    assert 'page2["costs"]["trend_current"] = [None] * 12' in s
    assert 'pages = load_generator_example("pages_3_13")' not in s
    assert 'pages = {' in s


def test_report_month_labels_are_dutch_and_page2_unavailable_gas_kpis_are_compact():
    m = load_main('v32322_dutch_months')
    assert m._dutch_month_name(8) == 'augustus'
    assert m._dutch_month_label(2026, 8) == 'augustus 2026'
    s = P2.read_text(encoding='utf-8')
    assert "('Graaddagen'," in s and "else 'n.b.','' if degree_days_available else 'niet gekoppeld'" in s
    assert "('Weerscorrectie'," in s and "else 'n.b.','' if degree_days_available else 'niet toegepast'" in s
    assert "'nog niet gevalideerd'" in s


def test_page2_contract_history_header_does_not_claim_wrong_fixed_start_day():
    s = P2.read_text(encoding='utf-8')
    assert "Contractjaarhistorie" in s
    assert "Contractjaar (15 jul - 15 jul)" not in s


def test_closed_month_prefers_complete_smp_over_partial_p1_and_reports_full_coverage(tmp_path, monkeypatch):
    m = load_main('v32322_source_priority')
    month = '2026_08'
    # P1 is only present from 6 August onward, so its cumulative delta is partial.
    (tmp_path / 'P1e.csv').write_text(
        'captured_at,total_power_import_kwh,total_power_export_kwh\n'
        '2026-08-06T00:15:00+02:00,100,200\n'
        '2026-08-31T23:45:00+02:00,150,260\n',
        encoding='utf-8',
    )
    (tmp_path / 'P1g.csv').write_text(
        'captured_at,total_gas_m3\n'
        '2026-08-06T00:15:00+02:00,500\n'
        '2026-08-31T23:45:00+02:00,507\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(m, 'load_smp_month_metrics', lambda key: {
        'status': 'ready', 'coverage_status': 'ok',
        'grid_import_kwh': 180.0, 'grid_export_kwh': 300.0, 'gas_m3': 9.0,
        'days_expected': 62, 'days_covered': 62, 'errors': [],
    })
    result = m._month_energy_metrics(month, input_folder=tmp_path)
    assert result['metrics']['grid_import_kwh'] == 180.0
    assert result['metrics']['grid_export_kwh'] == 300.0
    assert result['metrics']['gas_m3'] == 9.0
    assert result['quality']['grid_import_source'] == 'slimmemeterportal_full_month_primary'
    assert result['quality']['grid_export_source'] == 'slimmemeterportal_full_month_primary'
    assert result['quality']['gas_source'] == 'slimmemeterportal_full_month_primary'
    assert result['quality']['p1_coverage']['complete'] is False
    period = m._report_period_from_resolved_quality(month, result['quality'])
    assert period['completeness'] == 'FULL'
    assert period['period_start_date'] == '2026-08-01'
    assert period['period_end_date'] == '2026-08-31'
    assert period['source'] == 'slimmemeterportal_full_month_primary'


def test_smp_month_metrics_reads_complete_monthly_jsonl_when_raw_daily_files_are_aggregate_placeholders(tmp_path, monkeypatch):
    m = load_main('v32322_smp_jsonl')
    month = '2026_08'
    (tmp_path / 'raw').mkdir()
    coverage = {
        'status': 'ok', 'missing_days': [], 'empty_days': [], 'errors': [],
        'available_through': '2026-08-31', 'calendar_expected_through': '2026-08-31',
        'days_expected': 62, 'days_with_measurements': 62,
    }
    (tmp_path / 'content_coverage_report.json').write_text(json.dumps(coverage), encoding='utf-8')
    # The monthly exports are authoritative when raw daily files are placeholders.
    (tmp_path / 'elektriciteit_E1_2026_08.jsonl').write_text(
        json.dumps({'meter_identifier':'E1','_date':'2026-08-01','_connection_type':'elektriciteit',
                    'usages': json.dumps([{'delivery_low':'1,50','returned_delivery_low':'2,50'}])}) + '\n',
        encoding='utf-8',
    )
    (tmp_path / 'gas_G1_2026_08.jsonl').write_text(
        json.dumps({'meter_identifier':'G1','_date':'2026-08-01','_connection_type':'gas',
                    'usages': json.dumps([{'delivery':'3,00'}])}) + '\n',
        encoding='utf-8',
    )
    monkeypatch.setattr(m, '_smp_source_candidates', lambda key: [tmp_path])
    result = m.load_smp_month_metrics(month)
    assert result['status'] == 'ready'
    assert result['grid_import_kwh'] == 1.5
    assert result['grid_export_kwh'] == 2.5
    assert result['gas_m3'] == 3.0
    assert result['data_shape'] == 'monthly_jsonl'
