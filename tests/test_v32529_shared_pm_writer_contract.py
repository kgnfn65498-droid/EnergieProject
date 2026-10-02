from pathlib import Path
import importlib.util
import stat
import pytest

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'tools/release_controller_service.py'

def load():
    spec=importlib.util.spec_from_file_location('rc529',MOD)
    m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def test_shared_pm_writer_contract_normalizes_exact_allowlist(tmp_path):
    m=load()
    rels=(
        'Data/03_Systeem/Projectmanager/Handover',
        'Data/03_Systeem/Projectmanager/ClearUp/Recovery',
        'Data/03_Systeem/Projectmanager/ClearUp/Exports',
        'Data/03_Systeem/Projectmanager/ClearUp/State',
    )
    for rel in rels:
        p=tmp_path/rel; p.mkdir(parents=True,exist_ok=True); p.chmod(0o755)
    result=m.ensure_projectmanager_shared_writer_contract(tmp_path)
    assert result['status']=='GREEN'
    assert result['directories']==list(rels)
    for rel in rels:
        assert stat.S_IMODE((tmp_path/rel).stat().st_mode)==0o1777

def test_shared_pm_writer_contract_refuses_symlink(tmp_path):
    m=load()
    real=tmp_path/'real'; real.mkdir()
    target=tmp_path/'Data/03_Systeem/Projectmanager/Handover'; target.parent.mkdir(parents=True)
    target.symlink_to(real,target_is_directory=True)
    with pytest.raises(RuntimeError,match='projectmanager_shared_writer_directory_unsafe'):
        m.ensure_projectmanager_shared_writer_contract(tmp_path)
