from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
CP_DIR = ROOT / 'tools' / 'control_plane'


def _load_bootstrap():
    sys.path.insert(0, str(CP_DIR))
    try:
        spec = importlib.util.spec_from_file_location('qnap_bootstrap_32524', CP_DIR / 'qnap_control_plane_bootstrap.py')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.pop(0)


def test_qnap_bootstrap_accepts_all_proven_project_roots():
    mod = _load_bootstrap()
    expected = {
        '/share/Energie_NAS/EnergieProject',
        '/share/AI Projecten/EnergieProject',
        '/share/CACHEDEV1_DATA/AI Projecten/EnergieProject',
    }
    assert mod.QNAP_ALLOWED_PROJECT_ROOTS == expected
    for root in expected:
        payload = mod.qnap_watcher_create_payload(root)
        assert f'{root}:/energy' in payload['HostConfig']['Binds']


def test_qnap_bootstrap_rejects_unknown_project_root():
    mod = _load_bootstrap()
    try:
        mod.qnap_watcher_create_payload('/tmp/not-energy-project')
    except RuntimeError as exc:
        assert 'onverwachte QNAP host project-root' in str(exc)
    else:
        raise AssertionError('unknown root accepted')
