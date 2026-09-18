from pathlib import Path
import sys
APP=Path(__file__).resolve().parents[1]/'slimmemeterportal_import/rootfs/app'
sys.path.insert(0,str(APP))
import project_clearup

def test_appledouble_inside_protected_input_never_becomes_clearup_candidate(tmp_path: Path):
    p=tmp_path/'Data/01_Input/EPEX manual downlaod'
    p.mkdir(parents=True)
    (p/'._Download_EPEX_v6.command').write_bytes(b'AppleDouble')
    items=project_clearup._collect_candidates(tmp_path, keep_rollbacks=1)
    paths={x['source_path'] for x in items}
    assert 'Data/01_Input/EPEX manual downlaod/._Download_EPEX_v6.command' not in paths

def test_collect_candidates_never_returns_protected_paths(tmp_path: Path):
    p=tmp_path/'Data/01_Input/EPEX manual downlaod'
    p.mkdir(parents=True)
    (p/'._x').write_bytes(b'x')
    for item in project_clearup._collect_candidates(tmp_path, keep_rollbacks=1):
        assert not project_clearup._is_protected(item['source_path'])
