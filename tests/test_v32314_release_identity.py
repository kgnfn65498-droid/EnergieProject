import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "slimmemeterportal_import/rootfs/app"


def test_v32314_release_identity_is_preserved_in_history():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.3.14 — Release Validation Hold" in changelog


def test_v32314_changelog_documents_the_safety_release():
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## 32.3.14 — Release Validation Hold" in changelog
    section = changelog.split("## 32.3.14 — Release Validation Hold", 1)[1].split("## 32.3.13", 1)[0].lower()
    for required in (
        "release validation hold",
        "development",
        "runtime",
        "automatische maandafsluiting",
        "noodvrijgave",
    ):
        assert required in section


def test_v32314_keeps_existing_production_core_revision():
    main = (APP_ROOT / "main.py").read_text(encoding="utf-8")
    assert 'PRODUCTION_CORE_REVISION = "9.4-core1"' in main
