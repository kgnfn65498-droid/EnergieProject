from pathlib import Path
import importlib.util
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
PATHS = ROOT / "slimmemeterportal_import/rootfs/app/project_paths.py"
INSTALLER = ROOT / "tools/release_installer.sh"
CONFIG = ROOT / "slimmemeterportal_import/config.yaml"

def _load_paths_module():
    spec = importlib.util.spec_from_file_location("project_paths_test", PATHS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

def test_v32037_dynamic_project_energie_mount_resolution():
    module = _load_paths_module()
    with tempfile.TemporaryDirectory() as td:
        share = Path(td)
        mount = share / "Project Energie"
        (mount / "App").mkdir(parents=True)
        (mount / "App" / "VERSIE.txt").write_text("32.2.2\n", encoding="utf-8")
        (mount / "Inbox").mkdir()
        resolved_mount, resolved_layout = module.resolve_nas_roots(share)
        assert resolved_mount == mount
        assert resolved_layout == mount

def test_v32037_publication_contract_is_fail_closed():
    main = MAIN.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    assert 'version: "32.3.2"' in config
    assert "automatic_month_close_enabled: false" in config
    assert "github_publication_enabled: true" in config
    assert 'APP_VERSION = "32.3.2"' in main
    assert 'HA_PUBLICATION_REQUIRED = NAS_RELEASE_ROOT / "ha_publication_required.json"' in main
    assert "def _load_github_publication_contract" in main
    assert "def _prepare_validated_publication_source" in main
    assert "def _verify_github_remote_baseline" in main
    assert "_sync_project_to_github_worktree(release_source, GITHUB_WORKTREE)" in main
    assert "expected_previous_manifest_sha256" in main
    assert "processed_zip_sha256" in main
    assert "target_manifest_sha256" in main
    assert '"expected_previous_manifest_sha256":"$CURRENT_MANIFEST_SHA256"' in installer
    assert '"processed_zip_sha256":"$PROCESSED_SHA256"' in installer
    assert '"target_manifest_sha256":"$TARGET_MANIFEST_SHA256"' in installer
    assert "git push --force" not in main
    assert "git push -f" not in main

def test_v32037_preserves_release_and_month_safety():
    main = MAIN.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    bootstrap = (ROOT / "tools/bootstrap_release_watcher_container.sh").read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    assert "automatic_month_close_enabled: false" in config
    assert '-e ENERGIE_BACKUP_RETENTION=999' in bootstrap
    assert '-e ENERGIE_PROCESSED_RETENTION=999' in bootstrap
    assert 'chmod 2775 "$BACKUPS"' in installer
    assert 'chmod 660 "$BACKUP"' in installer
    assert 'LOGDIR="$INBOX/logs"' in installer
    assert 'mkdir -p "$INCOMING" "$PROCESSING" "$PROCESSED" "$FAILED" "$LOGDIR" "$BACKUPS"' in installer
    assert "def report_input_readiness(" in main
