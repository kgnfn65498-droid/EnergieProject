from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

SUPERVISOR_SELF_INFO_URL = "http://supervisor/addons/self/info"
SUPERVISOR_DISCOVERY_URL = "http://supervisor/discovery"
DISCOVERY_STATE_PATH = Path("/data/energie_assistant_discovery.json")
SERVICE = "energie_assistant"


def build_discovery_payload(*, host: str, app_version: str) -> dict[str, Any]:
    return {
        "service": SERVICE,
        "config": {
            "host": host,
            "port": 8099,
            "ssl": False,
            "api_path": "/api/assistant/respond",
            "version": app_version,
        },
    }


def _request_json(url: str, *, method: str = "GET", payload: dict[str, Any] | None = None, timeout: float = 5.0) -> dict[str, Any]:
    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN ontbreekt")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError("Supervisor response is geen JSON-object")
    return parsed


def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def _load_previous_uuid() -> str | None:
    try:
        data = json.loads(DISCOVERY_STATE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    value = data.get("uuid") if isinstance(data, dict) else None
    return str(value).strip() or None if value is not None else None


def publish_assistant_discovery(*, app_version: str) -> dict[str, Any]:
    """Publish secret-free Supervisor discovery for the internal read-only endpoint."""
    info = _unwrap(_request_json(SUPERVISOR_SELF_INFO_URL))
    host = str(info.get("ip_address") or info.get("ip") or "").strip()
    if not host:
        hostname = str(info.get("hostname") or info.get("slug") or "").strip()
        if hostname:
            host = hostname.replace("_", "-")
    if not host:
        raise RuntimeError("Supervisor self info bevat geen intern hostadres")

    previous_uuid = _load_previous_uuid()
    if previous_uuid:
        try:
            _request_json(f"{SUPERVISOR_DISCOVERY_URL}/{previous_uuid}", method="DELETE")
        except (OSError, urllib.error.URLError, RuntimeError, json.JSONDecodeError):
            pass

    payload = build_discovery_payload(host=host, app_version=app_version)
    result = _unwrap(_request_json(SUPERVISOR_DISCOVERY_URL, method="POST", payload=payload))
    uuid = str(result.get("uuid") or "").strip() or None
    state = {"uuid": uuid}
    DISCOVERY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = DISCOVERY_STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(DISCOVERY_STATE_PATH)
    return {"status": "published", "host": host, "uuid": uuid, "payload": payload}
