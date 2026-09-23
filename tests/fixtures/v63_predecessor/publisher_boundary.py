"""Frozen critical V63 predecessor publisher boundary.

Source contract captured from live 32.4.63 after independent audit.
Live V63 artifact SHA256:
e0af96f555b4fef61667e17cd5c0fc81324e9edbd0257c5bc1a174e1e3b6c913
"""
from __future__ import annotations
from typing import Any
import urllib.request

APP_VERSION = "32.4.63"

def request_target_transition(token: str, target_version: str) -> dict[str, Any]:
    token = str(token or "").strip()
    target_version = str(target_version or "").strip()
    if not token:
        return {"status": "SKIPPED", "requested": False, "reason": "supervisor_token_missing"}
    if APP_VERSION == target_version:
        return {"status": "ALREADY_TARGET", "requested": False, "target_version": target_version}
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    request = urllib.request.Request(
        "http://supervisor/store/reload", data=b"{}", headers=headers, method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        return {
            "status": "RED", "requested": False, "steps": [],
            "failed_endpoint": "/store/reload",
            "error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "status": "GREEN", "requested": False, "store_refreshed": True,
        "manual_ha_update_required": True, "target_version": target_version,
        "steps": [{"endpoint": "/store/reload", "ok": True, "body": body[:500]}],
    }
