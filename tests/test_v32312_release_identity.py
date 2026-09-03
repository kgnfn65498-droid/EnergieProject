import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_v32314_identity_is_consistent():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.26"
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    entry = (ROOT / "slimmemeterportal_import/rootfs/app/mode_entrypoint.py").read_text(encoding="utf-8")
    run_sh = (ROOT / "slimmemeterportal_import/run.sh").read_text(encoding="utf-8")
    assert re.search(r'version:\s*"32\.3\.26"', config)
    assert 'TARGET_RELEASE_VERSION = "32.3.26"' in entry
    assert "app.APP_VERSION = TARGET_RELEASE_VERSION" in entry
    assert "exec python3 -u /app/mode_entrypoint.py" in run_sh
