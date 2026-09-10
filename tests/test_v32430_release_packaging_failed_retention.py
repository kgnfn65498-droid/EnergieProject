from __future__ import annotations

import importlib.util
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
TOOLS = ROOT / "tools"
BUILDER = TOOLS / "release_artifact_builder.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _minimal_release_source(root: Path) -> None:
    files = {
        "README.md": "ok\n",
        "INSTALL.md": "ok\n",
        "CHANGELOG.md": "ok\n",
        "repository.yaml": "name: energie\n",
        "VERSIE.txt": "32.4.30\n",
        "slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt": "2.0.0-rc22\n",
        "payload.py": "VALUE = 1\n",
    }
    for rel, text in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def test_32430_canonical_release_builder_exists_and_filters_test_cache(tmp_path: Path):
    assert BUILDER.is_file(), "canonieke releasebuilder ontbreekt; packaging gate kan worden overgeslagen"
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    builder = _load(BUILDER, "release_artifact_builder_32430")

    source = tmp_path / "source"
    source.mkdir()
    _minimal_release_source(source)
    (source / ".pytest_cache/v/cache").mkdir(parents=True)
    (source / ".pytest_cache/.gitignore").write_text("# cache\n", encoding="utf-8")
    (source / ".pytest_cache/v/cache/nodeids").write_text("[]\n", encoding="utf-8")
    (source / "tests/__pycache__").mkdir(parents=True)
    (source / "tests/__pycache__/x.cpython-313.pyc").write_bytes(b"cache")
    (source / ".DS_Store").write_bytes(b"junk")

    output = tmp_path / "EnergieProject_v32.4.30.zip"
    result = builder.build_release_artifact(source, output)

    assert result["status"] == "GREEN"
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        assert archive.testzip() is None
        assert ".pytest_cache/.gitignore" not in names
        assert not any("__pycache__" in Path(name).parts for name in names)
        assert not any(name.endswith((".pyc", ".pyo", ".DS_Store")) for name in names)
        manifest = archive.read("MANIFEST.sha256").decode("utf-8")
        sums = json.loads(archive.read("SHA256SUMS.json"))

    assert "payload.py" in manifest
    assert any(item["path"] == "payload.py" for item in sums["files"])
    assert result["filtered_count"] >= 4


def test_32430_project_hygiene_counts_failed_inbox_release_without_mutation(tmp_path: Path):
    hygiene = _load(APP / "project_hygiene.py", "project_hygiene_32430")
    (tmp_path / "Inbox/failed").mkdir(parents=True)
    failed = tmp_path / "Inbox/failed/EnergieProject_v32.4.10.zip"
    failed.write_bytes(b"old failed release")

    before = failed.read_bytes()
    check = hygiene.project_hygiene_check(tmp_path, keep_rollbacks=3)

    assert check["status"] == "ORANGE"
    assert check["details"]["failed_release_count"] == 1
    assert failed.read_bytes() == before


def test_32430_clearup_quarantines_settled_failed_release_reversibly(tmp_path: Path):
    clearup = _load(APP / "project_clearup.py", "project_clearup_failed_32430")
    (tmp_path / "App").mkdir(parents=True)
    (tmp_path / "App/VERSIE.txt").write_text("32.4.30\n", encoding="utf-8")
    (tmp_path / "Infra").mkdir(parents=True)
    (tmp_path / "Inbox/failed").mkdir(parents=True)
    (tmp_path / "Data/03_Systeem/Projectmanager/Roadmap").mkdir(parents=True)
    (tmp_path / "Data/03_Systeem/Projectmanager/Policies").mkdir(parents=True)
    (tmp_path / "Data/03_Systeem/Projectmanager/State").mkdir(parents=True)
    failed = tmp_path / "Inbox/failed/EnergieProject_v32.4.10.zip"
    failed.write_bytes(b"old failed release")

    plan = clearup.build_clearup_plan(tmp_path, current_version="32.4.30", keep_rollbacks=3)
    item = next(item for item in plan["items"] if item["source_path"] == "Inbox/failed/EnergieProject_v32.4.10.zip")
    assert item["category"] == "failed_release"
    assert item["disposition"] == "CLEARUP"

    result = clearup.apply_clearup_plan(
        tmp_path,
        plan,
        confirmation=plan["confirmation_required"],
        run_id="failed-retention-test",
    )
    assert result["status"] == "completed"
    assert not failed.exists()
    moved = tmp_path / "CLEARUP/failed-retention-test/original/Inbox/failed/EnergieProject_v32.4.10.zip"
    assert moved.read_bytes() == b"old failed release"
