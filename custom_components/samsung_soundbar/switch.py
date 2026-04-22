"""Switch platform for Samsung Soundbar.

Exposes advanced audio toggles as switches:
  - Night Mode
  - Voice Amplifier
  - Bass Boost
  - Active Voice Amplifier
  - Space Fit Sound
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    DOMAIN,
    HREF_ADVANCED_AUDIO,
    HREF_ACTIVE_VOICE_AMP,
    HREF_SPACEFIT_SOUND,
    OPT_ENABLE_ADVANCED_AUDIO,
    PROP_BASS_BOOST,
    PROP_NIGHTMODE,
    PROP_VOICE_AMP,
    PROP_ACTIVE_VOICE_AMP,
    PROP_SPACEFIT_SOUND,
)
from .coordinator import SoundbarCoordinator, SoundbarState


@dataclass(frozen=True)
class SoundbarSwitchDef:
    """Definition for a soundbar switch entity."""

    key: str
    name: str
    icon: str
    state_fn: Callable[[SoundbarState], bool]
    href: str
    prop: str


SWITCH_DEFINITIONS: list[SoundbarSwitchDef] = [
    SoundbarSwitchDef(
        key="night_mode",
        name="Night Mode",
        icon="mdi:weather-night",
        state_fn=lambda s: s.night_mode,
        href=HREF_ADVANCED_AUDIO,
        prop=PROP_NIGHTMODE,
    ),
    SoundbarSwitchDef(
        key="voice_amplifier",
        name="Voice Amplifier",
        icon="mdi:account-voice",
        state_fn=lambda s: s.voice_amplifier,
        href=HREF_ADVANCED_AUDIO,
        prop=PROP_VOICE_AMP,
    ),
    SoundbarSwitchDef(
        key="bass_boost",
        name="Bass Boost",
        icon="mdi:speaker-wireless",
        state_fn=lambda s: s.bass_boost,
        href=HREF_ADVANCED_AUDIO,
        prop=PROP_BASS_BOOST,
    ),
    SoundbarSwitchDef(
        key="active_voice_amplifier",
        name="Active Voice Amplifier",
        icon="mdi:account-voice",
        state_fn=lambda _: False,  # no coordinator state yet — service-only
        href=HREF_ACTIVE_VOICE_AMP,
        prop=PROP_ACTIVE_VOICE_AMP,
    ),
    SoundbarSwitchDef(
        key="space_fit_sound",
        name="Space Fit Sound",
        icon="mdi:surround-sound",
        state_fn=lambda _: False,  # no coordinator state yet — service-only
        href=HREF_SPACEFIT_SOUND,
        prop=PROP_SPACEFIT_SOUND,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]

    if not coordinator.options.get(OPT_ENABLE_ADVANCED_AUDIO, True):
        return

    device_id = entry.data[CONF_DEVICE_ID]
    async_add_entities(
        [
            SoundbarSwitch(coordinator, device_id, defn)
            for defn in SWITCH_DEFINITIONS
        ],
        update_before_add=False,
    )


class SoundbarSwitch(CoordinatorEntity[SoundbarCoordinator], SwitchEntity):
    """A toggle for a soundbar audio feature."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SoundbarCoordinator,
        device_id: str,
        defn: SoundbarSwitchDef,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._defn = defn
        self._attr_unique_id = f"{device_id}_{defn.key}"
        self._attr_name = defn.name
        self._attr_icon = defn.icon
        # Optimistic state for features without coordinator readback
        self._optimistic_state: bool | None = None

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
    def is_on(self) -> bool:
        if self._optimistic_state is not None:
            return self._optimistic_state
        state = self.coordinator.data
        if not state:
            return False
        return self._defn.state_fn(state)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.send_execute_command(
            self._device_id,
            self._defn.href,
            {self._defn.prop: 1},
        )
        self._optimistic_state = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.send_execute_command(
            self._device_id,
            self._defn.href,
            {self._defn.prop: 0},
        )
        self._optimistic_state = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    def _handle_coordinator_update(self) -> None:
        # Clear optimistic state once coordinator has fresh data
        self._optimistic_state = None
        super()._handle_coordinator_update()
