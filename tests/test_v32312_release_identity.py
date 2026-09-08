from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_v32314_identity_is_consistent():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == CURRENT_RELEASE
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    entry = (ROOT / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py").read_text(encoding="utf-8")
    run_sh = (ROOT / "slimmemeterportal_import/run.sh").read_text(encoding="utf-8")
    assert re.search(rf'version:\s*"{re.escape(CURRENT_RELEASE)}"', config)
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in entry
    assert "app.APP_VERSION = TARGET_RELEASE_VERSION" in entry
    assert "exec python3 -u /app/mode_entrypoint.py" in run_sh
