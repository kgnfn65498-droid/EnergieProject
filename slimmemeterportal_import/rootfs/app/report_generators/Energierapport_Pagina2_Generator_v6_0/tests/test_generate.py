import json, subprocess, sys
from pathlib import Path

def test_generate(tmp_path):
    root=Path(__file__).resolve().parents[1]
    out=tmp_path/'p2.pdf'
    subprocess.run([sys.executable,str(root/'src/generate_p2.py'),'--data',str(root/'data/juli_2026.json'),'--output',str(out)],check=True)
    assert out.exists() and out.stat().st_size>10000
    assert out.read_bytes()[:4]==b'%PDF'

def test_json_sections():
    root=Path(__file__).resolve().parents[1]
    data=json.loads((root/'data/juli_2026.json').read_text())
    for key in ['electricity','gas','costs','forecast','battery','term']:
        assert key in data

def test_generate_with_unknown_feed_in_compensation(tmp_path):
    root=Path(__file__).resolve().parents[1]
    source=json.loads((root/'data/juli_2026.json').read_text())
    source['costs']['feed_in_compensation']=None
    source['costs']['feed_in_tariff']=None
    data_file=tmp_path/'page_2_unknown_compensation.json'
    data_file.write_text(json.dumps(source), encoding='utf-8')
    out=tmp_path/'p2_unknown_compensation.pdf'
    completed=subprocess.run(
        [sys.executable,str(root/'src/generate_p2.py'),'--data',str(data_file),'--output',str(out)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert out.exists() and out.stat().st_size>10000
    assert out.read_bytes()[:4]==b'%PDF'
