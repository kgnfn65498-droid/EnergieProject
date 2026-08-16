import json
import os
import pathlib
import runpy
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
HELPER = ROOT / "tools/mcp_system_path_guard_hotfix.py"
WATCHER = ROOT / "tools/release_watcher.sh"

EXPECTED_DUPLICATE = (
    pathlib.Path("Data/03_Systeem/Data/03_Systeem/Projectmanager/Runs")
    / "20260816T1716Z_v32_3_0_live_acceptance.json"
)


def fake_tools_source() -> str:
    return '''from pathlib import Path\nimport os\nimport re\nSYSTEM_ROOT = Path(os.environ.get("ENERGIE_SYSTEM_ROOT", "/system")).resolve()\n\ndef _system_path(path: str) -> Path:\n    """Resolve a path strictly below the dedicated writable system root."""\n    raw = str(path or ".").strip()\n    relative = Path(raw)\n    if relative.is_absolute():\n        raise ValueError("Gebruik een relatief pad binnen Data/03_Systeem.")\n\n    target = (SYSTEM_ROOT / relative).resolve(strict=False)\n    if target != SYSTEM_ROOT and SYSTEM_ROOT not in target.parents:\n        raise ValueError("Pad valt buiten Data/03_Systeem.")\n    return target\n'''


def exact_duplicate_payload() -> str:
    payload = {
        "schema": "energie_v32_3_0_live_acceptance_v1",
        "checked_at": "2026-08-16T17:16:00Z",
        "version": "32.3.0",
        "candidate_sha256": "dada3770dd41c06c0cab2d4f916e16c731e5088222c71ae8d426de5fbeda9372",
        "result": "LIVE_INSTALLED_RUNTIME_ACTIVE_ACCEPTANCE_PARTIAL_OBSERVABILITY_GAP",
        "installation": {"processed_zip_bytes": 4730677},
        "safety": {"terminal_used": False, "finalize_month_used": False, "august_closed": False},
        "padding": "",
    }
    # The real accidental artifact is exactly 3278 bytes. Pad a valid JSON fixture to match.
    while True:
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        delta = 3278 - len(text.encode("utf-8"))
        if delta == 0:
            return text
        assert delta > 0
        payload["padding"] += "x" * delta


def seed_project(tmp_path, *, valid_duplicate=True):
    project = tmp_path / "EnergieProject"
    (project / "App").mkdir(parents=True)
    (project / "Backups").mkdir(parents=True)
    source = project / "Infra/Docker/native-mcp/tools_filesystem.py"
    source.parent.mkdir(parents=True)
    source.write_text(fake_tools_source(), encoding="utf-8")
    (project / "Data/03_Systeem/Projectmanager").mkdir(parents=True)
    (project / "Inbox/logs").mkdir(parents=True)
    target = project / EXPECTED_DUPLICATE
    target.parent.mkdir(parents=True)
    if valid_duplicate:
        target.write_text(exact_duplicate_payload(), encoding="utf-8")
    else:
        target.write_text("not-the-known-artifact\n", encoding="utf-8")
    return project, source, target


def run_helper(project):
    result = project / "Inbox/logs/mcp_system_path_guard_hotfix_v3231.json"
    proc = subprocess.run(
        [sys.executable, str(HELPER), "--root", str(project), "--result", str(result)],
        text=True,
        capture_output=True,
    )
    data = json.loads(result.read_text(encoding="utf-8")) if result.exists() else None
    return proc, data


def test_hotfix_patches_runtime_guard_and_removes_only_known_duplicate(tmp_path, monkeypatch):
    project, source, target = seed_project(tmp_path)
    before = source.read_text(encoding="utf-8")

    proc, result = run_helper(project)

    assert proc.returncode == 0, proc.stderr
    assert result["status"] == "ok"
    assert result["guard"]["status"] == "patched"
    assert result["cleanup"]["status"] == "removed_exact_duplicate_tree"
    assert not (project / "Data/03_Systeem/Data").exists()
    backup = pathlib.Path(result["guard"]["backup"])
    assert backup.read_text(encoding="utf-8") == before

    monkeypatch.setenv("ENERGIE_SYSTEM_ROOT", str(project / "Data/03_Systeem"))
    ns = runpy.run_path(str(source))
    for bad in ["Data/03_Systeem/Projectmanager/Runs/x.json", "./Data/03_Systeem/x", r"Data\\03_Systeem\\x"]:
        try:
            ns["_system_path"](bad)
        except ValueError as exc:
            assert "prefix" in str(exc).lower() or "relatief" in str(exc).lower()
        else:
            raise AssertionError(f"prefixed system path was accepted: {bad}")
    assert ns["_system_path"]("Projectmanager/Runs/x.json") == project / "Data/03_Systeem/Projectmanager/Runs/x.json"


def test_hotfix_is_idempotent(tmp_path):
    project, source, target = seed_project(tmp_path)
    first, result1 = run_helper(project)
    assert first.returncode == 0, first.stderr
    second, result2 = run_helper(project)
    assert second.returncode == 0, second.stderr
    assert result2["guard"]["status"] == "already_guarded"
    assert result2["cleanup"]["status"] == "already_absent"


def test_hotfix_refuses_unknown_duplicate_content(tmp_path):
    project, source, target = seed_project(tmp_path, valid_duplicate=False)
    proc, result = run_helper(project)
    assert proc.returncode != 0
    assert result["status"] == "error"
    assert target.exists()
    # Guard may safely patch, but unknown user content must never be removed.
    assert project.joinpath("Data/03_Systeem/Data").exists()


def test_watcher_runs_hotfix_before_release_scan():
    source = WATCHER.read_text(encoding="utf-8")
    assert 'MCP_GUARD_HOTFIX_HELPER="$PROJECT/tools/mcp_system_path_guard_hotfix.py"' in source
    assert "process_mcp_guard_hotfix" in source
    startup = source.split('log "Release watcher gestart; interval=${INTERVAL}s"', 1)[1]
    assert startup.index("process_mcp_guard_hotfix") < startup.index("while :; do")
