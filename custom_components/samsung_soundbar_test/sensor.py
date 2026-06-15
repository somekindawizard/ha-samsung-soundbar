"""Sensor platform for Samsung Soundbar.

Exposes the raw volume level as a sensor entity (useful for automations
that trigger on volume thresholds).
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DEVICE_ID, DOMAIN
from .coordinator import SoundbarCoordinator, SoundbarState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities(
        [VolumeSensor(coordinator, device_id)],
        update_before_add=False,
    )


class VolumeSensor(CoordinatorEntity[SoundbarCoordinator], SensorEntity):
    """Sensor showing the current raw volume level."""

    _attr_has_entity_name = True
    _attr_name = "Volume"
    _attr_icon = "mdi:volume-high"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "%"

    def __init__(
        self,
        coordinator: SoundbarCoordinator,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_volume_sensor"

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
    def native_value(self) -> int | None:
        data = self.coordinator.data
        return data.volume if data else None
