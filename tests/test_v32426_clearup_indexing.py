from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
MODULE = APP / "project_clearup.py"


def _load():
    spec = importlib.util.spec_from_file_location("project_clearup_v32426", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rollback(root: Path, version: str) -> None:
    path = root / f"App.__rollback_{version}"
    path.mkdir(parents=True)
    (path / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    (path / "payload.txt").write_text("payload-" + version, encoding="utf-8")


def _project(root: Path) -> Path:
    (root / "App/slimmemeterportal_import/rootfs/app").mkdir(parents=True)
    (root / "Infra").mkdir(parents=True)
    (root / "Inbox").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/Roadmap").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/Policies").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/State").mkdir(parents=True)
    (root / "Inbox/atomic_app_swap_state.json").write_text(
        json.dumps({"state": "ACCEPTED", "to_version": "32.4.26", "rollback_path": "App.__rollback_32.4.24"}),
        encoding="utf-8",
    )
    for version in ("32.4.19", "32.4.20", "32.4.21", "32.4.22", "32.4.23", "32.4.24"):
        _rollback(root, version)
    active = root / "Infra/active.conf"
    active.write_text("mode=production\n", encoding="utf-8")
    return active


def test_32426_dependency_text_is_read_once_for_many_candidates(tmp_path: Path, monkeypatch):
    mod = _load()
    active = _project(tmp_path)

    original = Path.read_text
    reads = {"active": 0}

    def counted(self: Path, *args, **kwargs):
        if self == active:
            reads["active"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counted)
    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.26", keep_rollbacks=3)

    assert plan["clearup_count"] >= 2
    assert reads["active"] == 1, "actieve files moeten één keer geïndexeerd worden, niet per kandidaat herlezen"


def test_32426_active_symlink_tree_is_walked_once_after_text_inventory(tmp_path: Path, monkeypatch):
    mod = _load()
    _project(tmp_path)

    original = Path.rglob
    infra_walks = {"count": 0}

    def counted(self: Path, pattern: str):
        if self == tmp_path / "Infra":
            infra_walks["count"] += 1
        return original(self, pattern)

    monkeypatch.setattr(Path, "rglob", counted)
    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.26", keep_rollbacks=3)

    assert plan["clearup_count"] >= 2
    # Eén walk voor text inventory + één walk voor symlink inventory.
    assert infra_walks["count"] <= 2, "symlinkboom mag niet opnieuw per cleanup-kandidaat worden doorlopen"


def test_32426_indexed_dependency_scan_preserves_blocking_semantics(tmp_path: Path):
    mod = _load()
    _project(tmp_path)
    (tmp_path / "Infra/active.conf").write_text("fallback=App.__rollback_32.4.20\n", encoding="utf-8")
    os.symlink(tmp_path / "App.__rollback_32.4.19", tmp_path / "Infra/runtime-fallback")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.26", keep_rollbacks=3)
    by_path = {item["source_path"]: item for item in plan["items"]}

    assert by_path["App.__rollback_32.4.20"]["disposition"] == "REVIEW"
    assert any(ref["path"] == "Infra/active.conf" for ref in by_path["App.__rollback_32.4.20"]["active_references"])
    assert by_path["App.__rollback_32.4.19"]["disposition"] == "REVIEW"
    assert any("symlink_dependency" in ref["matches"] for ref in by_path["App.__rollback_32.4.19"]["active_references"])
