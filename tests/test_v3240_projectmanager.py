from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_v3240_identity_and_embedded_projectmanager():
    assert (ROOT/"VERSIE.txt").read_text().strip()==CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT/"slimmemeterportal_import/config.yaml").read_text()
    app=ROOT/"slimmemeterportal_import/rootfs/app"
    mode=(app/"mode_entrypoint.py").read_text()
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in mode
    assert 'start_projectmanager_v2(app.STOP, root, TARGET_RELEASE_VERSION)' in mode
    assert (app/"projectmanager_v2_entrypoint.py").is_file()
    assert (app/"projectmanager_v2/manager_service.py").is_file()
    assert (app/"projectmanager_v2/embedded_runtime.py").is_file()
