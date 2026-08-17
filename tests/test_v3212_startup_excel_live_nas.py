from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
PATHS = APP / "project_paths.py"
MAIN = APP / "main.py"


def _load_paths():
    spec = importlib.util.spec_from_file_location("project_paths_v3212", PATHS)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _make_layout(root: Path) -> Path:
    layout = root / "Project Energie"
    (layout / "App").mkdir(parents=True)
    (layout / "App" / "VERSIE.txt").write_text("32.2.2\n", encoding="utf-8")
    (layout / "Inbox").mkdir()
    return layout


def test_wait_for_live_nas_retries_instead_of_returning_unmounted_fallback(tmp_path: Path):
    paths = _load_paths()
    share = tmp_path / "share"
    share.mkdir()
    created: list[Path] = []

    def mount_after_first_attempt(_seconds: float) -> None:
        if not created:
            created.append(_make_layout(share))

    mount, layout = paths.wait_for_existing_nas_roots(
        share,
        attempts=2,
        delay_seconds=0,
        sleep_fn=mount_after_first_attempt,
    )
    assert layout == created[0]
    assert mount == created[0]


def test_startup_excel_uses_fresh_live_nas_root_and_writes_status_file():
    source = MAIN.read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.3.15"' in source
    start = source.index("def startup_historical_energy_excel")
    end = source.index("threading.Thread(\n        target=startup_historical_energy_excel", start)
    block = source[start:end]
    assert "wait_for_existing_nas_roots" in block
    assert "bootstrap_historical_energy_workbook(live_nas_layout_root)" in block
    assert "bootstrap_historical_energy_workbook(NAS_LAYOUT_ROOT)" not in block
    assert "HISTORICAL_BOOTSTRAP_STATUS_RELATIVE" in block
    assert "migrate_project_structure(live_nas_layout_root)" in block

    sidecar_start = source.index("def run_historical_energy_excel_sidecar")
    sidecar_end = source.index("def create_project_backup", sidecar_start)
    sidecar = source[sidecar_start:sidecar_end]
    assert "wait_for_existing_nas_roots" in sidecar
    assert "migrate_project_structure(live_nas_layout_root)" in sidecar
    assert "publish_historical_energy_workbook(\n            live_nas_layout_root," in sidecar
    assert "publish_historical_energy_workbook(\n            NAS_LAYOUT_ROOT," not in sidecar
