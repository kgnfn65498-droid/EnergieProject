from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"

import sys
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import historical_energy_excel as hx  # noqa: E402

MAIN = APP / "main.py"
CONFIG = ROOT / "slimmemeterportal_import" / "config.yaml"


def test_latest_complete_bootstrap_month_comes_from_validated_history(tmp_path: Path):
    assert hx.latest_complete_month_key(tmp_path) == "2026_07"


def test_startup_bootstrap_creates_master_and_latest_full_archive_without_month_workflow(tmp_path: Path):
    result = hx.bootstrap_historical_energy_workbook(tmp_path)
    assert result["status"] == "completed"
    assert result["month"] == "2026_07"
    master = tmp_path / "Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie.xlsx"
    archive = tmp_path / "Data/02_Output/Rapportages/Verbruikshistorie/Archief/Energie_verbruik_historie_2026_07.xlsx"
    assert master.is_file()
    assert archive.is_file()
    assert hx.validate_xlsx(master)["status"] == "ok"
    assert master.read_bytes() == archive.read_bytes()


def test_startup_bootstrap_is_idempotent_when_master_and_archive_are_already_valid(tmp_path: Path):
    first = hx.bootstrap_historical_energy_workbook(tmp_path)
    master = tmp_path / "Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie.xlsx"
    before = hashlib.sha256(master.read_bytes()).hexdigest()
    second = hx.bootstrap_historical_energy_workbook(tmp_path)
    after = hashlib.sha256(master.read_bytes()).hexdigest()
    assert first["status"] == "completed"
    assert second["status"] == "skipped_existing"
    assert before == after


def test_v3211_main_starts_excel_bootstrap_independently_of_month_workflow():
    source = MAIN.read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.3.34"' in source
    assert "bootstrap_historical_energy_workbook" in source
    assert "def startup_historical_energy_excel" in source
    main_start = source.index("def main()")
    startup = source.index("def startup_historical_energy_excel", main_start)
    thread = source.index("target=startup_historical_energy_excel", startup)
    scheduler = source.index("target=scheduler", main_start)
    assert startup < thread
    assert scheduler < thread or thread < scheduler  # independent daemon threads; no workflow dependency
    workflow_start = source.index("def run_full_month_workflow")
    workflow_end = source.index("def scheduler", workflow_start)
    workflow = source[workflow_start:workflow_end]
    assert "startup_historical_energy_excel" not in workflow


def test_v3211_safety_contract_is_unchanged():
    source = MAIN.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    assert 'version: "32.3.34"' in config
    assert "automatic_month_close_enabled: false" in config
    assert "finalize_month(" not in (APP / "historical_energy_excel.py").read_text(encoding="utf-8")
