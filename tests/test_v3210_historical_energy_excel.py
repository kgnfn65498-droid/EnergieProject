from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
CONFIG = ROOT / "slimmemeterportal_import/config.yaml"
DOCKERFILE = ROOT / "slimmemeterportal_import/Dockerfile"
BOOTSTRAP = ROOT / "tools/bootstrap_release_watcher_container.sh"
INSTALLER = ROOT / "tools/release_installer.sh"


def test_v3210_release_identity_and_runtime_dependency():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.36"
    config = CONFIG.read_text(encoding="utf-8")
    main = MAIN.read_text(encoding="utf-8")
    docker = DOCKERFILE.read_text(encoding="utf-8")
    assert 'version: "32.3.36"' in config
    assert 'APP_VERSION = "32.3.36"' in main
    assert 'xlsxwriter>=3.2,<4' in docker.lower()
    assert 'for name in ("reportlab", "pypdf")' in main
    assert 'for name in ("xlsxwriter",)' in main


def test_v3210_excel_sidecar_runs_only_after_success_and_cannot_fail_workflow():
    source = MAIN.read_text(encoding="utf-8")
    start = source.index("def run_full_month_workflow")
    end = source.index("def scheduler", start)
    workflow = source[start:end]
    assert '"Historische Energie-Excel bijwerken"' not in workflow
    backup = workflow.index("backup_result = create_project_backup(month_key, trigger=trigger)")
    excel_sidecar = workflow.index("energy_history_excel_result = run_historical_energy_excel_sidecar(")
    notify = workflow.index("if options.workflow_notify_home_assistant:", excel_sidecar)
    assert backup < excel_sidecar < notify
    sidecar_start = source.index("def run_historical_energy_excel_sidecar")
    sidecar_end = source.index("def create_project_backup", sidecar_start)
    sidecar = source[sidecar_start:sidecar_end]
    assert "try:" in sidecar
    assert "except Exception as exc:" in sidecar
    assert '"status": "error"' in sidecar
    assert '"previous_master_preserved": True' in sidecar


def test_v3210_preserves_month_and_release_safety():
    source = MAIN.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    installer = INSTALLER.read_text(encoding="utf-8")
    assert "automatic_month_close_enabled: false" in config
    assert "finalize_month(" not in (ROOT / "slimmemeterportal_import/rootfs/app/historical_energy_excel.py").read_text(encoding="utf-8")
    assert '-e ENERGIE_BACKUP_RETENTION=999' in bootstrap
    assert '-e ENERGIE_PROCESSED_RETENTION=999' in bootstrap
    assert '"reason":"validated_qnap_release_ready_for_github"' in installer
    assert "git push --force" not in source
    assert "git push -f" not in source
