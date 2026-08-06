from pathlib import Path
import json
import subprocess
import sys
from pypdf import PdfReader
import pytest

ROOT = Path(__file__).resolve().parents[1]

def run(data: Path, out: Path):
    subprocess.check_call([sys.executable, str(ROOT/'verwerk_maandupdate.py'), str(data), '-o', str(out)])

def test_example_data_valid():
    subprocess.check_call([sys.executable, str(ROOT/'validate_maanddata.py'), str(ROOT/'maanddata_voorbeeld.json')])

def test_generate_example(tmp_path):
    out=tmp_path/'example.pdf'; run(ROOT/'maanddata_voorbeeld.json',out)
    assert out.stat().st_size > 10000
    page=PdfReader(str(out)).pages[0]
    assert float(page.mediabox.width) == pytest.approx(595.2756, abs=.1)
    assert float(page.mediabox.height) == pytest.approx(841.8898, abs=.1)

def test_changed_monthdata_keeps_template_page_geometry(tmp_path):
    d=json.loads((ROOT/'maanddata_voorbeeld.json').read_text(encoding='utf-8'))
    d['rapport']['maand']='AUGUSTUS 2026'
    d['rapport']['rapportdatum']='31 augustus 2026'
    d['maand']['verbruik']['waarde']=999.9
    d['batterij']['score']=72
    alt=tmp_path/'augustus.json'; alt.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    a=tmp_path/'a.pdf'; b=tmp_path/'b.pdf'
    run(ROOT/'maanddata_voorbeeld.json',a); run(alt,b)
    pa,pb=PdfReader(str(a)).pages[0],PdfReader(str(b)).pages[0]
    assert len(PdfReader(str(a)).pages)==len(PdfReader(str(b)).pages)==1
    assert tuple(map(float,pa.mediabox)) == pytest.approx(tuple(map(float,pb.mediabox)),abs=.01)

def test_reject_wrong_fixed_length(tmp_path):
    d=json.loads((ROOT/'maanddata_voorbeeld.json').read_text(encoding='utf-8'))
    d['kpi_boven'].pop()
    bad=tmp_path/'bad.json'; bad.write_text(json.dumps(d),encoding='utf-8')
    p=subprocess.run([sys.executable,str(ROOT/'validate_maanddata.py'),str(bad)],capture_output=True,text=True)
    assert p.returncode != 0

def test_management_summary_color_order_is_stable():
    sys.path.insert(0, str(ROOT))
    from generate_energierapport_pagina1 import sorted_summary_items
    items = [
        {'kleur':'oranje','tekst':'o1'},
        {'kleur':'groen','tekst':'g1'},
        {'kleur':'rood','tekst':'r1'},
        {'kleur':'groen','tekst':'g2'},
        {'kleur':'oranje','tekst':'o2'},
    ]
    result = sorted_summary_items(items)
    assert [x['kleur'] for x in result] == ['groen','groen','oranje','oranje','rood']
    assert [x['tekst'] for x in result] == ['g1','g2','o1','o2','r1']
