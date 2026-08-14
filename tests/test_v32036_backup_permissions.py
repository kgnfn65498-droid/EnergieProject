from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"

def test_v32036_release_identity_is_synchronized():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.0.36"
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    changelog = (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8")
    assert 'version: "32.0.36"' in config
    assert 'APP_VERSION = "32.0.36"' in main
    assert "## 32.0.36" in changelog
    assert changelog.count("\n## ") == 1

def test_v32036_preserves_report_fallback_and_month_safety():
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    assert "automatic_month_close_enabled: false" in config
    assert "def report_input_readiness(" in main
    assert "historical: bool = False" in main
    assert '"Historisch rapport informatief overgeslagen"' in main

def test_v32036_backup_permissions_and_watcher_retention_are_persistent():
    installer = (ROOT / "tools/release_installer.sh").read_text(encoding="utf-8")
    bootstrap = (ROOT / "tools/bootstrap_release_watcher_container.sh").read_text(encoding="utf-8")
    builder = PROJECT_ROOT / "Infra/Docker/native-mcp/build_nas_container_crash_recovery.sh"
    assert 'chgrp everyone "$BACKUPS"' in installer
    assert 'chmod 2775 "$BACKUPS"' in installer
    assert 'chgrp everyone "$BACKUP"' in installer
    assert 'chmod 660 "$BACKUP"' in installer
    assert '-e ENERGIE_BACKUP_RETENTION=999' in bootstrap
    assert '-e ENERGIE_PROCESSED_RETENTION=999' in bootstrap
    assert builder.is_file()
    assert 'chmod 660 "$OUT" "$SHA_FILE" "$VERIFY"' in builder.read_text(encoding="utf-8")
