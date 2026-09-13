from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"


def load_clearup():
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    spec = importlib.util.spec_from_file_location("project_clearup_32431_unreadable", APP / "project_clearup.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def minimal_root(root: Path) -> tuple[Path, Path]:
    (root / "App").mkdir(parents=True)
    (root / "App/VERSIE.txt").write_text("32.4.32\n", encoding="utf-8")
    (root / "Infra").mkdir()
    for rel in (
        "Data/03_Systeem/Projectmanager/Roadmap",
        "Data/03_Systeem/Projectmanager/Policies",
        "Data/03_Systeem/Projectmanager/State",
        "Inbox/failed",
        "Backups/RestoreStaging",
    ):
        (root / rel).mkdir(parents=True, exist_ok=True)

    unreadable_dir = root / "Backups/RestoreStaging/old-restore-drill"
    unreadable_dir.mkdir()
    unreadable_file = unreadable_dir / "nested/VERIFY.txt"
    unreadable_file.parent.mkdir()
    unreadable_file.write_text("restore evidence\n", encoding="utf-8")

    readable_failed = root / "Inbox/failed/EnergieProject_v32.4.10.zip"
    readable_failed.write_bytes(b"old failed release")
    return unreadable_file, readable_failed


def deny_binary_read(monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    real_open = Path.open
    target_resolved = target.resolve()

    def guarded_open(self: Path, *args, **kwargs):
        mode = args[0] if args else kwargs.get("mode", "r")
        if self.resolve() == target_resolved and "b" in str(mode) and "r" in str(mode):
            raise PermissionError(13, "Permission denied", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guarded_open)


def test_unreadable_candidate_becomes_review_without_aborting_plan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clearup = load_clearup()
    unreadable_file, readable_failed = minimal_root(tmp_path)
    deny_binary_read(monkeypatch, unreadable_file)

    plan = clearup.build_clearup_plan(tmp_path, current_version="32.4.32", keep_rollbacks=3)

    unreadable = next(item for item in plan["items"] if item["source_path"] == "Backups/RestoreStaging/old-restore-drill")
    readable = next(item for item in plan["items"] if item["source_path"] == "Inbox/failed/EnergieProject_v32.4.10.zip")

    assert unreadable["disposition"] == "REVIEW"
    assert unreadable["tree_sha256"] is None
    assert unreadable["candidate_read_error"]["type"] == "PermissionError"
    assert "Permission denied" in unreadable["candidate_read_error"]["message"]
    assert readable["disposition"] == "CLEARUP"
    assert readable["tree_sha256"]
    assert readable_failed.exists()


def test_apply_leaves_unreadable_review_in_place_and_moves_other_candidate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    clearup = load_clearup()
    unreadable_file, readable_failed = minimal_root(tmp_path)
    deny_binary_read(monkeypatch, unreadable_file)

    plan = clearup.build_clearup_plan(tmp_path, current_version="32.4.32", keep_rollbacks=3)
    result = clearup.apply_clearup_plan(
        tmp_path,
        plan,
        confirmation=plan["confirmation_required"],
        run_id="unreadable-review-proof",
    )

    assert result["status"] == "completed"
    assert unreadable_file.exists()
    assert not readable_failed.exists()
    moved = tmp_path / "CLEARUP/unreadable-review-proof/original/Inbox/failed/EnergieProject_v32.4.10.zip"
    assert moved.read_bytes() == b"old failed release"


def test_32431_release_identity_and_cross_chat_platform_rule():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.4.49"
    assert 'version: "32.4.49"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    main = (APP / "main.py").read_text(encoding="utf-8")
    mode = (APP / "mode_entrypoint.py").read_text(encoding="utf-8")
    agreements = (ROOT / "PROJECT_AFSPRAKEN.md").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.4.49"' in main
    assert 'TARGET_RELEASE_VERSION = "32.4.49"' in mode
    assert 'PRODUCTION_CORE_REVISION = "9.4-core3"' in main
    assert "nieuwe chat" in agreements.lower()
    assert "python3" in agreements.lower()
    assert "container" in agreements.lower()
