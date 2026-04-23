"""Select platform for Samsung Soundbar.

Provides standalone select entities for:
  - Sound mode
  - EQ preset
  - Input source

These complement the media_player's built-in sound_mode / source selectors
for users who want them as separate entities in dashboards or automations.
"""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    HREF_EQ,
    HREF_SOUNDMODE,
    OPT_ENABLE_EQ,
    OPT_ENABLE_SOUNDMODE,
    PROP_EQ_NAME,
    PROP_SOUNDMODE,
)
from .coordinator import SoundbarCoordinator, SoundbarState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    entities: list[SelectEntity] = []

    # Input source is always available
    entities.append(InputSourceSelect(coordinator, device_id))

    if coordinator.options.get(OPT_ENABLE_SOUNDMODE, True):
        entities.append(SoundModeSelect(coordinator, device_id))

    if coordinator.options.get(OPT_ENABLE_EQ, False):
        entities.append(EqPresetSelect(coordinator, device_id))

    async_add_entities(entities, update_before_add=False)


class _SoundbarSelect(CoordinatorEntity[SoundbarCoordinator], SelectEntity):
    """Base class for soundbar select entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SoundbarCoordinator,
        device_id: str,
        key: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_name = name
        self._attr_icon = icon

    @property
    def device_info(self) -> DeviceInfo:
        data: SoundbarState = self.coordinator.data
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self.coordinator.device_name,
            manufacturer=data.manufacturer if data else "Samsung",
            model=data.model if data else "",
            sw_version=data.firmware_version if data else "",
        )


class SoundModeSelect(_SoundbarSelect):
    """Select entity for sound mode."""

    def __init__(self, coordinator: SoundbarCoordinator, device_id: str) -> None:
        super().__init__(
            coordinator, device_id, "sound_mode_select", "Sound Mode", "mdi:surround-sound"
        )

    @property
    def options(self) -> list[str]:
        data = self.coordinator.data
        return data.supported_sound_modes if data else []

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        return data.sound_mode if data else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.send_execute_command(
            self._device_id, HREF_SOUNDMODE, {PROP_SOUNDMODE: option}
        )
        # Optimistic update via coordinator so all listeners are notified
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, sound_mode=option)
            )


class EqPresetSelect(_SoundbarSelect):
    """Select entity for EQ preset."""

    def __init__(self, coordinator: SoundbarCoordinator, device_id: str) -> None:
        super().__init__(
            coordinator, device_id, "eq_preset_select", "EQ Preset", "mdi:tune-vertical"
        )

    @property
    def options(self) -> list[str]:
        data = self.coordinator.data
        return data.supported_eq_presets if data else []

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        return data.eq_preset if data else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.send_execute_command(
            self._device_id, HREF_EQ, {PROP_EQ_NAME: option}
        )
        # Optimistic update via coordinator so all listeners are notified
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, eq_preset=option)
            )


class InputSourceSelect(_SoundbarSelect):
    """Select entity for input source."""

    def __init__(self, coordinator: SoundbarCoordinator, device_id: str) -> None:
        super().__init__(
            coordinator, device_id, "input_source_select", "Input Source", "mdi:video-input-hdmi"
        )

    @property
    def options(self) -> list[str]:
        data = self.coordinator.data
        return data.supported_input_sources if data else []

    @property
    def current_option(self) -> str | None:
        data = self.coordinator.data
        return data.input_source if data else None

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "samsungvd.audioInputSource", "setInputSource", [option]
        )
        # Optimistic update via coordinator so all listeners are notified
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, input_source=option)
            )
