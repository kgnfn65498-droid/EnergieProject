from __future__ import annotations

from typing import Literal

from homeassistant.components import conversation
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import intent

from .const import DOMAIN

PRIVACY_DISABLED_TEXT = "Energie Assistant staat uit via de privacy-schakelaar."


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    async_add_entities([EnergieAssistantConversation(entry)])


class EnergieAssistantConversation(conversation.ConversationEntity):
    _attr_has_entity_name = True
    _attr_name = "Energie Assistant"
    _attr_supported_features = conversation.ConversationEntityFeature(0)

    def __init__(self, entry: ConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_conversation"

    @property
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    async def _async_handle_message(self, user_input: conversation.ConversationInput, chat_log: conversation.ChatLog) -> conversation.ConversationResult:
        runtime = self.hass.data[DOMAIN][self.entry.entry_id]
        privacy_enabled = bool(runtime.privacy_enabled)
        privacy_disabled = not privacy_enabled
        if privacy_disabled:
            speech = PRIVACY_DISABLED_TEXT
        else:
            data = await runtime.client.async_respond(user_input.text, chat_log.conversation_id)
            speech = str(data["speech"])

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=self.entity_id, content=speech)
        )
        return conversation.async_get_result_from_chat_log(user_input, chat_log)
