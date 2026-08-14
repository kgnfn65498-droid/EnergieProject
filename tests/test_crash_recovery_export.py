import importlib.util
import pathlib
import sys
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
MODULE = APP_ROOT / "crash_recovery_export.py"


def load_export_module(name: str = "crash_recovery_export_test"):
    assert MODULE.exists(), "crash_recovery_export.py ontbreekt"
    spec = importlib.util.spec_from_file_location(name, MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_include_rule_only_excludes_explicit_backup_archives_and_ds_store():
    m = load_export_module("crash_export_include_rule")

    included = [
        pathlib.Path("Backups/EnergieProject_maandbackup_2026_07.zip"),
        pathlib.Path("Backups/Manifests/Energie_Complete_Backup_old_manifest.json"),
        pathlib.Path("Backups/NAS_DISASTER_RECOVERY_v32.md"),
        pathlib.Path("Backups/release_repair/history.json"),
        pathlib.Path("Backups/storage/state.json"),
        pathlib.Path("Backups/logs/backup.log"),
        pathlib.Path("Data/02_Output/2026_07/rapport.pdf"),
        pathlib.Path("Inbox/processed/EnergieProject_v32.0.28.zip"),
        pathlib.Path("Infra/docker-compose.yml"),
    ]
    excluded = [
        pathlib.Path("Backups/Energie_Complete_Backup_2026_08_x.zip"),
        pathlib.Path("Backups/old/Energie_Complete_Backup_2025_12_x.zip"),
        pathlib.Path("Backups/FULL_RECOVERY_v32.tar.gz"),
        pathlib.Path("Backups/old/FULL_RECOVERY_2026.tar.gz"),
        pathlib.Path("App/.DS_Store"),
        pathlib.Path("Data/sub/.DS_Store"),
    ]

    assert all(m.should_include_project_file(path) for path in included)
    assert all(not m.should_include_project_file(path) for path in excluded)


def _write(path: pathlib.Path, data: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def test_build_export_contains_whole_project_except_explicit_exclusions(tmp_path):
    m = load_export_module("crash_export_build")
    project = tmp_path / "EnergieProject"
    for root_name in ("App", "Data", "Backups", "Inbox", "Infra"):
        (project / root_name).mkdir(parents=True, exist_ok=True)

    _write(project / "App" / "main.py", b"print('ok')\n")
    _write(project / "Data" / "02_Output" / "2026_07" / "rapport.pdf", b"PDF")
    _write(project / "Backups" / "EnergieProject_maandbackup_2026_07.zip", b"MONTH")
    _write(project / "Backups" / "Manifests" / "current.json", b"{}")
    _write(project / "Backups" / "NAS_DISASTER_RECOVERY_v32.md", b"DR")
    _write(project / "Backups" / "release_repair" / "history.json", b"{}")
    _write(project / "Backups" / "storage" / "state.json", b"{}")
    _write(project / "Backups" / "logs" / "backup.log", b"log")
    _write(project / "Inbox" / "processed" / "EnergieProject_v32.0.28.zip", b"REL")
    _write(project / "Infra" / "docker-compose.yml", b"services: {}\n")

    _write(project / "Backups" / "Energie_Complete_Backup_2026_08_test.zip", b"OLD")
    _write(project / "Backups" / "FULL_RECOVERY_v32.tar.gz", b"OLD")
    _write(project / "Backups" / "old" / "FULL_RECOVERY_2026.tar.gz", b"OLD")
    _write(project / "App" / ".DS_Store", b"MAC")

    output = tmp_path / "export" / "EnergieProject_Complete_Crash_Recovery_test.zip"
    result = m.build_recovery_export(project, output)
    verified = m.verify_recovery_export(output)

    assert result.zip_path == output
    assert result.file_count == 10
    assert result.total_bytes > 0
    assert len(result.sha256) == 64
    assert verified.valid is True
    assert verified.file_count == result.file_count
    assert verified.sha256 == result.sha256
    assert verified.top_level_ok is True
    assert verified.required_roots_ok is True
    assert verified.excluded_hits == ()

    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())

    required = {
        "EnergieProject/App/main.py",
        "EnergieProject/Data/02_Output/2026_07/rapport.pdf",
        "EnergieProject/Backups/EnergieProject_maandbackup_2026_07.zip",
        "EnergieProject/Backups/Manifests/current.json",
        "EnergieProject/Backups/NAS_DISASTER_RECOVERY_v32.md",
        "EnergieProject/Backups/release_repair/history.json",
        "EnergieProject/Backups/storage/state.json",
        "EnergieProject/Backups/logs/backup.log",
        "EnergieProject/Inbox/processed/EnergieProject_v32.0.28.zip",
        "EnergieProject/Infra/docker-compose.yml",
    }
    assert required.issubset(names)
    assert all(name.startswith("EnergieProject/") for name in names)
    assert not any("Energie_Complete_Backup_" in name and name.endswith(".zip") for name in names)
    assert not any(pathlib.PurePosixPath(name).name.startswith("FULL_RECOVERY") and name.endswith(".tar.gz") for name in names)
    assert not any(pathlib.PurePosixPath(name).name == ".DS_Store" for name in names)


def test_build_export_requires_all_five_project_roots(tmp_path):
    m = load_export_module("crash_export_required_roots")
    project = tmp_path / "EnergieProject"
    (project / "App").mkdir(parents=True)

    output = tmp_path / "export.zip"
    try:
        m.build_recovery_export(project, output)
    except RuntimeError as exc:
        assert "hoofdmappen" in str(exc).lower()
    else:
        raise AssertionError("onvolledige EnergieProject-root werd ten onrechte geaccepteerd")


def test_verify_rejects_member_outside_energieproject(tmp_path):
    m = load_export_module("crash_export_verify_top")
    output = tmp_path / "bad.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("EnergieProject/App/main.py", "ok")
        archive.writestr("EnergieProject/Data/a.txt", "ok")
        archive.writestr("EnergieProject/Backups/a.txt", "ok")
        archive.writestr("EnergieProject/Inbox/a.txt", "ok")
        archive.writestr("EnergieProject/Infra/a.txt", "ok")
        archive.writestr("los_bestand.txt", "fout")

    verified = m.verify_recovery_export(output)
    assert verified.valid is False
    assert verified.top_level_ok is False


def test_sha256_file_is_stable(tmp_path):
    m = load_export_module("crash_export_sha")
    path = tmp_path / "x.bin"
    path.write_bytes(b"abc")
    assert m.sha256_file(path) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
