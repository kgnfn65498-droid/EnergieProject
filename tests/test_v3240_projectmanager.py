from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_v3240_identity_and_embedded_projectmanager():
    assert (ROOT/"VERSIE.txt").read_text().strip()=="32.4.3"
    assert 'version: "32.4.3"' in (ROOT/"slimmemeterportal_import/config.yaml").read_text()
    app=ROOT/"slimmemeterportal_import/rootfs/app"
    mode=(app/"mode_entrypoint.py").read_text()
    assert 'TARGET_RELEASE_VERSION = "32.4.3"' in mode
    assert 'start_projectmanager_v2(app.STOP, root)' in mode
    assert (app/"projectmanager_v2_entrypoint.py").is_file()
    assert (app/"projectmanager_v2/manager_service.py").is_file()
    assert (app/"projectmanager_v2/embedded_runtime.py").is_file()
