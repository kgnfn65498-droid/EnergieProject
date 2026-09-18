import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def test_release_builder_excludes_top_level_fulltest_evidence(tmp_path):
    from release_artifact_builder import build_release_artifact

    source = tmp_path / "src"
    source.mkdir()
    (source / "README.md").write_text("readme\n", encoding="utf-8")
    (source / "INSTALL.md").write_text("install\n", encoding="utf-8")
    (source / "CHANGELOG.md").write_text("change\n", encoding="utf-8")
    (source / "repository.yaml").write_text("name: test\n", encoding="utf-8")
    (source / "VERSIE.txt").write_text("32.4.56\n", encoding="utf-8")
    pm = source / "slimmemeterportal_import/rootfs/app/projectmanager_v2"
    pm.mkdir(parents=True)
    (pm / "VERSION.txt").write_text("2.0.0-rc43\n", encoding="utf-8")
    (source / "fulltest.log").write_text("local build path /mnt/data/example\n", encoding="utf-8")
    (source / "fulltest.exit").write_text("0\n", encoding="utf-8")

    output = tmp_path / "release.zip"
    result = build_release_artifact(source, output)
    assert result["status"] == "GREEN"
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
    assert "fulltest.log" not in names
    assert "fulltest.exit" not in names
