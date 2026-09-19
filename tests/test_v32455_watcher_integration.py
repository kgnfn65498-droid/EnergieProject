from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WATCHER = ROOT / "tests" / "fixtures" / "pre57" / "release_watcher.sh"


def _function_source(name: str) -> str:
    source = WATCHER.read_text(encoding="utf-8")
    match = re.search(rf"(?ms)^{re.escape(name)}\(\)\{{\n.*?^\}}\n", source)
    assert match, f"function {name} not found"
    return match.group(0)


def _run_script(script: str, cwd: Path) -> None:
    result = subprocess.run(
        ["sh", "-eu", "-c", script],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr


def test_write_status_is_idempotent_for_identical_semantic_state(tmp_path: Path):
    fn = _function_source("write_status")
    status = tmp_path / "latest_release_status.txt"
    script = f'''STATUSFILE={str(status)!r}\n{fn}\nwrite_status BLOCKED "same detail"\n'''
    _run_script(script, tmp_path)
    first_bytes = status.read_bytes()
    first_mtime = status.stat().st_mtime_ns

    time.sleep(1.1)
    _run_script(script, tmp_path)

    assert status.read_bytes() == first_bytes
    assert status.stat().st_mtime_ns == first_mtime


def test_write_status_rewrites_when_semantic_state_changes(tmp_path: Path):
    fn = _function_source("write_status")
    status = tmp_path / "latest_release_status.txt"
    first = f'''STATUSFILE={str(status)!r}\n{fn}\nwrite_status BLOCKED "first"\n'''
    second = f'''STATUSFILE={str(status)!r}\n{fn}\nwrite_status BLOCKED "second"\n'''
    _run_script(first, tmp_path)
    first_bytes = status.read_bytes()
    time.sleep(1.1)
    _run_script(second, tmp_path)
    assert status.read_bytes() != first_bytes
    assert "| BLOCKED | second" in status.read_text(encoding="utf-8")


def test_preflight_is_between_integrity_and_installer():
    source = WATCHER.read_text(encoding="utf-8")
    integrity = source.index('if zip_integrity_ok "$ZIP_PATH"; then')
    installer = source.index('if run_installer; then', integrity)
    between = source[integrity:installer]
    assert 'release_preflight_allows "$ZIP_PATH"' in between
    assert 'write_status "BLOCKED"' in between


def test_watcher_once_uses_same_release_preflight_before_installer():
    source = WATCHER.read_text(encoding='utf-8')
    start = source.index('  once)')
    end = source.index('  run) ;;', start)
    branch = source[start:end]
    preflight = branch.index('release_preflight_allows')
    installer = branch.index('run_installer')
    assert preflight < installer
    assert 'exit 3' in branch or 'PREFLIGHT_RC' in branch
