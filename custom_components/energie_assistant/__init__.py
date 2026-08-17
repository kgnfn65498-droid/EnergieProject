from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import EnergieAssistantClient
from .const import CONF_API_PATH, CONF_SSL, DEFAULT_API_PATH, DEFAULT_PORT, DOMAIN


@dataclass
class EnergieAssistantRuntime:
    client: EnergieAssistantClient
    privacy_enabled: bool = False


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime = EnergieAssistantRuntime(
        client=EnergieAssistantClient(
            async_get_clientsession(hass),
            host=str(entry.data[CONF_HOST]),
            port=int(entry.data.get(CONF_PORT, DEFAULT_PORT)),
            ssl=bool(entry.data.get(CONF_SSL, False)),
            api_path=str(entry.data.get(CONF_API_PATH, DEFAULT_API_PATH)),
        )
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.CONVERSATION, Platform.SWITCH])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, [Platform.CONVERSATION, Platform.SWITCH])
    if unloaded:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unloaded
