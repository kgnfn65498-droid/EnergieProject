from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def _load_hotfix():
    spec = importlib.util.spec_from_file_location(
        "mcp_path_health_runtime_hotfix_v32530_test",
        TOOLS / "mcp_path_health_runtime_hotfix.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _old_common() -> str:
    return """from pathlib import Path\n\ndef _resolve_inside(root: Path, relative_path: str) -> Path:\n    clean = str(relative_path).strip()\n    candidate = root if clean in {\"\", \".\", \"/\"} else (root / clean.lstrip(\"/\")).resolve()\n    try:\n        candidate.relative_to(root)\n    except ValueError as exc:\n        raise ValueError(f\"Pad valt buiten de toegestane root: {root}\") from exc\n    return candidate\n"""


def test_32530_path_health_hotfix_is_idempotent_and_fingerprint_bound(tmp_path):
    hotfix = _load_hotfix()
    project = tmp_path / "project"
    native = project / "Infra/Docker/native-mcp"
    native.mkdir(parents=True)

    (native / "common.py").write_text(_old_common(), encoding="utf-8")
    (native / "server.py").write_text(
        "import tools_master_health  # noqa: F401\nfrom registry import mcp\n",
        encoding="utf-8",
    )
    (native / "runtime_fingerprint.py").write_text(
        'NATIVE_TARGETS = (\n    "server.py",\n)\n',
        encoding="utf-8",
    )

    first = hotfix.apply(project)
    assert first["status"] == "GREEN"
    assert first["project_root_alias_current"] is True
    assert first["health_scan_guard_current"] is True
    assert first["fingerprint_covers_fix"] is True
    assert first["reload_required"] is True

    common = (native / "common.py").read_text(encoding="utf-8")
    assert hotfix.COMMON_MARKER in common
    assert "clean == str(root)" in common
    assert "candidate.relative_to(root)" in common

    server = (native / "server.py").read_text(encoding="utf-8")
    assert server.count("import master_health_scan_guard  # noqa: F401") == 1

    fingerprint = (native / "runtime_fingerprint.py").read_text(encoding="utf-8")
    assert fingerprint.count('"common.py"') == 1
    assert fingerprint.count('"master_health_scan_guard.py"') == 1

    guard = (native / "master_health_scan_guard.py").read_text(encoding="utf-8")
    assert hotfix.HEALTH_MARKER in guard
    assert "name != _health.BACKUP_DIR_NAME" in guard
    assert "_ORIGINAL_FILES(directory, recursive=False)" in guard

    second = hotfix.apply(project)
    assert second["status"] == "GREEN"
    assert second["changed"] == []
    assert second["reload_required"] is False


def test_32530_release_runtime_adapter_enforces_path_health_contract():
    source = (TOOLS / "release_runtime_adapter.py").read_text(encoding="utf-8")
    assert "import mcp_path_health_runtime_hotfix" in source
    assert "path_health=mcp_path_health_runtime_hotfix.apply(self.root)" in source
    assert "native_mcp_path_health_contract_red" in source
    assert "fingerprint_covers_fix" in source
