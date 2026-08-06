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
