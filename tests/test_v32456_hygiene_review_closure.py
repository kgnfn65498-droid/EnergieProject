import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))


def _root(tmp_path: Path, version: str = "32.4.56") -> Path:
    for name in ("App", "Backups", "Inbox", "Data", "Infra", "CLEARUP"):
        (tmp_path / name).mkdir(parents=True, exist_ok=True)
    (tmp_path / "App/VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    return tmp_path


def _rollback(root: Path, version: str) -> Path:
    path = root / f"App.__rollback_{version}"
    path.mkdir()
    (path / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    return path


def _seed_reviewed_debt(root: Path) -> list[str]:
    for version in ("32.4.51", "32.4.52", "32.4.53", "32.4.54"):
        _rollback(root, version)
    (root / "Backups/_release_prepare/old.zip").parent.mkdir(parents=True, exist_ok=True)
    (root / "Backups/_release_prepare/old.zip").write_bytes(b"old")
    (root / "Inbox/failed/failed.zip").parent.mkdir(parents=True, exist_ok=True)
    (root / "Inbox/failed/failed.zip").write_bytes(b"failed")
    (root / "Inbox/release_hold_tmp").mkdir(parents=True, exist_ok=True)
    (root / "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2/old-build").mkdir(parents=True, exist_ok=True)
    return [
        "App.__rollback_32.4.51",
        "Backups/_release_prepare/old.zip",
        "Inbox/failed/failed.zip",
        "Inbox/release_hold_tmp",
        "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2/old-build",
    ]


def _write_clearup_review(root: Path, paths: list[str], *, release: str = "32.4.56") -> None:
    manifest_rel = Path("CLEARUP/review-proof/manifest.json")
    manifest = {
        "schema": "energie_project_clearup_v1",
        "current_version": release,
        "plan_id": "review-plan-1",
        "review_items": [{"source_path": path, "disposition": "REVIEW"} for path in paths],
        "items": [],
        "delete_capability": False,
    }
    target = root / manifest_rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(manifest), encoding="utf-8")
    runtime = root / "Inbox/logs/project_clearup_runtime.json"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(json.dumps({
        "status": "completed",
        "release_version": release,
        "plan_id": "review-plan-1",
        "manifest": manifest_rel.as_posix(),
        "delete_performed": False,
    }), encoding="utf-8")


def test_current_release_clearup_review_can_close_exact_legacy_hygiene_debt(tmp_path):
    from project_hygiene import project_hygiene_check

    root = _root(tmp_path)
    paths = _seed_reviewed_debt(root)
    _write_clearup_review(root, paths)

    check = project_hygiene_check(root, keep_rollbacks=3)

    assert check["status"] == "GREEN"
    assert check["reason"] == "clean_reviewed_debt_preserved"
    assert check["details"]["reviewed_hygiene_debt_count"] == len(paths)
    assert check["details"]["unreviewed_hygiene_debt_count"] == 0
    assert check["details"]["clearup_review_evidence_current"] is True


def test_stale_clearup_review_never_masks_current_hygiene_debt(tmp_path):
    from project_hygiene import project_hygiene_check

    root = _root(tmp_path)
    paths = _seed_reviewed_debt(root)
    _write_clearup_review(root, paths, release="32.4.55")

    check = project_hygiene_check(root, keep_rollbacks=3)

    assert check["status"] == "ORANGE"
    assert check["details"]["clearup_review_evidence_current"] is False
    assert check["details"]["unreviewed_hygiene_debt_count"] == len(paths)


def test_new_unreviewed_debt_stays_orange_even_with_current_review_evidence(tmp_path):
    from project_hygiene import project_hygiene_check

    root = _root(tmp_path)
    paths = _seed_reviewed_debt(root)
    _write_clearup_review(root, paths)
    (root / "Backups/_release_prepare/new.zip").write_bytes(b"new")

    check = project_hygiene_check(root, keep_rollbacks=3)

    assert check["status"] == "ORANGE"
    assert check["details"]["reviewed_hygiene_debt_count"] == len(paths)
    assert check["details"]["unreviewed_hygiene_debt"] == ["Backups/_release_prepare/new.zip"]
