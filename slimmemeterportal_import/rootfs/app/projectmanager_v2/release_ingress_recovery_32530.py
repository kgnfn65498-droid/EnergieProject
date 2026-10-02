from __future__ import annotations

"""Projectmanager client for the 32.5.30 single-owner release-ingress recovery."""

import json
import os
import secrets
import time
from pathlib import Path
from typing import Any

from system_path_contract import project_system_path

REQUEST_SCHEMA = "energie_release_ingress_recovery_request_v2"
RESULT_SCHEMA = "energie_release_ingress_recovery_result_v2"
REQUEST_REL = "Inbox/projectmanager_v2/RuntimeV2/release_ingress/recovery_request.json"
RESULT_REL = "Inbox/projectmanager_v2/RuntimeV2/release_ingress/recovery_result.json"
TIMEOUT_SECONDS = 30


def _json(path: Path) -> dict[str, Any]:
    try:
        if path.is_symlink() or not path.is_file():
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError("release ingress request path symlink refused")
    tmp = path.with_name("." + path.name + f".tmp-{os.getpid()}")
    try:
        fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, path)
        try:
            os.chmod(path, 0o666)
        except OSError:
            pass
    finally:
        tmp.unlink(missing_ok=True)


def _call(project_root: Path | str, *, operation: str, expected_fingerprint: str = "") -> dict[str, Any]:
    root = Path(project_root).resolve()
    request_path = Path(project_system_path(root, REQUEST_REL))
    result_path = Path(project_system_path(root, RESULT_REL))
    if request_path.exists():
        raise RuntimeError("another release ingress recovery request is active")
    request_id = secrets.token_hex(16)
    previous_result = _json(result_path)
    payload = {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "operation": operation,
        "created_at_epoch": time.time(),
    }
    if expected_fingerprint:
        payload["expected_fingerprint"] = expected_fingerprint
    _atomic_json(request_path, payload)
    try:
        deadline = time.monotonic() + TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            response = _json(result_path)
            if response.get("schema") == RESULT_SCHEMA and response.get("request_id") == request_id:
                status = str(response.get("status") or "")
                if status != "completed":
                    raise RuntimeError(f"release ingress executor {status}:{response.get('error')}")
                result = response.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("release ingress executor result missing")
                return result
            time.sleep(0.2)
        raise RuntimeError("release ingress recovery watcher timeout")
    finally:
        try:
            current = _json(request_path)
            if current.get("request_id") == request_id:
                request_path.unlink(missing_ok=True)
        except OSError:
            pass
        # Keep the last result as durable evidence; do not restore stale prior bytes.
        _ = previous_result


def inspect_release_ingress(project_root: Path | str) -> dict[str, Any]:
    result = dict(_call(project_root, operation="inspect"))
    result["executed"] = False
    return result


def recover_release_ingress(project_root: Path | str) -> dict[str, Any]:
    inspection = inspect_release_ingress(project_root)
    if inspection.get("status") != "RECOVERABLE":
        return {
            "status": inspection.get("status"),
            "reason": inspection.get("reason"),
            "executed": False,
            "inspection": inspection,
        }
    fingerprint = str(inspection.get("fingerprint") or "")
    if len(fingerprint) != 64:
        raise RuntimeError("release ingress recovery inspection fingerprint invalid")
    result = dict(_call(project_root, operation="recover", expected_fingerprint=fingerprint))
    result.setdefault("executed", result.get("status") == "GREEN")
    result["inspection_fingerprint"] = fingerprint
    return result
