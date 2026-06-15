"""Button platform for Samsung Soundbar.

Exposes one-shot actions as button entities:
  - SpaceFit Sound calibration
"""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    HREF_SPACEFIT_SOUND,
    OPT_ENABLE_ADVANCED_AUDIO,
)
from .coordinator import SoundbarCoordinator, SoundbarState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Only show calibration buttons when advanced audio features are enabled
    if not coordinator.options.get(OPT_ENABLE_ADVANCED_AUDIO, True):
        return

    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities(
        [SpaceFitCalibrationButton(coordinator, device_id)],
        update_before_add=False,
    )


class SpaceFitCalibrationButton(
    CoordinatorEntity[SoundbarCoordinator], ButtonEntity
):
    """Button entity that triggers SpaceFit Sound calibration.

    SpaceFit Sound analyzes the room acoustics and adjusts the
    soundbar's audio profile accordingly. The calibration takes
    approximately 10 seconds and uses test tones emitted from all
    speakers.

    This is different from the SpaceFit Sound *toggle* (in switch.py)
    which enables/disables the feature. This button triggers the
    actual room calibration process.
    """

    _attr_has_entity_name = True
    _attr_name = "SpaceFit Calibration"
    _attr_icon = "mdi:tune"

    def __init__(
        self,
        coordinator: SoundbarCoordinator,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_spacefit_calibration"

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

    async def async_press(self) -> None:
        """Trigger the SpaceFit Sound room calibration.

        Sends the OCF execute command to start calibration. The
        soundbar will emit test tones from all speakers and analyze
        the room acoustics. Takes approximately 10 seconds.
        """
        _LOGGER.info("Starting SpaceFit Sound calibration")
        await self.coordinator.client.send_execute_command(
            self._device_id,
            HREF_SPACEFIT_SOUND,
            {"x.com.samsung.networkaudio.spacefitSound": "startSpacefit"},
        )
