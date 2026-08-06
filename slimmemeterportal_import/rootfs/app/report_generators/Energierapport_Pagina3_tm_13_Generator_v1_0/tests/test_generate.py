from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/'src'))
from generate_pages_3_13 import generate

def test_generate(tmp_path):
    root=Path(__file__).parents[1]; out=tmp_path/'out.pdf'; generate(root/'data/juli_2026.json',out)
    assert out.exists() and out.stat().st_size>10000
    assert out.read_bytes().startswith(b'%PDF')
