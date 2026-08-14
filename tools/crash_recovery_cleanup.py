#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKUP_RE = re.compile(r"^Energie_Complete_Backup_[A-Za-z0-9_.-]+\.zip$")
REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _within(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def _validated_targets(root: Path, request: dict[str, Any]) -> tuple[str, Path, Path, Path]:
    if int(request.get("schema") or 0) != 1:
        raise ValueError("cleanup schema moet exact 1 zijn")

    request_id = str(request.get("request_id") or "").strip()
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise ValueError("cleanup request_id is ongeldig")

    backup_name = str(request.get("backup_name") or "").strip()
    if Path(backup_name).name != backup_name or not BACKUP_RE.fullmatch(backup_name):
        raise ValueError("cleanup backup_name is geen complete Crash Recovery backup")

    expected_manifest = f"{Path(backup_name).stem}_manifest.json"
    manifest_name = str(request.get("manifest_name") or "").strip()
    if manifest_name != expected_manifest or Path(manifest_name).name != manifest_name:
        raise ValueError("cleanup manifest_name hoort niet exact bij de backup")

    staging_raw = str(request.get("restore_staging_path") or "").strip()
    prefix = "/recovery/RestoreStaging/"
    if not staging_raw.startswith(prefix):
        raise ValueError("cleanup RestoreStaging-pad moet een concrete run onder /recovery/RestoreStaging/ zijn")
    relative_stage = staging_raw[len("/recovery/") :]
    relative_path = Path(relative_stage)
    if relative_path.is_absolute() or ".." in relative_path.parts or len(relative_path.parts) < 2:
        raise ValueError("cleanup RestoreStaging-pad is ongeldig")

    backup_root = (root / "Backups").resolve()
    manifest_root = (backup_root / "Manifests").resolve()
    staging_root = (backup_root / "RestoreStaging").resolve()

    backup_path = (backup_root / backup_name).resolve()
    manifest_path = (manifest_root / manifest_name).resolve()
    staging_path = (backup_root / relative_path).resolve()

    if not _within(backup_path, backup_root) or backup_path == backup_root:
        raise ValueError("cleanup backuppad valt buiten Backups")
    if not _within(manifest_path, manifest_root) or manifest_path == manifest_root:
        raise ValueError("cleanup manifestpad valt buiten Backups/Manifests")
    if not _within(staging_path, staging_root) or staging_path == staging_root:
        raise ValueError("cleanup RestoreStaging-pad valt buiten de run-root")

    for target in (backup_path, manifest_path, staging_path):
        if target.exists() and target.is_symlink():
            raise ValueError(f"cleanup weigert symlink: {target.name}")

    return request_id, backup_path, manifest_path, staging_path


def process_cleanup(root: Path, request_path: Path, result_path: Path) -> dict[str, Any]:
    request_id = ""
    removed: list[str] = []
    already_absent: list[str] = []
    warnings: list[str] = []
    try:
        root = root.resolve()
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if not isinstance(request, dict):
            raise ValueError("cleanup request moet een JSON-object zijn")
        request_id, backup_path, manifest_path, staging_path = _validated_targets(root, request)

        for label, target in (
            ("backup", backup_path),
            ("manifest", manifest_path),
            ("restore_staging", staging_path),
        ):
            if not target.exists():
                already_absent.append(label)
                continue
            try:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
                removed.append(label)
            except OSError as exc:
                raise RuntimeError(f"{label} kon niet worden verwijderd: {exc}") from exc

        result = {
            "schema": 1,
            "request_id": request_id,
            "status": "ok",
            "removed": removed,
            "already_absent": already_absent,
            "warnings": warnings,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        _atomic_write_json(result_path, result)
        return result
    except Exception as exc:
        result = {
            "schema": 1,
            "request_id": request_id,
            "status": "error",
            "removed": removed,
            "already_absent": already_absent,
            "warnings": warnings,
            "error": f"{type(exc).__name__}: {exc}",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            _atomic_write_json(result_path, result)
        except Exception:
            pass
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Veilige Crash Recovery cleanup voor QNAP-watcher")
    parser.add_argument("--root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()

    result = process_cleanup(Path(args.root), Path(args.request), Path(args.result))
    if result.get("status") == "ok":
        print(json.dumps(result, ensure_ascii=False))
        return 0
    print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
