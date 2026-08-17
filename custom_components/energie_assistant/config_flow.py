from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.hassio import HassioServiceInfo

from .const import CONF_API_PATH, CONF_SSL, DEFAULT_API_PATH, DEFAULT_PORT, DOMAIN


class EnergieAssistantConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovered: dict[str, Any] | None = None

    async def async_step_hassio(self, discovery_info: HassioServiceInfo):
        config = dict(discovery_info.config)
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured(
            updates={
                CONF_HOST: config["host"],
                CONF_PORT: int(config.get("port", DEFAULT_PORT)),
                CONF_SSL: bool(config.get("ssl", False)),
                CONF_API_PATH: str(config.get("api_path", DEFAULT_API_PATH)),
            }
        )
        self._discovered = config
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(self, user_input: dict[str, Any] | None = None):
        assert self._discovered is not None
        if user_input is not None:
            data = {
                CONF_HOST: str(self._discovered["host"]),
                CONF_PORT: int(self._discovered.get("port", DEFAULT_PORT)),
                CONF_SSL: bool(self._discovered.get("ssl", False)),
                CONF_API_PATH: str(self._discovered.get("api_path", DEFAULT_API_PATH)),
            }
            return self.async_create_entry(title="Energie Assistant", data=data)
        self._set_confirm_only()
        return self.async_show_form(step_id="discovery_confirm")

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Energie Assistant",
                data={
                    CONF_HOST: str(user_input["host"]),
                    CONF_PORT: int(user_input["port"]),
                    CONF_SSL: False,
                    CONF_API_PATH: DEFAULT_API_PATH,
                },
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("host"): str,
                vol.Required("port", default=DEFAULT_PORT): int,
            }),
        )
