"""Number platform for Samsung Soundbar.

Exposes the subwoofer level as a number entity (-6 to +6, 1 dB steps).
"""

from __future__ import annotations

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    HREF_WOOFER,
    OPT_ENABLE_WOOFER,
    PROP_WOOFER,
)
from .coordinator import SoundbarCoordinator, SoundbarState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.options.get(OPT_ENABLE_WOOFER, True):
        return

    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities(
        [WooferLevelNumber(coordinator, device_id)],
        update_before_add=False,
    )


class WooferLevelNumber(CoordinatorEntity[SoundbarCoordinator], NumberEntity):
    """Number entity for subwoofer level adjustment."""

    _attr_has_entity_name = True
    _attr_name = "Woofer Level"
    _attr_icon = "mdi:speaker"
    _attr_native_min_value = -6
    _attr_native_max_value = 6
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "dB"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self,
        coordinator: SoundbarCoordinator,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_woofer_level"

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

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        return data.woofer_level if data else None

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.client.send_execute_command(
            self._device_id,
            HREF_WOOFER,
            {PROP_WOOFER: int(value)},
        )
        await self.coordinator.async_request_refresh()
