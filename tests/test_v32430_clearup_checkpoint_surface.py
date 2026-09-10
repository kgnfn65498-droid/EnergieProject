from pathlib import Path
import importlib.util
import sys

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
MAIN = APP / 'main.py'


def load_clearup():
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    spec = importlib.util.spec_from_file_location('project_clearup_32430', APP / 'project_clearup.py')
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_32430_checkpoint_uses_proven_runtime_writable_inbox_logs_surface():
    source = MAIN.read_text(encoding='utf-8')
    assert 'PROJECT_CLEARUP_RUNTIME_RELATIVE = Path("Inbox/logs/project_clearup_runtime.json")' in source
    assert 'PROJECT_CLEARUP_RUNTIME_RELATIVE = Path("Data/03_Systeem/Projectmanager/State/project_clearup_runtime.json")' not in source


def test_32430_root_resolution_is_persisted_before_clearup_gate():
    source = MAIN.read_text(encoding='utf-8')
    root_marker = '"phase": "root_resolved"'
    gate_call = 'result = run_approved_clearup_once('
    assert root_marker in source
    assert source.index(root_marker) < source.index(gate_call)


def test_32430_runtime_checkpoint_is_observational_not_a_dependency(tmp_path: Path):
    clearup = load_clearup()
    runtime = tmp_path / 'Inbox/logs/project_clearup_runtime.json'
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text('{"candidate":"App.__rollback_32.4.20"}', encoding='utf-8')
    assert clearup._reference_is_informational('Inbox/logs/project_clearup_runtime.json') is True


def test_32430_release_identity_is_consistent():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.30'
    assert 'version: "32.4.30"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert 'TARGET_RELEASE_VERSION = "32.4.30"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    assert 'APP_VERSION = "32.4.30"' in MAIN.read_text(encoding='utf-8')
