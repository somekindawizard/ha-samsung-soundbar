"""Samsung Soundbar integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import SmartThingsClient, TokenData
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_MAX_VOLUME,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DOMAIN,
    HREF_CHANNEL_VOLUME,
    HREF_SURROUND_SPEAKER,
    OPT_ENABLE_ADVANCED_AUDIO,
    OPT_ENABLE_EQ,
    OPT_ENABLE_SOUNDMODE,
    OPT_ENABLE_WOOFER,
    PROP_CHANNEL_VOLUME,
    PROP_REAR_POSITION,
    SpeakerChannel,
    RearSpeakerMode,
)
from .coordinator import SoundbarCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["media_player", "switch", "select", "number", "sensor"]

# Service call schemas
SERVICE_SET_SPEAKER_LEVEL = "set_speaker_level"
SERVICE_SET_REAR_SPEAKER_MODE = "set_rear_speaker_mode"

SCHEMA_SET_SPEAKER_LEVEL = vol.Schema(
    {
        vol.Required("speaker_channel"): vol.In(
            [e.value for e in SpeakerChannel]
        ),
        vol.Required("level"): vol.All(int, vol.Range(min=-6, max=6)),
    }
)

SCHEMA_SET_REAR_SPEAKER_MODE = vol.Schema(
    {
        vol.Required("mode"): vol.In([e.value for e in RearSpeakerMode]),
    }
)


def _get_coordinator_for_device(
    hass: HomeAssistant, call: ServiceCall
) -> SoundbarCoordinator | None:
    """Resolve the coordinator from a service call's device target."""
    device_ids = call.data.get("device_id", [])
    if not device_ids:
        # Fall back to first configured coordinator
        coordinators = hass.data.get(DOMAIN, {})
        if coordinators:
            return next(iter(coordinators.values()))
        return None

    dev_reg = dr.async_get(hass)
    for device_id in device_ids:
        device_entry = dev_reg.async_get(device_id)
        if not device_entry:
            continue
        for identifier in device_entry.identifiers:
            if identifier[0] == DOMAIN:
                # identifier[1] is the SmartThings device_id
                for coordinator in hass.data.get(DOMAIN, {}).values():
                    if coordinator.device_id == identifier[1]:
                        return coordinator
    return None


async def _async_setup_services(hass: HomeAssistant) -> None:
    """Register integration-level services."""

    async def handle_set_speaker_level(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_device(hass, call)
        if not coordinator:
            _LOGGER.error("No soundbar device found for service call")
            return
        channel = call.data["speaker_channel"]
        level = call.data["level"]
        await coordinator.client.send_execute_command(
            coordinator.device_id,
            HREF_CHANNEL_VOLUME,
            {PROP_CHANNEL_VOLUME: [{"name": channel, "value": level}]},
        )
        _LOGGER.info("Set %s level to %d", channel, level)

    async def handle_set_rear_speaker_mode(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_device(hass, call)
        if not coordinator:
            _LOGGER.error("No soundbar device found for service call")
            return
        mode = call.data["mode"]
        await coordinator.client.send_execute_command(
            coordinator.device_id,
            HREF_SURROUND_SPEAKER,
            {PROP_REAR_POSITION: mode},
        )
        _LOGGER.info("Set rear speaker mode to %s", mode)

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_SPEAKER_LEVEL,
        handle_set_speaker_level,
        schema=SCHEMA_SET_SPEAKER_LEVEL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_REAR_SPEAKER_MODE,
        handle_set_rear_speaker_mode,
        schema=SCHEMA_SET_REAR_SPEAKER_MODE,
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Samsung Soundbar from a config entry."""
    session = async_get_clientsession(hass)

    token_data = TokenData(
        access_token=entry.data[CONF_ACCESS_TOKEN],
        refresh_token=entry.data[CONF_REFRESH_TOKEN],
        expires_at=entry.data.get(CONF_TOKEN_EXPIRES_AT, 0),
    )

    client = SmartThingsClient(
        session=session,
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        token_data=token_data,
    )

    options = {
        OPT_ENABLE_SOUNDMODE: entry.options.get(OPT_ENABLE_SOUNDMODE, True),
        OPT_ENABLE_ADVANCED_AUDIO: entry.options.get(OPT_ENABLE_ADVANCED_AUDIO, True),
        OPT_ENABLE_WOOFER: entry.options.get(OPT_ENABLE_WOOFER, True),
        OPT_ENABLE_EQ: entry.options.get(OPT_ENABLE_EQ, False),
    }

    coordinator = SoundbarCoordinator(
        hass=hass,
        client=client,
        device_id=entry.data[CONF_DEVICE_ID],
        device_name=entry.data.get(CONF_DEVICE_NAME, "Samsung Soundbar"),
        options=options,
    )
    coordinator.config_entry = entry

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Register services once (first entry to load)
    if not hass.services.has_service(DOMAIN, SERVICE_SET_SPEAKER_LEVEL):
        await _async_setup_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            # Remove services when last device is unloaded
            hass.services.async_remove(DOMAIN, SERVICE_SET_SPEAKER_LEVEL)
            hass.services.async_remove(DOMAIN, SERVICE_SET_REAR_SPEAKER_MODE)
    return unload_ok
