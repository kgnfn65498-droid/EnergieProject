from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities([EnergieAssistantPrivacySwitch(entry)])


class EnergieAssistantPrivacySwitch(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = "Energie Assistant toegestaan"
    _attr_icon = "mdi:account-voice"

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_privacy"
        self._is_on = False

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._is_on = last_state.state == STATE_ON
        self._sync_runtime()

    def _sync_runtime(self) -> None:
        runtime = self.hass.data[DOMAIN][self._entry.entry_id]
        runtime.privacy_enabled = self._is_on

    async def async_turn_on(self, **kwargs) -> None:
        self._is_on = True
        self._sync_runtime()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._is_on = False
        self._sync_runtime()
        self.async_write_ha_state()
