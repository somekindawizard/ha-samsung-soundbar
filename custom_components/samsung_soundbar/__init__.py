"""Samsung Soundbar integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
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
    OPT_ENABLE_ADVANCED_AUDIO,
    OPT_ENABLE_EQ,
    OPT_ENABLE_SOUNDMODE,
    OPT_ENABLE_WOOFER,
)
from .coordinator import SoundbarCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["media_player", "switch", "select", "number", "sensor"]


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

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload_ok
