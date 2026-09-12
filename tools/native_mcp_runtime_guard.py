#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from datetime import datetime, timezone
from pathlib import Path

MARKER_REL = Path("Data/03_Systeem/Projectmanager/RuntimeEvidence/native_mcp_runtime_fingerprint.json")
STATE_REL = Path("Inbox/native_mcp_runtime/runtime_guard.json")
SCHEMA = "energie_native_mcp_runtime_v3"

def _runtime_module(root: Path):
    path = root / "Infra/Docker/native-mcp/runtime_fingerprint.py"
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("runtime_fingerprint.py missing/unsafe")
    spec = importlib.util.spec_from_file_location("energie_runtime_fingerprint_contract", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("runtime fingerprint contract cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def expected_fingerprint(root: Path | str) -> tuple[str, list[str]]:
    base = Path(root).resolve()
    module = _runtime_module(base)
    return module.compute_fingerprint(native_root=base / "Infra/Docker/native-mcp", project_root=base)

def _atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def probe(root: Path | str) -> dict:
    base = Path(root).resolve()
    expected, targets = expected_fingerprint(base)
    marker_path = base / MARKER_REL
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8")) if marker_path.is_file() else None
    except (OSError, json.JSONDecodeError, UnicodeError):
        marker = None
    actual = str((marker or {}).get("fingerprint") or "")
    schema_ok = (marker or {}).get("schema") == SCHEMA
    targets_ok = list((marker or {}).get("targets") or []) == list(targets)
    ready = schema_ok and targets_ok and actual == expected
    result = {
        "schema": "energie_native_mcp_runtime_guard_v2",
        "status": "GREEN" if ready else "RELOAD_REQUIRED",
        "ready": ready,
        "reload_required": not ready,
        "expected_fingerprint": expected,
        "runtime_fingerprint": actual or None,
        "targets": targets,
        "marker": str(marker_path),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic(base / STATE_REL, result)
    return result

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    result = probe(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result.get("ready") else 3

if __name__ == "__main__":
    raise SystemExit(main())
