import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / 'slimmemeterportal_import/rootfs/app/main.py'


def load_main(name: str):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_nextenergy_offer_financial_summary_uses_confirmed_terms():
    m = load_main('v32321_finance_summary')
    result = m.nextenergy_offer_financial_summary()
    assert result['current_monthly_advance_eur'] == 150.0
    assert result['offer_monthly_projection_eur'] == 153.0
    assert result['offer_annual_projection_eur'] == 1836.0
    assert result['expected_annual_payments_eur'] == 1800.0
    assert result['expected_balance_eur'] == -36.0
    assert result['monthly_difference_eur'] == 3.0
    assert result['source_label'] == 'NextEnergy-offerteprognose'


def test_report_overview_href_uses_home_assistant_ingress_base():
    m = load_main('v32321_report_href')
    assert m.report_overview_href('/api/hassio_ingress/abc123') == '/api/hassio_ingress/abc123/'
    assert m.report_overview_href('/api/hassio_ingress/abc123/') == '/api/hassio_ingress/abc123/'
    assert m.report_overview_href('') == './'


def test_nonconfigured_epex_sources_are_hidden_from_visible_source_list():
    m = load_main('v32321_visible_sources')
    result = m.visible_workflow_sources({
        'slimmemeterportal': 'ready',
        'homewizard': 'ready',
        'enphase': 'not_configured',
        'epex_electricity': 'not_configured',
        'epex_gas': 'not_configured',
    })
    assert result == {
        'slimmemeterportal': 'ready',
        'homewizard': 'ready',
        'enphase': 'not_configured',
    }


def test_report_payload_wires_confirmed_offer_into_page1_and_page2():
    source = MAIN.read_text(encoding='utf-8')
    assert 'offer_finance = nextenergy_offer_financial_summary()' in source
    assert '"Verwachte jaarkosten"' in source
    assert 'offer_finance["offer_annual_projection_eur"]' in source
    assert 'offer_finance["expected_annual_payments_eur"]' in source
    assert '"advice": offer_finance["offer_monthly_projection_eur"]' in source
    assert '"annual_cost": offer_finance["offer_annual_projection_eur"]' in source
    assert '"balance": offer_finance["expected_balance_eur"]' in source


def test_current_release_identity():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.3.26'
    assert 'version: "32.3.26"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.3.26"' in MAIN.read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.3.26"' in (ROOT / 'slimmemeterportal_import/rootfs/app/mode_entrypoint.py').read_text(encoding='utf-8')
