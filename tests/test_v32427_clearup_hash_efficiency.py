from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest

APP = Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
MOD = APP / "project_clearup.py"


def _load():
    spec = importlib.util.spec_from_file_location("project_clearup_32427", MOD)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def _rollback(root: Path, version: str, payload: str = "x") -> Path:
    p = root / f"App.__rollback_{version}"
    p.mkdir(parents=True)
    (p / "VERSIE.txt").write_text(version, encoding="utf-8")
    (p / "payload.txt").write_text(payload, encoding="utf-8")
    return p


def test_32427_same_filesystem_hard_move_hashes_candidate_at_most_twice(monkeypatch, tmp_path: Path):
    mod = _load()
    for v in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, v, payload="payload-" + v)

    target = "App.__rollback_32.4.20"
    real = mod.tree_sha256
    calls = []

    def counted(path):
        rel = Path(path).resolve(strict=False).relative_to(tmp_path.resolve()).as_posix()
        if rel == target or rel.endswith("/original/" + target):
            calls.append(rel)
        return real(path)

    monkeypatch.setattr(mod, "tree_sha256", counted)
    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.27", keep_rollbacks=3)
    mod.apply_clearup_plan(tmp_path, plan, confirmation=plan["confirmation_required"], run_id="efficiency")

    assert len(calls) <= 2, f"candidate tree werd {len(calls)}x volledig gehasht: {calls}"
    assert not (tmp_path / target).exists()
    assert (tmp_path / "CLEARUP/efficiency/original" / target).is_dir()


def test_32427_apply_refreshes_dependencies_without_rehashing_whole_plan(tmp_path: Path):
    mod = _load()
    for v in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, v)
    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.27", keep_rollbacks=3)

    infra = tmp_path / "Infra"
    infra.mkdir()
    (infra / "active.conf").write_text("consumer=App.__rollback_32.4.20\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="dependency|plan|gewijzigd|referentie",):
        mod.apply_clearup_plan(tmp_path, plan, confirmation=plan["confirmation_required"], run_id="blocked")
    assert (tmp_path / "App.__rollback_32.4.20").is_dir()
    assert not (tmp_path / "CLEARUP/blocked/manifest.json").exists()
