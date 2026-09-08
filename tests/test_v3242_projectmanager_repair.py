from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'

def test_v3242_release_identity_and_pm_entrypoints():
    assert (ROOT / 'VERSIE.txt').read_text().strip() == CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / 'main.py').read_text()
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text()
    assert (PM / 'VERSION.txt').read_text().strip() == CURRENT_PM_VERSION

def test_v3242_single_writer_and_local_approval_contract():
    mode = (APP / 'mode_entrypoint.py').read_text()
    entry = (APP / 'projectmanager_v2_entrypoint.py').read_text()
    package_tools = (PM / 'tools_projectmanager.py').read_text()
    api = (PM / 'projectmanager_api.py').read_text()
    assert 'install_projectmanager_web(app, root)' in mode
    assert entry.index('from service_lock import FileLock') < entry.index('from orchestrator import ProjectmanagerRuntime')
    assert '@mcp.tool' not in package_tools
    assert 'direct RuntimeV2 command writes disabled' in api
    assert (PM / 'command_ingress.py').is_file()
    assert (PM / 'approval_ingress.py').is_file()
    assert (PM / 'runtime_truth.py').is_file()
    assert (PM / 'roadmap_regie.py').is_file()
