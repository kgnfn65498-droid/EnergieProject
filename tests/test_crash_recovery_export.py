import importlib.util
import pathlib
import sys
import zipfile

import pytest

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


def _make_project(tmp_path: pathlib.Path) -> pathlib.Path:
    project = tmp_path / "EnergieProject"
    for root_name in ("App", "Data", "Backups", "Inbox", "Infra"):
        (project / root_name).mkdir(parents=True, exist_ok=True)
    return project


def test_build_export_contains_whole_project_except_explicit_exclusions(tmp_path):
    m = load_export_module("crash_export_build")
    project = _make_project(tmp_path)

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


def _mutate_after_member_is_written(monkeypatch, live_path: pathlib.Path, member_name: str, new_bytes: bytes) -> None:
    original_write = zipfile.ZipFile.write
    original_writestr = zipfile.ZipFile.writestr
    changed = {"done": False}

    def maybe_mutate(name: str) -> None:
        if not changed["done"] and name == member_name:
            live_path.write_bytes(new_bytes)
            changed["done"] = True

    def wrapped_write(self, filename, arcname=None, *args, **kwargs):
        result = original_write(self, filename, arcname, *args, **kwargs)
        maybe_mutate(str(arcname or filename).replace("\\", "/"))
        return result

    def wrapped_writestr(self, zinfo_or_arcname, data, *args, **kwargs):
        result = original_writestr(self, zinfo_or_arcname, data, *args, **kwargs)
        name = getattr(zinfo_or_arcname, "filename", zinfo_or_arcname)
        maybe_mutate(str(name).replace("\\", "/"))
        return result

    monkeypatch.setattr(zipfile.ZipFile, "write", wrapped_write)
    monkeypatch.setattr(zipfile.ZipFile, "writestr", wrapped_writestr)


def test_build_export_snapshots_scheduler_heartbeat_while_live_file_keeps_changing(tmp_path, monkeypatch):
    m = load_export_module("crash_export_heartbeat_snapshot")
    project = _make_project(tmp_path)
    heartbeat = project / "Data" / "01_Input" / "_scheduler" / "quarter_hour_heartbeat.json"
    original = b'{"heartbeat":"before"}\n'
    updated = b'{"heartbeat":"after"}\n'
    _write(heartbeat, original)
    _write(project / "App" / "main.py", b"ok\n")

    _mutate_after_member_is_written(
        monkeypatch,
        heartbeat,
        "EnergieProject/Data/01_Input/_scheduler/quarter_hour_heartbeat.json",
        updated,
    )

    output = tmp_path / "heartbeat-export.zip"
    result = m.build_recovery_export(project, output)

    assert result.file_count == 2
    assert heartbeat.read_bytes() == updated
    with zipfile.ZipFile(output) as archive:
        assert archive.read(
            "EnergieProject/Data/01_Input/_scheduler/quarter_hour_heartbeat.json"
        ) == original


def test_build_export_still_rejects_other_project_file_changes(tmp_path, monkeypatch):
    m = load_export_module("crash_export_other_mutation")
    project = _make_project(tmp_path)
    live = project / "Data" / "live.json"
    _write(live, b'{"value":1}\n')
    _write(project / "App" / "main.py", b"ok\n")

    _mutate_after_member_is_written(
        monkeypatch,
        live,
        "EnergieProject/Data/live.json",
        b'{"value":2}\n',
    )

    output = tmp_path / "other-change-export.zip"
    with pytest.raises(RuntimeError, match="Projectinhoud wijzigde"):
        m.build_recovery_export(project, output)
    assert not output.exists()
