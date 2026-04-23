"""Diagnostics support for Samsung Soundbar.

Exports redacted configuration and the last coordinator state snapshot
for debugging. Required for HA Silver quality scale.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SoundbarCoordinator

# Keys that contain sensitive data and must be redacted in diagnostics.
TO_REDACT_CONFIG = {
    "access_token",
    "refresh_token",
    "client_id",
    "client_secret",
    "token_expires_at",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Build the state snapshot, handling the case where the coordinator
    # hasn't completed its first poll yet.
    state_data: dict[str, Any] = {}
    if coordinator.data:
        state_data = asdict(coordinator.data)
        # Media info is not sensitive but can be large; keep it.
        # No fields in SoundbarState are sensitive.

    diagnostics: dict[str, Any] = {
        "config_entry": {
            "entry_id": entry.entry_id,
            "version": entry.version,
            "domain": entry.domain,
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT_CONFIG),
            "options": dict(entry.options),
        },
        "coordinator": {
            "device_id": coordinator.device_id,
            "device_name": coordinator.device_name,
            "options": coordinator.options,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "last_update_success": coordinator.last_update_success,
        },
        "state": state_data,
        "token_status": {
            "has_access_token": bool(coordinator.client.access_token),
            "has_refresh_token": bool(coordinator.client.refresh_token),
            "token_expires_at": coordinator.client.token_expires_at,
            "token_needs_refresh": coordinator.client.token_needs_refresh(),
        },
    }

    return diagnostics
