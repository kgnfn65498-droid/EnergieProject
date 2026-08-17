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
    assert 'APP_VERSION = "32.3.15"' in source
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
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.15"
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'version: "32.3.15"' in config

@pytest.mark.skipif(not STRUCTURE.is_file(), reason="RED gate")
def test_v3221_existing_readonly_knowledge_base_is_rehomed_without_data_loss(tmp_path: Path, monkeypatch):
    spec = importlib.util.spec_from_file_location("project_structure_v3221_readonly_kb", STRUCTURE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    reports = tmp_path / "Data/02_Output/Rapportages"
    kb = reports / "KnowledgeBase"
    kb.mkdir(parents=True)
    (kb / "00_START_HIER.md").write_text("# start\n", encoding="utf-8")
    (reports / "EnergieProject_Roadmap.md").write_text("# roadmap\n", encoding="utf-8")
    (reports / "Apparatuur_index.md").write_text("# apparatuur\n", encoding="utf-8")
    (reports / "Mobiele_socket_meetlog.md").write_text("# socket\n", encoding="utf-8")

    real_probe = module._directory_accepts_atomic_write
    original_kb = kb.resolve()

    def fake_probe(path: Path) -> bool:
        # Simuleer exact de QNAP-runtime: de reeds bestaande KB-map is niet
        # schrijfbaar voor HA; een nieuw door HA aangemaakte KB-map wel.
        if path.resolve() == original_kb and not (reports / ".KnowledgeBase_v32.2_rehome").exists():
            return False
        return real_probe(path)

    monkeypatch.setattr(module, "_directory_accepts_atomic_write", fake_probe)
    result = module.migrate_project_structure(tmp_path)

    assert result["status"] == "completed"
    assert result["knowledge_base_rehomed"] is True
    assert (kb / "00_START_HIER.md").read_text(encoding="utf-8").startswith("# start")
    assert (kb / "EnergieProject_Roadmap.md").is_file()
    assert (kb / "Apparatuur_index.md").is_file()
    assert (kb / "Mobiele_socket_meetlog.md").is_file()
    assert not (reports / ".KnowledgeBase_v32.2_rehome").exists()

@pytest.mark.skipif(not STRUCTURE.is_file(), reason="RED gate")
def test_v3221_recovers_exact_partial_v3220_runtime_state(tmp_path: Path, monkeypatch):
    spec = importlib.util.spec_from_file_location("project_structure_v3221_partial", STRUCTURE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    reports = tmp_path / "Data/02_Output/Rapportages"
    kb = reports / "KnowledgeBase"
    history = reports / "Verbruikshistorie"
    old_archive = reports / "Archief"
    kb.mkdir(parents=True)
    history.mkdir(parents=True)
    old_archive.mkdir(parents=True)

    # Exacte live toestand na de mislukte 32.2.0-startup: history-bestanden zijn
    # al verhuisd, KnowledgeBase-doelen en juli-archief nog niet.
    (history / "Energie_verbruik_historie.xlsx").write_bytes(b"master-live")
    (history / "Energie_verbruik_historie_bootstrap_status.json").write_text('{"status":"error"}\n', encoding="utf-8")
    (history / "Historische_data_index.md").write_text("# history\n", encoding="utf-8")
    (history / "Energie_verbruik_historie_design.md").write_text("# design\n", encoding="utf-8")
    (old_archive / "Energie_verbruik_historie_2026_07.xlsx").write_bytes(b"july-archive")
    (reports / "EnergieProject_Roadmap.md").write_text("# roadmap\nData/02_Output/Rapportages/Energie_verbruik_historie.xlsx\n", encoding="utf-8")
    (reports / "Apparatuur_index.md").write_text("# apparatuur\n", encoding="utf-8")
    (reports / "Mobiele_socket_meetlog.md").write_text("# socket\n", encoding="utf-8")
    (kb / "00_START_HIER.md").write_text("# start\nData/02_Output/Rapportages/EnergieProject_Roadmap.md\n", encoding="utf-8")

    # Een bestaande, geldige pre-migratiebackup zoals live aanwezig.
    backup_root = tmp_path / module.STRUCTURE_BACKUP_RELATIVE
    backup_root.mkdir(parents=True)
    backup_copy = backup_root / "Data/02_Output/Rapportages/KnowledgeBase/00_START_HIER.md"
    backup_copy.parent.mkdir(parents=True)
    backup_copy.write_text("# start\nData/02_Output/Rapportages/EnergieProject_Roadmap.md\n", encoding="utf-8")
    manifest = {
        "version": "32.2.0",
        "files": [{
            "path": "Data/02_Output/Rapportages/KnowledgeBase/00_START_HIER.md",
            "sha256": hashlib.sha256(backup_copy.read_bytes()).hexdigest(),
            "size": backup_copy.stat().st_size,
        }],
    }
    (backup_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    real_probe = module._directory_accepts_atomic_write
    original_kb = kb.resolve()
    def fake_probe(path: Path) -> bool:
        if path.resolve() == original_kb and not (reports / ".KnowledgeBase_v32.2_rehome").exists():
            return False
        return real_probe(path)
    monkeypatch.setattr(module, "_directory_accepts_atomic_write", fake_probe)

    result = module.migrate_project_structure(tmp_path)
    assert result["status"] == "completed"
    assert result["knowledge_base_rehomed"] is True
    assert (history / "Energie_verbruik_historie.xlsx").read_bytes() == b"master-live"
    assert (history / "Archief/Energie_verbruik_historie_2026_07.xlsx").read_bytes() == b"july-archive"
    assert (kb / "EnergieProject_Roadmap.md").is_file()
    assert (kb / "Apparatuur_index.md").is_file()
    assert (kb / "Mobiele_socket_meetlog.md").is_file()
    assert not (reports / "EnergieProject_Roadmap.md").exists()
    assert not (reports / "Apparatuur_index.md").exists()
    assert not (reports / "Mobiele_socket_meetlog.md").exists()
    assert not (old_archive / "Energie_verbruik_historie_2026_07.xlsx").exists()
    assert (tmp_path / module.STRUCTURE_STATUS_RELATIVE).is_file()

    second = module.migrate_project_structure(tmp_path)
    assert second["status"] == "completed"
    assert second["idempotent"] is True


def test_v3222_cleanup_permission_error_after_completed_migration_is_nonfatal(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('project_structure_v3222_cleanup', STRUCTURE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    reports = tmp_path / module.REPORTS_RELATIVE
    kb = tmp_path / module.KNOWLEDGE_BASE_RELATIVE
    reports.mkdir(parents=True, exist_ok=True)
    kb.mkdir(parents=True, exist_ok=True)
    (kb / 'README.md').write_text('# kb\n', encoding='utf-8')
    (reports / 'EnergieProject_Roadmap.md').write_text('# roadmap\n', encoding='utf-8')
    (reports / 'Apparatuur_index.md').write_text('# apparatuur\n', encoding='utf-8')
    (reports / 'Mobiele_socket_meetlog.md').write_text('# socket\n', encoding='utf-8')

    real_rmtree = module.shutil.rmtree
    def blocked_rmtree(path, *args, **kwargs):
        if Path(path).name == '.KnowledgeBase_v32.2_rehome':
            raise PermissionError(13, 'Permission denied', str(path))
        return real_rmtree(path, *args, **kwargs)

    calls = {'kb': 0}
    def writable_probe(directory):
        if directory.name == 'KnowledgeBase':
            calls['kb'] += 1
            return calls['kb'] > 1
        return True
    monkeypatch.setattr(module, '_directory_accepts_atomic_write', writable_probe)
    monkeypatch.setattr(module.shutil, 'rmtree', blocked_rmtree)

    result = module.migrate_project_structure(tmp_path)
    assert result['status'] == 'completed'
    assert result.get('cleanup_deferred') is True
    assert (tmp_path / module.STRUCTURE_STATUS_RELATIVE).is_file()


def test_v3222_completed_prior_migration_ignores_unreadable_stale_rehome(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('project_structure_v3222_stale', STRUCTURE)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    for rel in (
        module.ROADMAP_RELATIVE,
        module.APPARATUUR_INDEX_RELATIVE,
        module.MOBILE_SOCKET_LOG_RELATIVE,
        module.HISTORY_MASTER_RELATIVE,
        module.HISTORICAL_DATA_INDEX_RELATIVE,
        module.HISTORICAL_DESIGN_RELATIVE,
        module.HISTORICAL_BOOTSTRAP_STATUS_RELATIVE,
    ):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'canonical\n')

    status = tmp_path / module.STRUCTURE_STATUS_RELATIVE
    status.write_text(json.dumps({'status':'completed','version':'32.2.1','canonical':{}}), encoding='utf-8')
    rehome = tmp_path / module.KNOWLEDGE_BASE_REHOME_RELATIVE
    rehome.mkdir(parents=True)
    (rehome / 'old.md').write_text('old\n', encoding='utf-8')

    real_tree_hashes = module._tree_file_hashes
    def guarded_tree_hashes(root):
        if Path(root) == rehome:
            raise AssertionError('stale rehome must not be traversed after completed migration')
        return real_tree_hashes(root)
    monkeypatch.setattr(module, '_tree_file_hashes', guarded_tree_hashes)

    result = module.migrate_project_structure(tmp_path)
    assert result['status'] == 'completed'
    assert result['version'] == '32.2.2'
    assert result['idempotent'] is True
    assert result['cleanup_deferred'] is True
    saved = json.loads(status.read_text(encoding='utf-8'))
    assert saved['version'] == '32.2.2'
    assert saved['cleanup_deferred'] is True
