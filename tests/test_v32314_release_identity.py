import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "slimmemeterportal_import/rootfs/app"


def test_v32314_release_identity_is_consistent():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.14"

    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert re.search(r'^version:\s*"32\.3\.14"\s*$', config, re.MULTILINE)

    entry = (APP_ROOT / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.3.14"' in entry

    main = (APP_ROOT / "main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.3.14"' in main


def test_v32314_changelog_documents_the_safety_release():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.startswith("## 32.3.14 — Release Validation Hold")
    for required in (
        "RELEASE VALIDATION HOLD",
        "DEVELOPMENT",
        "runtime",
        "automatische maandafsluiting",
        "noodvrijgave",
    ):
        assert required in changelog.split("## 32.3.13", 1)[0]


def test_v32314_keeps_existing_production_core_revision():
    main = (APP_ROOT / "main.py").read_text(encoding="utf-8")
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in main
