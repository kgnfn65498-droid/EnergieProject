from pathlib import Path
ROOT=Path(__file__).parents[1]
MAIN=ROOT/'slimmemeterportal_import/rootfs/app/main.py'
P1=ROOT/'slimmemeterportal_import/rootfs/app/report_generators/Energierapport_Pagina1_Echte_Generator_v7/generate_energierapport_pagina1.py'
P2=ROOT/'slimmemeterportal_import/rootfs/app/report_generators/Energierapport_Pagina2_Generator_v6_0/src/generate_p2.py'

def test_dynamic_year_comparison():
 s=P1.read_text(); assert 'VS. JULI 2025' not in s and 'comparison_label' in s

def test_july_contract_index_and_finance_fail_closed():
 s=MAIN.read_text(); assert 'contract_month_index = (month - 7) % 12' in s; assert 'page1["kpi_onder"] = [' in s; assert '"Niet beschikbaar"' in s

def test_gas_current_contract_year_and_canonical_output():
 s=MAIN.read_text(); assert '_gas_contract_year_series' in s and 'page2["gas"]["series"]' in s; block=s.split('def publish_month_output(',1)[1].split('def publish_durable_report_package(',1)[0]; assert 'transfer_folder.parent / "02_Output"' not in block; assert 'NAS_DATA_ROOT / "02_Output" / "Rapportages" / month_key' in block

def test_page2_missing_future_values_safe():
 s=P2.read_text(); assert 'numeric_vals' in s and 'if not isinstance(v, (int, float))' in s
