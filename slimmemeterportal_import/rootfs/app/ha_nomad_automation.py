from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen as default_urlopen

AUTOMATION_ID = "nomad_energie_assistent"
AUTOMATION_ALIAS = "Nomad - Energie Assistent"
AUTOMATION_DESCRIPTION = "Native Home Assistant koppeling voor Nomad"
CORE_AUTOMATION_URL = (
    "http://supervisor/core/api/config/automation/config/"
    + AUTOMATION_ID
)
CORE_AUTOMATION_RELOAD_URL = "http://supervisor/core/api/services/automation/reload"


def build_nomad_automation_config() -> dict[str, Any]:
    """Return the exact UI-managed Home Assistant automation payload.

    The id is deliberately omitted: Home Assistant owns it through the
    /config/automation/config/{id} endpoint, matching the frontend editor.
    """
    return {
        "alias": AUTOMATION_ALIAS,
        "description": AUTOMATION_DESCRIPTION,
        "triggers": [
            {
                "trigger": "conversation",
                "command": ["Nomad {vraag}", "No mad {vraag}"],
            }
        ],
        "conditions": [],
        "actions": [
            {
                "variables": {
                    "nomad_request_id": "{{ this.context.id }}",
                    "nomad_session_id": (
                        "{{ trigger.satellite_id if trigger.satellite_id else "
                        "(trigger.device_id if trigger.device_id else "
                        "'home-assistant-assist') }}"
                    ),
                }
            },
            {
                "event": "energie_nomad_request",
                "event_data": {
                    "request_id": "{{ nomad_request_id }}",
                    "query": "{{ trigger.slots.vraag }}",
                    "session_id": "{{ nomad_session_id }}",
                },
            },
            {
                "wait_for_trigger": [
                    {
                        "trigger": "event",
                        "event_type": "energie_nomad_response",
                        "event_data": {"request_id": "{{ nomad_request_id }}"},
                    }
                ],
                "timeout": "00:00:05",
                "continue_on_timeout": True,
            },
            {
                "if": [
                    {
                        "condition": "template",
                        "value_template": "{{ wait.completed and wait.trigger is not none }}",
                    }
                ],
                "then": [
                    {
                        "set_conversation_response": "{{ wait.trigger.event.data.speech }}"
                    }
                ],
                "else": [
                    {
                        "set_conversation_response": "Nomad is tijdelijk niet beschikbaar."
                    }
                ],
            },
        ],
        "mode": "parallel",
        "max": 5,
    }


def _read_json_response(response: Any) -> dict[str, Any]:
    raw = response.read()
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise RuntimeError("Home Assistant automation API response is not an object")
    return parsed


def _request(
    method: str,
    token: str,
    *,
    payload: dict[str, Any] | None,
    urlopen: Callable[..., Any],
    timeout: float,
) -> dict[str, Any] | None:
    data = None
    headers = {"Authorization": f"Bearer {token}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(CORE_AUTOMATION_URL, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return _read_json_response(response)
    except HTTPError as exc:
        if method == "GET" and exc.code == 404:
            return None
        raise RuntimeError(
            f"Home Assistant automation API {method} failed with HTTP {exc.code}"
        ) from exc



def _reload_automations(
    token: str,
    *,
    urlopen: Callable[..., Any],
    timeout: float,
) -> None:
    data = b"{}"
    request = Request(
        CORE_AUTOMATION_RELOAD_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read()
    except HTTPError as exc:
        raise RuntimeError(
            f"Home Assistant automation reload failed with HTTP {exc.code}"
        ) from exc


def ensure_nomad_automation(
    *,
    urlopen: Callable[..., Any] = default_urlopen,
    timeout: float = 5.0,
) -> dict[str, Any]:
    """Create Nomad's one owned automation if missing; never overwrite conflicts."""
    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN ontbreekt")

    existing = _request(
        "GET",
        token,
        payload=None,
        urlopen=urlopen,
        timeout=timeout,
    )
    if existing is not None:
        if (
            existing.get("alias") == AUTOMATION_ALIAS
            and existing.get("description") == AUTOMATION_DESCRIPTION
        ):
            _reload_automations(token, urlopen=urlopen, timeout=timeout)
            return {
                "status": "already_present",
                "automation_id": AUTOMATION_ID,
                "reloaded": True,
            }
        return {
            "status": "conflict",
            "automation_id": AUTOMATION_ID,
        }

    _request(
        "POST",
        token,
        payload=build_nomad_automation_config(),
        urlopen=urlopen,
        timeout=timeout,
    )
    _reload_automations(token, urlopen=urlopen, timeout=timeout)
    return {
        "status": "installed",
        "automation_id": AUTOMATION_ID,
        "reloaded": True,
    }
