from pathlib import Path
import importlib.util
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "slimmemeterportal_import/config.yaml"
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
PATHS = ROOT / "slimmemeterportal_import/rootfs/app/project_paths.py"
INSTALLER = ROOT / "tools/release_installer.sh"
BOOTSTRAP = ROOT / "tools/bootstrap_release_watcher_container.sh"

def _load_paths():
    spec = importlib.util.spec_from_file_location("project_paths_v32038", PATHS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

def test_v32038_release_identity():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.17"
    config = CONFIG.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    assert 'version: "32.3.17"' in config
    assert 'APP_VERSION = "32.3.17"' in main

def test_v32038_automatic_publication_contract_remains_fail_closed():
    config = CONFIG.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    assert "github_publication_enabled: true" in config
    assert "automatic_month_close_enabled: false" in config
    assert "def _load_github_publication_contract" in main
    assert "def _prepare_validated_publication_source" in main
    assert "def _verify_github_remote_baseline" in main
    assert "_sync_project_to_github_worktree(release_source, GITHUB_WORKTREE)" in main
    assert "processed_zip_sha256" in main
    assert "expected_previous_manifest_sha256" in main
    assert "target_manifest_sha256" in main
    assert '"reason":"validated_qnap_release_ready_for_github"' in installer
    assert 'LOGDIR="$INBOX/logs"' in installer
    assert "git push --force" not in main
    assert "git push -f" not in main

def test_v32038_project_energie_mount_and_retention_safety():
    module = _load_paths()
    with tempfile.TemporaryDirectory() as td:
        share = Path(td)
        mount = share / "Project Energie"
        (mount / "App").mkdir(parents=True)
        (mount / "App" / "VERSIE.txt").write_text("32.2.2\n", encoding="utf-8")
        (mount / "Inbox").mkdir()
        resolved_mount, resolved_layout = module.resolve_nas_roots(share)
        assert resolved_mount == mount
        assert resolved_layout == mount
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    assert '-e ENERGIE_BACKUP_RETENTION=999' in bootstrap
    assert '-e ENERGIE_PROCESSED_RETENTION=999' in bootstrap
