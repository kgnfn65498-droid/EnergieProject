from pathlib import Path
import hashlib
import importlib.util
import zipfile

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'tools/release_artifact_retention.py'
spec = importlib.util.spec_from_file_location('release_artifact_retention', MOD)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _zip(path: Path, label: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('VERSIE.txt', label+'\n')
        z.writestr('payload.txt', label*3)
    return hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size


def test_32524_retention_keeps_three_and_latest_has_only_official_name(tmp_path):
    project = tmp_path/'project'
    sources = tmp_path/'sources'
    results=[]
    for index in range(1,5):
        source=sources/f'EnergieProject_v32.5.{20+index}.zip'
        sha,size=_zip(source, f'32.5.{20+index}')
        results.append(mod.retain_release_artifact(project, source, expected_sha256=sha, expected_size=size, retention=3))
    last=results[-1]
    assert last['status']=='GREEN'
    store=project/mod.STORE_RELATIVE
    zips=sorted(p.name for p in store.glob('*.zip'))
    assert len(zips)==3
    assert 'EnergieProject_v32.5.24.zip' in zips
    assert sum(name.startswith('previous_') for name in zips)==2
    assert not any(name == 'EnergieProject_v32.5.23.zip' for name in zips)
    assert len(last['entries'])==3
    assert last['entries'][0]['name']=='EnergieProject_v32.5.24.zip'
    assert last['entries'][0]['official_name'] is True


def test_32524_retention_same_version_new_candidate_archives_previous_identity(tmp_path):
    project=tmp_path/'project'; sources=tmp_path/'sources'
    a=sources/'EnergieProject_v32.5.24.zip'; sha_a,size_a=_zip(a,'candidate-A')
    mod.retain_release_artifact(project,a,expected_sha256=sha_a,expected_size=size_a,retention=3)
    b=sources/'EnergieProject_v32.5.24.zip'; sha_b,size_b=_zip(b,'candidate-B')
    result=mod.retain_release_artifact(project,b,expected_sha256=sha_b,expected_size=size_b,retention=3)
    store=project/mod.STORE_RELATIVE
    official=store/'EnergieProject_v32.5.24.zip'
    assert hashlib.sha256(official.read_bytes()).hexdigest()==sha_b
    assert any(p.name.startswith('previous_1__EnergieProject_v32.5.24') for p in store.glob('*.zip'))
    assert any(e['sha256']==sha_a for e in result['entries'][1:])
