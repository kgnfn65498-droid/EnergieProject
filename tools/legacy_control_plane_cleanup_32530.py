from __future__ import annotations

"""32.5.30 post-acceptance cleanup for two proven stopped control-plane backups."""

import http.client
import json
import os
import socket
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

LEGACY_CONTAINERS = (
    "energie-control-plane-pre32524-20260927T135556",
    "energie-control-plane-type2-legacy-0dc5d7d08afe",
)
CANONICAL = "energie-control-plane"
SOCKET_PATH = "/var/run/docker.sock"


class _UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, socket_path: str, timeout: float = 15.0):
        super().__init__("localhost", timeout=timeout)
        self.socket_path = socket_path

    def connect(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect(self.socket_path)
        self.sock = sock


def _request(method: str, path: str, ok: tuple[int, ...]) -> tuple[int, Any]:
    conn = _UnixHTTPConnection(SOCKET_PATH)
    try:
        conn.request(method, path)
        response = conn.getresponse()
        raw = response.read()
        if response.status not in ok:
            raise RuntimeError(f"Docker HTTP {response.status}: {raw[:500]!r}")
        if not raw:
            return response.status, {}
        return response.status, json.loads(raw.decode("utf-8"))
    finally:
        conn.close()


def _json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}


def cleanup_legacy_control_plane_containers(project_root: Path | str) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if not Path(SOCKET_PATH).exists():
        return {
            "schema": "energie_32530_legacy_control_plane_cleanup_v1",
            "status": "NOT_AVAILABLE",
            "reason": "docker_socket_not_mounted",
            "removed": [],
            "deletion_performed": False,
        }

    version = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    try:
        version_tuple = tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        raise RuntimeError("active release identity invalid") from exc
    if version_tuple < (32, 5, 30):
        raise RuntimeError("legacy container cleanup requires active 32.5.30+")

    if (root / "Data/03_Systeem/Projectmanager/ReleaseController/control_plane_restart_attempt.json").exists():
        raise RuntimeError("control-plane restart attempt is active")

    rc = _json(root / "Data/03_Systeem/Projectmanager/ReleaseController/runtime.json")
    if str(rc.get("phase") or "").upper() != "IDLE" or str(rc.get("status") or "").upper() != "IDLE":
        raise RuntimeError("ReleaseController must be IDLE")

    runtime = _json(root / "Data/03_Systeem/Projectmanager/ControlPlane/Runtime/runtime.json")
    heartbeat = float(runtime.get("heartbeat_at_epoch") or 0)
    if heartbeat <= 0 or time.time() - heartbeat > 120:
        raise RuntimeError("canonical control-plane heartbeat is stale")

    _status, canonical = _request("GET", f"/containers/{quote(CANONICAL, safe='')}/json", (200,))
    if not bool((canonical.get("State") or {}).get("Running")):
        raise RuntimeError("canonical control-plane is not running")
    canonical_id = str(canonical.get("Id") or "")
    if not canonical_id:
        raise RuntimeError("canonical control-plane identity missing")

    rows = []
    removed = []
    for name in LEGACY_CONTAINERS:
        status, info = _request("GET", f"/containers/{quote(name, safe='')}/json", (200, 404))
        if status == 404:
            rows.append({"name": name, "state": "ABSENT"})
            continue
        legacy_id = str(info.get("Id") or "")
        if not legacy_id or legacy_id == canonical_id:
            raise RuntimeError(f"legacy container identity unsafe: {name}")
        if bool((info.get("State") or {}).get("Running")):
            raise RuntimeError(f"legacy container unexpectedly running: {name}")
        _request("DELETE", f"/containers/{quote(name, safe='')}?v=1&force=0", (204,))
        check_status, _check = _request("GET", f"/containers/{quote(name, safe='')}/json", (404,))
        if check_status != 404:
            raise RuntimeError(f"legacy container deletion readback failed: {name}")
        rows.append({"name": name, "state": "REMOVED"})
        removed.append(name)

    return {
        "schema": "energie_32530_legacy_control_plane_cleanup_v1",
        "status": "GREEN",
        "canonical_container": CANONICAL,
        "canonical_id": canonical_id,
        "rows": rows,
        "removed": removed,
        "deletion_performed": bool(removed),
    }
