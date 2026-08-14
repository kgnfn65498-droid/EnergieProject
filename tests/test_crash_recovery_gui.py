import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def test_crash_recovery_gui_shows_export_identity_and_cleanup_state():
    source = MAIN.read_text(encoding="utf-8")

    for required in (
        'id="complete-recovery-export-count"',
        "result.export_name||result.backup_name",
        "result.export_sha256||result.backup_sha256||result.sha256",
        "result.export_file_count",
        "result.download_status",
        "result.cleanup_status",
        "bewaar hem zelf in iCloud",
        "tijdelijke Crash-Recovery-bestanden op de NAS zijn opgeruimd",
        "download is afgebroken; niets is opgeruimd",
    ):
        assert required in source


def test_primary_gui_action_uses_one_export_flow():
    source = MAIN.read_text(encoding="utf-8")
    assert "fetch('api/crash-recovery/export'" in source
    assert "Download Crash Recovery ZIP" in source
    assert "window.location.href='api/crash-recovery/download'" in source


def test_gui_keeps_safety_language_visible():
    source = MAIN.read_text(encoding="utf-8")
    assert "Sluit de maand niet af" in source
    assert "RestoreStaging overschrijft geen productiedata" in source
