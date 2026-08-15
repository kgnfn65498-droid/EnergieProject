from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
STRUCTURE = APP / "project_structure.py"
MAIN = APP / "main.py"
HISTORICAL = APP / "historical_energy_excel.py"
TESTINSTRUCTIES = ROOT / "TESTINSTRUCTIES.md"


def test_v3220_structure_module_exists_red_gate():
    assert STRUCTURE.is_file(), "v32.2 project_structure.py ontbreekt"


@pytest.mark.skipif(not STRUCTURE.is_file(), reason="RED gate: project_structure.py bestaat nog niet")
def test_v3220_canonical_paths_are_single_source_of_truth():
    spec = importlib.util.spec_from_file_location("project_structure_v3220", STRUCTURE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.KNOWLEDGE_BASE_RELATIVE == Path("Data/02_Output/Rapportages/KnowledgeBase")
    assert module.ROADMAP_RELATIVE == Path("Data/02_Output/Rapportages/KnowledgeBase/EnergieProject_Roadmap.md")
    assert module.HISTORY_RELATIVE == Path("Data/02_Output/Rapportages/Verbruikshistorie")
    assert module.HISTORY_MASTER_RELATIVE == Path("Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie.xlsx")
    assert module.HISTORY_ARCHIVE_RELATIVE == Path("Data/02_Output/Rapportages/Verbruikshistorie/Archief")


@pytest.mark.skipif(not STRUCTURE.is_file(), reason="RED gate")
def test_v3220_migration_preserves_bytes_and_is_idempotent(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("project_structure_v3220_idempotent", STRUCTURE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    reports = tmp_path / "Data/02_Output/Rapportages"
    kb = reports / "KnowledgeBase"
    archive = reports / "Archief"
    kb.mkdir(parents=True)
    archive.mkdir(parents=True)
    fixtures = {
        reports / "Energie_verbruik_historie.xlsx": b"master-v3213",
        archive / "Energie_verbruik_historie_2026_07.xlsx": b"archive-v3213",
        reports / "Energie_verbruik_historie_bootstrap_status.json": b'{"status":"skipped_existing"}\n',
        reports / "Historische_data_index.md": b"# history\n",
        reports / "Energie_verbruik_historie_design.md": b"# design\n",
        reports / "EnergieProject_Roadmap.md": b"# Roadmap\nData/02_Output/Rapportages/Energie_verbruik_historie.xlsx\n",
        reports / "Apparatuur_index.md": b"# apparatuur\n",
        reports / "Mobiele_socket_meetlog.md": b"# socket\n",
        kb / "00_START_HIER.md": b"# start\nData/02_Output/Rapportages/EnergieProject_Roadmap.md\n",
        reports / "API-v2-test.md": b"API cleanup is bewust buiten v32.2\n",
        archive / "onverwant_rapport.txt": b"blijft in legacy Archief\n",
    }
    for path, data in fixtures.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    hashes = {path: hashlib.sha256(data).hexdigest() for path, data in fixtures.items() if path.name.endswith(".xlsx")}

    first = module.migrate_project_structure(tmp_path)
    assert first["status"] == "completed"
    new_master = tmp_path / module.HISTORY_MASTER_RELATIVE
    new_archive = tmp_path / module.HISTORY_ARCHIVE_RELATIVE / "Energie_verbruik_historie_2026_07.xlsx"
    assert hashlib.sha256(new_master.read_bytes()).hexdigest() == hashes[reports / "Energie_verbruik_historie.xlsx"]
    assert hashlib.sha256(new_archive.read_bytes()).hexdigest() == hashes[archive / "Energie_verbruik_historie_2026_07.xlsx"]
    assert not (reports / "Energie_verbruik_historie.xlsx").exists()
    assert not (reports / "EnergieProject_Roadmap.md").exists()
    assert (kb / "EnergieProject_Roadmap.md").is_file()
    assert (kb / "Apparatuur_index.md").is_file()
    assert (kb / "Mobiele_socket_meetlog.md").is_file()
    assert (reports / "API-v2-test.md").read_bytes() == b"API cleanup is bewust buiten v32.2\n"
    assert (archive / "onverwant_rapport.txt").read_bytes() == b"blijft in legacy Archief\n"
    assert (tmp_path / module.STRUCTURE_BACKUP_RELATIVE / "manifest.json").is_file()

    second = module.migrate_project_structure(tmp_path)
    assert second["status"] == "completed"
    assert second["idempotent"] is True
    assert new_master.read_bytes() == b"master-v3213"
    assert new_archive.read_bytes() == b"archive-v3213"


@pytest.mark.skipif(not STRUCTURE.is_file(), reason="RED gate")
def test_v3220_conflict_is_fail_closed(tmp_path: Path):
    spec = importlib.util.spec_from_file_location("project_structure_v3220_conflict", STRUCTURE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    old = tmp_path / module.LEGACY_MASTER_RELATIVE
    new = tmp_path / module.HISTORY_MASTER_RELATIVE
    old.parent.mkdir(parents=True, exist_ok=True)
    new.parent.mkdir(parents=True, exist_ok=True)
    old.write_bytes(b"old-master")
    new.write_bytes(b"different-new-master")
    with pytest.raises(module.StructureMigrationConflict, match="verschillen"):
        module.migrate_project_structure(tmp_path)
    assert old.read_bytes() == b"old-master"
    assert new.read_bytes() == b"different-new-master"


@pytest.mark.skipif(not STRUCTURE.is_file(), reason="RED gate")
def test_v3220_main_migrates_before_bootstrap_and_sidecar():
    source = MAIN.read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.2.0"' in source
    assert "from project_structure import HISTORICAL_BOOTSTRAP_STATUS_RELATIVE, migrate_project_structure" in source
    start = source.index("def startup_historical_energy_excel")
    end = source.index("threading.Thread(\n        target=startup_historical_energy_excel", start)
    block = source[start:end]
    assert block.index("migrate_project_structure(live_nas_layout_root)") < block.index("bootstrap_historical_energy_workbook(live_nas_layout_root)")
    assert "HISTORICAL_BOOTSTRAP_STATUS_RELATIVE" in block
    sidecar_start = source.index("def run_historical_energy_excel_sidecar")
    sidecar_end = source.index("def create_project_backup", sidecar_start)
    sidecar = source[sidecar_start:sidecar_end]
    assert sidecar.index("migrate_project_structure(live_nas_layout_root)") < sidecar.index("publish_historical_energy_workbook(")


@pytest.mark.skipif(not STRUCTURE.is_file(), reason="RED gate")
def test_v3220_active_writers_have_no_legacy_write_paths():
    forbidden = (
        "Data/02_Output/Rapportages/Energie_verbruik_historie.xlsx",
        "Data/02_Output/Rapportages/Archief",
        "Data/02_Output/Rapportages/Energie_verbruik_historie_bootstrap_status.json",
    )
    for path in (MAIN, HISTORICAL, TESTINSTRUCTIES):
        text = path.read_text(encoding="utf-8")
        for old in forbidden:
            assert old not in text, f"legacy pad achtergebleven in {path.name}: {old}"


def test_v3220_release_identity():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.2.0"
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'version: "32.2.0"' in config
