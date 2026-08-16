#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

TARGET_REL = Path("Infra/Docker/native-mcp/tools_filesystem.py")
DUPLICATE_REL = Path(
    "Data/03_Systeem/Data/03_Systeem/Projectmanager/Runs/"
    "20260816T1716Z_v32_3_0_live_acceptance.json"
)
CANONICAL_PM_REL = Path("Data/03_Systeem/Projectmanager")
BACKUP_REL = Path("Backups/MCPHotfix/v32.3.1/tools_filesystem.py.pre")
EXPECTED_DUPLICATE_SIZE = 3278
EXPECTED_SCHEMA = "energie_v32_3_0_live_acceptance_v1"
EXPECTED_VERSION = "32.3.0"
EXPECTED_CANDIDATE_SHA = "dada3770dd41c06c0cab2d4f916e16c731e5088222c71ae8d426de5fbeda9372"
EXPECTED_RESULT = "LIVE_INSTALLED_RUNTIME_ACTIVE_ACCEPTANCE_PARTIAL_OBSERVABILITY_GAP"

OLD = '''    raw = str(path or ".").strip()\n    relative = Path(raw)\n    if relative.is_absolute():\n        raise ValueError("Gebruik een relatief pad binnen Data/03_Systeem.")\n'''
NEW = '''    raw = str(path or ".").strip()\n    normalized = re.sub(r"/+", "/", raw.replace("\\\\", "/"))\n    while normalized.startswith("./"):\n        normalized = normalized[2:]\n    if normalized == "Data/03_Systeem" or normalized.startswith("Data/03_Systeem/"):\n        raise ValueError(\n            "Gebruik een pad relatief aan Data/03_Systeem; laat de prefix Data/03_Systeem weg."\n        )\n    relative = Path(raw)\n    if relative.is_absolute():\n        raise ValueError("Gebruik een relatief pad binnen Data/03_Systeem.")\n'''
GUARD_MARKER = 'normalized == "Data/03_Systeem" or normalized.startswith("Data/03_Systeem/")'


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_result(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".tmp-{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def validate_root(root: Path) -> Path:
    root = root.resolve()
    for rel in (Path("App"), Path("Infra"), Path("Data/03_Systeem"), Path("Inbox"), Path("Backups")):
        if not (root / rel).exists():
            raise RuntimeError(f"Projectroot ongeldig; ontbreekt: {rel.as_posix()}")
    canonical = root / CANONICAL_PM_REL
    if not canonical.is_dir() or canonical.is_symlink():
        raise RuntimeError("Canonieke Data/03_Systeem/Projectmanager ontbreekt of is onveilig.")
    return root


def patch_guard(root: Path) -> dict:
    source = root / TARGET_REL
    if not source.is_file() or source.is_symlink():
        raise RuntimeError("MCP tools_filesystem.py ontbreekt of is onveilig.")
    text = source.read_text(encoding="utf-8")
    if GUARD_MARKER in text:
        return {"status": "already_guarded", "target": TARGET_REL.as_posix(), "backup": None}
    if text.count(OLD) != 1:
        raise RuntimeError("Verwachte _system_path-bronvorm niet exact één keer gevonden; patch geweigerd.")

    patched = text.replace(OLD, NEW, 1)
    compile(patched, str(source), "exec")

    backup = root / BACKUP_REL
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        if backup.read_text(encoding="utf-8") != text:
            raise RuntimeError("Hotfix-backup bestaat maar komt niet overeen met actuele pre-patchbron.")
    else:
        shutil.copyfile(source, backup)

    tmp = source.with_name(source.name + f".hotfix-{os.getpid()}")
    tmp.write_text(patched, encoding="utf-8")
    compile(tmp.read_text(encoding="utf-8"), str(source), "exec")
    os.replace(tmp, source)

    actual = source.read_text(encoding="utf-8")
    if GUARD_MARKER not in actual:
        raise RuntimeError("Guardmarker ontbreekt na patch.")
    return {
        "status": "patched",
        "target": TARGET_REL.as_posix(),
        "backup": str(backup),
    }


def validate_known_duplicate(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Bekende duplicate target is geen regulier bestand.")
    size = path.stat().st_size
    if size != EXPECTED_DUPLICATE_SIZE:
        raise RuntimeError(f"Duplicate target heeft onverwachte grootte: {size} bytes.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Duplicate target is geen geldige JSON: {exc}") from exc
    required = {
        "schema": EXPECTED_SCHEMA,
        "version": EXPECTED_VERSION,
        "candidate_sha256": EXPECTED_CANDIDATE_SHA,
        "result": EXPECTED_RESULT,
    }
    for key, expected in required.items():
        if payload.get(key) != expected:
            raise RuntimeError(f"Duplicate target veld {key!r} wijkt af; cleanup geweigerd.")
    if (payload.get("installation") or {}).get("processed_zip_bytes") != 4730677:
        raise RuntimeError("Duplicate target processed_zip_bytes wijkt af; cleanup geweigerd.")


def cleanup_duplicate(root: Path) -> dict:
    target = root / DUPLICATE_REL
    duplicate_root = root / "Data/03_Systeem/Data"
    if not target.exists():
        if duplicate_root.exists():
            raise RuntimeError("Bekende foutkopie ontbreekt maar dubbele Data-root bestaat nog; niets verwijderd.")
        return {"status": "already_absent", "target": DUPLICATE_REL.as_posix()}

    parent_entries = list(target.parent.iterdir())
    if parent_entries != [target]:
        names = sorted(p.name for p in parent_entries)
        raise RuntimeError(f"Runs-map bevat onverwachte entries: {names}; cleanup geweigerd.")
    validate_known_duplicate(target)
    target.unlink()

    # Alleen de exact bekende lege fouttak omhoog opruimen; stop zodra iets niet leeg is.
    for directory in [
        target.parent,
        target.parent.parent,
        target.parent.parent.parent,
        target.parent.parent.parent.parent,
    ]:
        if directory.is_symlink():
            raise RuntimeError(f"Symlink in cleanupketen: {directory}")
        if any(directory.iterdir()):
            raise RuntimeError(f"Cleanupketen niet leeg na targetverwijdering: {directory}")
        directory.rmdir()

    if duplicate_root.exists():
        raise RuntimeError("Dubbele Data-root bestaat nog na exacte cleanup.")
    return {"status": "removed_exact_duplicate_tree", "target": DUPLICATE_REL.as_posix()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    payload = {
        "schema": "energie_mcp_system_path_guard_hotfix_v3231",
        "started_at": now_iso(),
        "status": "error",
        "guard": None,
        "cleanup": None,
        "mcp_restart_required": True,
    }
    try:
        root = validate_root(Path(args.root))
        payload["guard"] = patch_guard(root)
        payload["cleanup"] = cleanup_duplicate(root)
        payload["status"] = "ok"
        payload["finished_at"] = now_iso()
        write_result(result_path, payload)
        print(json.dumps(payload, ensure_ascii=False))
        return 0
    except Exception as exc:
        payload["error"] = str(exc)
        payload["finished_at"] = now_iso()
        write_result(result_path, payload)
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
