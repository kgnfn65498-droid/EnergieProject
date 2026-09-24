from pathlib import Path
import zipfile
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
from minimal_release_preflight import verify_candidate

def test_preflight_rejects_atomic_forbidden_pytest_cache(tmp_path):
    root=tmp_path
    (root/"Inbox/incoming").mkdir(parents=True)
    (root/"App").mkdir(); (root/"App/VERSIE.txt").write_text("32.5.3")
    z=root/"Inbox/incoming/EnergieProject_v32.5.4.zip"
    with zipfile.ZipFile(z,"w") as a:
        a.writestr("VERSIE.txt","32.5.4")
        a.writestr("MANIFEST.sha256","")
        a.writestr("SHA256SUMS.json",'{"files":[]}')
        a.writestr(".pytest_cache/.gitignore","x")
    result=verify_candidate(root,z)
    assert result["status"]=="BLOCKED"
    assert "candidate_integrity_invalid" in result["blockers"]

def test_preflight_source_contains_atomic_forbidden_set():
    s=(ROOT/"tools/minimal_release_preflight.py").read_text()
    for token in [".pytest_cache","__pycache__",".DS_Store",".pyc",".pyo"]: assert token in s
