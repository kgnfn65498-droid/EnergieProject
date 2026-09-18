import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def _root(tmp_path: Path) -> Path:
    for name in ("App", "Backups", "Inbox", "Data", "Infra", "CLEARUP"):
        (tmp_path / name).mkdir()
    return tmp_path


def _rollback(root: Path, version: str) -> Path:
    path = root / f"App.__rollback_{version}"
    path.mkdir()
    (path / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    return path


def test_root_cleanup_keeps_three_rollbacks_and_quarantines_only_excess(tmp_path):
    from project_clearup import _collect_candidates

    root = _root(tmp_path)
    for version in ("32.4.51", "32.4.52", "32.4.53", "32.4.54"):
        _rollback(root, version)

    items = _collect_candidates(root, keep_rollbacks=3)
    rows = {row["source_path"]: row for row in items}

    assert "App.__rollback_32.4.51" in rows
    assert rows["App.__rollback_32.4.51"]["category"] == "release_rollback"
    assert "App.__rollback_32.4.52" not in rows
    assert "App.__rollback_32.4.53" not in rows
    assert "App.__rollback_32.4.54" not in rows


def test_known_root_release_and_build_debris_become_reversible_clearup_candidates(tmp_path):
    from project_clearup import _collect_candidates

    root = _root(tmp_path)
    release_zip = root / "EnergieProject_v32.4.40.zip"
    release_zip.write_bytes(b"old release")
    temp_dir = root / "tmp_release_probe"
    temp_dir.mkdir()
    candidate_dir = root / "candidate_32455"
    candidate_dir.mkdir()
    failed = root / "App.__failed_32.4.50"
    failed.mkdir()

    rows = {row["source_path"]: row for row in _collect_candidates(root, keep_rollbacks=3)}

    assert rows[release_zip.name]["reason"] == "root_release_zip_leftover"
    assert rows[release_zip.name]["category"] == "root_release_debt"
    assert rows[temp_dir.name]["category"] == "root_development_debt"
    assert rows[candidate_dir.name]["category"] == "root_development_debt"
    assert rows[failed.name]["category"] == "failed_release"


def test_unknown_root_material_is_health_debt_but_not_auto_clearup_candidate(tmp_path):
    from project_clearup import _collect_candidates
    from project_hygiene import project_hygiene_check

    root = _root(tmp_path)
    unknown = root / "important-unclassified.txt"
    unknown.write_text("do not move without classification", encoding="utf-8")

    candidates = {row["source_path"] for row in _collect_candidates(root, keep_rollbacks=3)}
    assert unknown.name not in candidates

    check = project_hygiene_check(root)
    assert check["status"] == "ORANGE"
    assert check["details"]["root_unclassified_item_count"] == 1
    assert check["details"]["root_unclassified_items"] == [unknown.name]


def test_known_root_debris_is_reported_separately_from_unclassified_material(tmp_path):
    from project_hygiene import project_hygiene_check

    root = _root(tmp_path)
    (root / "EnergieProject_v32.4.41.zip").write_bytes(b"release")
    (root / "tmp_builder").mkdir()
    (root / "mystery.bin").write_bytes(b"?")

    check = project_hygiene_check(root)
    details = check["details"]

    assert details["root_known_debt_count"] == 2
    assert details["root_known_debt"] == [
        "EnergieProject_v32.4.41.zip",
        "tmp_builder",
    ]
    assert details["root_unclassified_item_count"] == 1
    assert details["root_unclassified_items"] == ["mystery.bin"]


def test_canonical_root_names_are_not_hygiene_debt(tmp_path):
    from project_hygiene import project_hygiene_check

    root = _root(tmp_path)
    check = project_hygiene_check(root)
    details = check["details"]

    assert details["root_known_debt_count"] == 0
    assert details["root_unclassified_item_count"] == 0
