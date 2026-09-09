from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_v32424_historical_scope_remains_documented_and_core3_is_preserved():
    root = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text(encoding="utf-8")
    assert "## 32.4.24 — legacy closure" in root
    assert 'PRODUCTION_CORE_REVISION = "9.4-core3"' in main
    section = root.split("## 32.4.24", 1)[1].split("## 32.4.23", 1)[0].lower()
    assert "legacy" in section
    assert "non-mutating" in section or "non_mutating" in section
    assert "roadmap" in section
