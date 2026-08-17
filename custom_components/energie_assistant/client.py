from __future__ import annotations

from typing import Any

import asyncio
from aiohttp import ClientSession

from homeassistant.exceptions import HomeAssistantError

from .const import DEFAULT_API_PATH

READ_ONLY_RESPONSE_PATH = "/api/assistant/respond"


class EnergieAssistantClient:
    def __init__(self, session: ClientSession, *, host: str, port: int, ssl: bool = False, api_path: str = READ_ONLY_RESPONSE_PATH) -> None:
        scheme = "https" if ssl else "http"
        self._session = session
        self._url = f"{scheme}://{host}:{int(port)}{api_path or READ_ONLY_RESPONSE_PATH}"

    async def async_respond(self, query: str, session_id: str | None) -> dict[str, Any]:
        payload = {"query": query, "session_id": session_id}
        try:
            async with asyncio.timeout(5):
                response = await self._session.post(self._url, json=payload)
                if response.status != 200:
                    raise HomeAssistantError(f"Energie Assistant HTTP {response.status}")
                data = await response.json()
        except HomeAssistantError:
            raise
        except Exception as exc:
            raise HomeAssistantError(f"Energie Assistant niet bereikbaar: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("speech"), str):
            raise HomeAssistantError("Energie Assistant gaf geen geldige response")
        return data
