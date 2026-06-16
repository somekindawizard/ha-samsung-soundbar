"""Fan platform for Samsung Soundbar (Apple Home compatibility).

These entities only exist when the "Apple Home compatibility" option is
enabled. HomeKit has no native control for an arbitrary audio level, so a
Fan service (its 0-100 % speed slider) is the standard way to surface
volume and subwoofer level as draggable tiles in the Apple Home app.

  - Volume:    0-100 % maps to the soundbar volume (0..max_volume).
  - Subwoofer: 0-100 % maps to the subwoofer level (-6..+6 dB), so 0 %
               is the minimum (-6 dB), 50 % is neutral (0 dB), 100 % is
               +6 dB. There is no real "off" for the woofer; turning the
               fan off just sets it to the minimum.

Fans (not lightbulbs) are used deliberately so Apple Home light scenes,
"turn off the lights", and Adaptive Lighting never grab these controls.
"""

from __future__ import annotations

from dataclasses import replace

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_MAX_VOLUME,
    DOMAIN,
    HREF_WOOFER,
    OPT_ENABLE_HOMEKIT_COMPAT,
    OPT_ENABLE_WOOFER,
    PROP_WOOFER,
)
from .coordinator import SoundbarCoordinator, SoundbarState

# Subwoofer hardware range, in dB.
WOOFER_MIN = -6
WOOFER_MAX = 6
WOOFER_SPAN = WOOFER_MAX - WOOFER_MIN  # 12 discrete steps


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Only create these helper fans in Apple Home compatibility mode.
    if not coordinator.options.get(OPT_ENABLE_HOMEKIT_COMPAT, False):
        return

    device_id = entry.data[CONF_DEVICE_ID]
    max_volume = entry.data.get(CONF_MAX_VOLUME, 100)
    entities: list[FanEntity] = [VolumeFan(coordinator, device_id, max_volume)]
    if coordinator.options.get(OPT_ENABLE_WOOFER, True):
        entities.append(SubwooferFan(coordinator, device_id))

    async_add_entities(entities, update_before_add=False)


class _SoundbarFan(CoordinatorEntity[SoundbarCoordinator], FanEntity):
    """Base class wiring up device info for the helper fans."""

    _attr_has_entity_name = True
    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.TURN_ON
        | FanEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator: SoundbarCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

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


class VolumeFan(_SoundbarFan):
    """Soundbar volume surfaced as a fan speed slider for Apple Home."""

    _attr_name = "Volume (Home)"
    _attr_icon = "mdi:volume-high"

    def __init__(
        self, coordinator: SoundbarCoordinator, device_id: str, max_volume: int
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_volume_fan"
        self._max_volume = max_volume or 100

    @property
    def percentage(self) -> int | None:
        data = self.coordinator.data
        if not data or not self._max_volume:
            return None
        return max(0, min(100, round(data.volume / self._max_volume * 100)))

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        return bool(data and data.volume > 0)

    async def async_set_percentage(self, percentage: int) -> None:
        target = round(percentage / 100 * self._max_volume)
        await self.coordinator.client.send_standard_command(
            self._device_id, "audioVolume", "setVolume", [target]
        )
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, volume=target)
            )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        if percentage is None:
            data = self.coordinator.data
            current = data.volume if data else 0
            percentage = (
                round(current / self._max_volume * 100) if current else 20
            )
        await self.async_set_percentage(percentage)

    async def async_turn_off(self, **kwargs) -> None:
        await self.async_set_percentage(0)


class SubwooferFan(_SoundbarFan):
    """Subwoofer level surfaced as a fan speed slider for Apple Home."""

    _attr_name = "Subwoofer (Home)"
    _attr_icon = "mdi:speaker"
    _attr_speed_count = WOOFER_SPAN  # 12 steps -> -6..+6 in 1 dB increments

    def __init__(self, coordinator: SoundbarCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_woofer_fan"

    @property
    def percentage(self) -> int | None:
        data = self.coordinator.data
        if not data:
            return None
        pct = (data.woofer_level - WOOFER_MIN) / WOOFER_SPAN * 100
        return max(0, min(100, round(pct)))

    @property
    def is_on(self) -> bool:
        data = self.coordinator.data
        return bool(data and data.woofer_level > WOOFER_MIN)

    async def async_set_percentage(self, percentage: int) -> None:
        level = round(percentage / 100 * WOOFER_SPAN) + WOOFER_MIN
        level = max(WOOFER_MIN, min(WOOFER_MAX, level))
        await self.coordinator.client.send_execute_command(
            self._device_id, HREF_WOOFER, {PROP_WOOFER: level}
        )
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, woofer_level=level)
            )

    async def async_turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs,
    ) -> None:
        # Default to neutral (0 dB = 50 %) when toggled on without a level.
        await self.async_set_percentage(percentage if percentage is not None else 50)

    async def async_turn_off(self, **kwargs) -> None:
        await self.async_set_percentage(0)
