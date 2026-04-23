"""Device triggers for Samsung Soundbar.

Allows users to create automations in the HA UI that trigger when
soundbar state changes occur, without needing to know entity IDs.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_DOMAIN,
    CONF_ENTITY_ID,
    CONF_PLATFORM,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

# Trigger types that map to entity state changes
TRIGGER_TYPES = {
    "sound_mode_changed",
    "playback_started",
    "playback_paused",
    "playback_stopped",
    "night_mode_on",
    "night_mode_off",
    "input_source_changed",
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)

# Map trigger types to the entity suffix and state values
_TRIGGER_MAP: dict[str, tuple[str, str | None, str | None]] = {
    # (entity_suffix, from_state, to_state)
    "playback_started": ("media_player", None, "playing"),
    "playback_paused": ("media_player", None, "paused"),
    "playback_stopped": ("media_player", None, "off"),
    "night_mode_on": ("night_mode", None, "on"),
    "night_mode_off": ("night_mode", None, "off"),
}


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Return a list of triggers for this device."""
    triggers: list[dict[str, Any]] = []

    for trigger_type in TRIGGER_TYPES:
        triggers.append(
            {
                CONF_PLATFORM: "device",
                CONF_DEVICE_ID: device_id,
                CONF_DOMAIN: DOMAIN,
                CONF_TYPE: trigger_type,
            }
        )

    return triggers


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger to fire when the soundbar state changes."""
    trigger_type = config[CONF_TYPE]
    device_id = config[CONF_DEVICE_ID]

    # Find the relevant entity for this trigger type
    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    device_entry = dev_reg.async_get(device_id)
    if not device_entry:
        raise ValueError(f"Device {device_id} not found")

    # Get all entities for this device
    entries = er.async_entries_for_device(ent_reg, device_id)

    if trigger_type in _TRIGGER_MAP:
        suffix, from_state, to_state = _TRIGGER_MAP[trigger_type]
        entity_id = _find_entity(entries, suffix)
        if not entity_id:
            raise ValueError(
                f"No matching entity found for trigger {trigger_type}"
            )

        state_config = {
            CONF_PLATFORM: "state",
            CONF_ENTITY_ID: entity_id,
        }
        if from_state is not None:
            state_config["from"] = from_state
        if to_state is not None:
            state_config["to"] = to_state

        return await state_trigger.async_attach_trigger(
            hass, state_config, action, trigger_info, platform_type="device"
        )

    # For sound_mode_changed and input_source_changed, trigger on any
    # change to the corresponding select entity
    if trigger_type == "sound_mode_changed":
        entity_id = _find_entity(entries, "sound_mode_select")
        if not entity_id:
            raise ValueError("Sound mode select entity not found")
        return await state_trigger.async_attach_trigger(
            hass,
            {CONF_PLATFORM: "state", CONF_ENTITY_ID: entity_id},
            action,
            trigger_info,
            platform_type="device",
        )

    if trigger_type == "input_source_changed":
        entity_id = _find_entity(entries, "input_source_select")
        if not entity_id:
            raise ValueError("Input source select entity not found")
        return await state_trigger.async_attach_trigger(
            hass,
            {CONF_PLATFORM: "state", CONF_ENTITY_ID: entity_id},
            action,
            trigger_info,
            platform_type="device",
        )

    raise ValueError(f"Unknown trigger type: {trigger_type}")


def _find_entity(
    entries: list[er.RegistryEntry], suffix: str
) -> str | None:
    """Find an entity ID by matching its unique_id suffix."""
    for entry in entries:
        if entry.unique_id and entry.unique_id.endswith(f"_{suffix}"):
            return entry.entity_id
    return None
