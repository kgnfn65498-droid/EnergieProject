from __future__ import annotations

import json
import logging
import os
import time
import threading
from typing import Any, Callable

try:
    import websocket
except ImportError:  # pragma: no cover - runtime dependency gate covers this
    websocket = None

LOGGER = logging.getLogger(__name__)

CORE_WEBSOCKET_URL = "ws://supervisor/core/websocket"
REQUEST_EVENT = "energie_nomad_request"
RESPONSE_EVENT = "energie_nomad_response"
MAX_QUERY_BYTES = 32 * 1024
MAX_ID_LENGTH = 160


def _clean_identifier(value: Any, field_name: str, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    cleaned = value.strip()
    if required and not cleaned:
        raise ValueError(f"{field_name} is required")
    if len(cleaned) > MAX_ID_LENGTH:
        raise ValueError(f"{field_name} exceeds {MAX_ID_LENGTH} characters")
    return cleaned or None


def validate_request_event(data: Any) -> dict[str, str | None]:
    if not isinstance(data, dict):
        raise ValueError("event data must be an object")
    unsupported = sorted(set(data) - {"request_id", "query", "session_id"})
    if unsupported:
        raise ValueError("unsupported Nomad event fields: " + ", ".join(unsupported))

    request_id = _clean_identifier(data.get("request_id"), "request_id", required=True)
    query = data.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query is required")
    query = query.strip()
    if len(query.encode("utf-8")) > MAX_QUERY_BYTES:
        raise ValueError("query exceeds 32 KiB")
    session_id = _clean_identifier(data.get("session_id"), "session_id", required=False)
    return {"request_id": request_id, "query": query, "session_id": session_id}


class NomadGreetingTracker:
    def __init__(self, idle_seconds: int = 900) -> None:
        self.idle_seconds = int(idle_seconds)
        self._last_seen: dict[str, float] = {}

    def should_greet(self, session_id: str | None, *, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else float(now)
        key = (session_id or "home-assistant-assist").strip() or "home-assistant-assist"
        previous = self._last_seen.get(key)
        self._last_seen[key] = current
        return previous is None or (current - previous) >= self.idle_seconds


def _prefix_greeting(speech: str, display_name: str) -> str:
    name = display_name.strip() or "Nomad"
    text = speech.strip()
    return f"{name} hier. {text}" if text else f"{name} hier."


def handle_request_event(
    data: Any,
    *,
    respond: Callable[..., dict[str, Any]],
    display_name: str,
    greeting_enabled: bool,
    greeting_tracker: NomadGreetingTracker,
    app_version: str,
    now: float | None = None,
) -> dict[str, Any]:
    request = validate_request_event(data)
    payload = respond(request["query"], session_id=request["session_id"])
    speech = str(payload.get("speech") or "").strip()
    greeted = bool(greeting_enabled and greeting_tracker.should_greet(request["session_id"], now=now))
    if greeted:
        speech = _prefix_greeting(speech, display_name)
    return {
        "request_id": request["request_id"],
        "status": "ok",
        "version": app_version,
        "speech": speech,
        "session_id": payload.get("session_id") or request["session_id"],
        "greeted": greeted,
    }


def _recv_json(ws: Any) -> dict[str, Any]:
    raw = ws.recv()
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise RuntimeError("Home Assistant WebSocket response is not an object")
    return payload


def authenticate_and_subscribe(ws: Any, token: str) -> None:
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN ontbreekt")
    required = _recv_json(ws)
    if required.get("type") != "auth_required":
        raise RuntimeError("Home Assistant WebSocket auth_required ontbreekt")
    ws.send(json.dumps({"type": "auth", "access_token": token}, separators=(",", ":")))
    auth = _recv_json(ws)
    if auth.get("type") != "auth_ok":
        raise RuntimeError("Home Assistant WebSocket authenticatie geweigerd")
    ws.send(json.dumps({"id": 1, "type": "subscribe_events", "event_type": REQUEST_EVENT}, separators=(",", ":")))
    subscribed = _recv_json(ws)
    if subscribed.get("type") != "result" or subscribed.get("id") != 1 or not subscribed.get("success"):
        raise RuntimeError("Home Assistant Nomad event subscription mislukt")


def fire_response_event(ws: Any, command_id: int, event_data: dict[str, Any]) -> int:
    ws.send(json.dumps({
        "id": command_id,
        "type": "fire_event",
        "event_type": RESPONSE_EVENT,
        "event_data": event_data,
    }, ensure_ascii=False, separators=(",", ":")))
    return command_id + 1


class HomeAssistantNomadBridge:
    def __init__(
        self,
        stop_event: Any,
        *,
        respond: Callable[..., dict[str, Any]],
        app_version: str,
        display_name: str = "Nomad",
        greeting_enabled: bool = True,
        greeting_idle_seconds: int = 900,
        websocket_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.stop_event = stop_event
        self.respond = respond
        self.app_version = app_version
        self.display_name = display_name.strip() or "Nomad"
        self.greeting_enabled = bool(greeting_enabled)
        self.greeting_tracker = NomadGreetingTracker(max(60, int(greeting_idle_seconds)))
        self._status_lock = threading.Lock()
        self._status: dict[str, Any] = {
            "status": "starting",
            "connected": False,
            "request_event": REQUEST_EVENT,
            "response_event": RESPONSE_EVENT,
        }
        if websocket_factory is not None:
            self.websocket_factory = websocket_factory
        elif websocket is not None:
            self.websocket_factory = websocket.create_connection
        else:
            self.websocket_factory = None

    def _set_status(self, **values: Any) -> None:
        with self._status_lock:
            self._status.update(values)

    def status_snapshot(self) -> dict[str, Any]:
        with self._status_lock:
            return dict(self._status)

    def _connect(self) -> Any:
        if self.websocket_factory is None:
            raise RuntimeError("websocket-client runtime ontbreekt")
        return self.websocket_factory(CORE_WEBSOCKET_URL, timeout=2.0)

    def _serve(self, ws: Any) -> None:
        token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
        authenticate_and_subscribe(ws, token)
        command_id = 2
        self._set_status(status="connected", connected=True, last_error_type=None)
        LOGGER.info("Nomad event bridge verbonden en geabonneerd op %s", REQUEST_EVENT)
        while not self.stop_event.is_set():
            try:
                message = _recv_json(ws)
            except Exception as exc:
                if exc.__class__.__name__ in {"WebSocketTimeoutException", "TimeoutError"}:
                    continue
                raise
            if message.get("type") != "event":
                continue
            event = message.get("event")
            if not isinstance(event, dict) or event.get("event_type") != REQUEST_EVENT:
                continue
            try:
                response = handle_request_event(
                    event.get("data"),
                    respond=self.respond,
                    display_name=self.display_name,
                    greeting_enabled=self.greeting_enabled,
                    greeting_tracker=self.greeting_tracker,
                    app_version=self.app_version,
                )
            except Exception as exc:
                data = event.get("data") if isinstance(event.get("data"), dict) else {}
                request_id = str(data.get("request_id") or "").strip()
                if not request_id:
                    LOGGER.warning("Nomad event genegeerd: ongeldig request zonder request_id")
                    continue
                response = {
                    "request_id": request_id[:MAX_ID_LENGTH],
                    "status": "error",
                    "version": self.app_version,
                    "speech": f"{self.display_name} is tijdelijk niet beschikbaar.",
                    "session_id": None,
                    "greeted": False,
                }
                LOGGER.warning("Nomad event kon niet veilig worden beantwoord: %s", type(exc).__name__)
            command_id = fire_response_event(ws, command_id, response)

    def run_forever(self) -> None:
        backoff = 2.0
        while not self.stop_event.is_set():
            ws = None
            try:
                ws = self._connect()
                self._serve(ws)
                backoff = 2.0
            except Exception as exc:
                if not self.stop_event.is_set():
                    self._set_status(status="reconnecting", connected=False, last_error_type=type(exc).__name__, retry_seconds=backoff)
                    LOGGER.warning("Nomad event bridge verbinding onderbroken: %s; retry in %.0fs", type(exc).__name__, backoff)
                    self.stop_event.wait(backoff)
                    backoff = min(backoff * 2.0, 30.0)
            finally:
                if self.stop_event.is_set():
                    self._set_status(status="stopped", connected=False)
                if ws is not None:
                    try:
                        ws.close()
                    except Exception:
                        pass
