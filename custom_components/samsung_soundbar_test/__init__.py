"""Samsung Soundbar integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
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
    HREF_ADVANCED_AUDIO,
    HREF_CHANNEL_VOLUME,
    HREF_EQ,
    HREF_SOUNDMODE,
    HREF_SURROUND_SPEAKER,
    HREF_WOOFER,
    OPT_ENABLE_ADVANCED_AUDIO,
    OPT_ENABLE_EQ,
    OPT_ENABLE_SOUNDMODE,
    OPT_ENABLE_WOOFER,
    PROP_CHANNEL_VOLUME,
    PROP_EQ_NAME,
    PROP_NIGHTMODE,
    PROP_REAR_POSITION,
    PROP_SOUNDMODE,
    PROP_WOOFER,
    SpeakerChannel,
    RearSpeakerMode,
)
from .coordinator import SoundbarCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.MEDIA_PLAYER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BUTTON,
]

SERVICE_SET_SPEAKER_LEVEL = "set_speaker_level"
SERVICE_SET_REAR_SPEAKER_MODE = "set_rear_speaker_mode"
SERVICE_APPLY_PRESET = "apply_preset"

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

SCHEMA_APPLY_PRESET = vol.Schema(
    {
        vol.Optional("sound_mode"): str,
        vol.Optional("eq_preset"): str,
        vol.Optional("night_mode"): bool,
        vol.Optional("woofer_level"): vol.All(int, vol.Range(min=-6, max=6)),
    }
)


def _get_coordinator_for_device(
    hass: HomeAssistant, call: ServiceCall
) -> SoundbarCoordinator | None:
    device_ids = call.data.get("device_id", [])
    if not device_ids:
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
                for coordinator in hass.data.get(DOMAIN, {}).values():
                    if coordinator.device_id == identifier[1]:
                        return coordinator
    return None


async def _async_setup_services(hass: HomeAssistant) -> None:
    async def handle_set_speaker_level(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_device(hass, call)
        if not coordinator:
            raise HomeAssistantError(
                "No soundbar device found for service call"
            )
        channel = call.data["speaker_channel"]
        level = call.data["level"]
        await coordinator.client.send_execute_command(
            coordinator.device_id,
            HREF_CHANNEL_VOLUME,
            {PROP_CHANNEL_VOLUME: [{"name": channel, "value": level}]},
        )
        _LOGGER.info("Set %s level to %d", channel, level)
        await coordinator.async_request_refresh()

    async def handle_set_rear_speaker_mode(call: ServiceCall) -> None:
        coordinator = _get_coordinator_for_device(hass, call)
        if not coordinator:
            raise HomeAssistantError(
                "No soundbar device found for service call"
            )
        mode = call.data["mode"]
        await coordinator.client.send_execute_command(
            coordinator.device_id,
            HREF_SURROUND_SPEAKER,
            {PROP_REAR_POSITION: mode},
        )
        _LOGGER.info("Set rear speaker mode to %s", mode)
        await coordinator.async_request_refresh()

    async def handle_apply_preset(call: ServiceCall) -> None:
        """Apply a sound preset atomically.

        Sets any combination of sound_mode, eq_preset, night_mode, and
        woofer_level in a single service call. Only fields that are
        provided in the call data will be changed.
        """
        coordinator = _get_coordinator_for_device(hass, call)
        if not coordinator:
            raise HomeAssistantError(
                "No soundbar device found for service call"
            )

        device_id = coordinator.device_id
        client = coordinator.client

        sound_mode = call.data.get("sound_mode")
        eq_preset = call.data.get("eq_preset")
        night_mode = call.data.get("night_mode")
        woofer_level = call.data.get("woofer_level")

        if sound_mode is not None:
            await client.send_execute_command(
                device_id, HREF_SOUNDMODE, {PROP_SOUNDMODE: sound_mode}
            )
            _LOGGER.debug("Preset: sound_mode=%s", sound_mode)

        if eq_preset is not None:
            await client.send_execute_command(
                device_id, HREF_EQ, {PROP_EQ_NAME: eq_preset}
            )
            _LOGGER.debug("Preset: eq_preset=%s", eq_preset)

        if night_mode is not None:
            await client.send_execute_command(
                device_id,
                HREF_ADVANCED_AUDIO,
                {PROP_NIGHTMODE: 1 if night_mode else 0},
            )
            _LOGGER.debug("Preset: night_mode=%s", night_mode)

        if woofer_level is not None:
            await client.send_execute_command(
                device_id, HREF_WOOFER, {PROP_WOOFER: woofer_level}
            )
            _LOGGER.debug("Preset: woofer_level=%d", woofer_level)

        _LOGGER.info(
            "Applied preset: sound_mode=%s, eq=%s, night=%s, woofer=%s",
            sound_mode, eq_preset, night_mode, woofer_level,
        )
        await coordinator.async_request_refresh()

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
    hass.services.async_register(
        DOMAIN,
        SERVICE_APPLY_PRESET,
        handle_apply_preset,
        schema=SCHEMA_APPLY_PRESET,
    )


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
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

    if not hass.services.has_service(DOMAIN, SERVICE_SET_SPEAKER_LEVEL):
        await _async_setup_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
            hass.services.async_remove(DOMAIN, SERVICE_SET_SPEAKER_LEVEL)
            hass.services.async_remove(DOMAIN, SERVICE_SET_REAR_SPEAKER_MODE)
            hass.services.async_remove(DOMAIN, SERVICE_APPLY_PRESET)
    return unload_ok
