"""Switch platform for Samsung Soundbar.

Exposes advanced audio toggles as switches:
  - Night Mode
  - Voice Amplifier
  - Bass Boost
  - Active Voice Amplifier
  - Space Fit Sound
"""

from __future__ import annotations

from dataclasses import dataclass, replace
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
    OPT_ENABLE_HOMEKIT_COMPAT,
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
    # Whether the coordinator reads this feature's state back from the
    # device. For features with no readback we keep the optimistic state
    # sticky so the toggle doesn't snap back to "off" on the next poll.
    has_readback: bool = True


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
        state_fn=lambda _: False,  # no readback — optimistic state only
        href=HREF_ACTIVE_VOICE_AMP,
        prop=PROP_ACTIVE_VOICE_AMP,
        has_readback=False,
    ),
    SoundbarSwitchDef(
        key="space_fit_sound",
        name="Space Fit Sound",
        icon="mdi:surround-sound",
        state_fn=lambda _: False,  # no readback — optimistic state only
        href=HREF_SPACEFIT_SOUND,
        prop=PROP_SPACEFIT_SOUND,
        has_readback=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]
    device_id = entry.data[CONF_DEVICE_ID]

    entities: list[SwitchEntity] = []
    if coordinator.options.get(OPT_ENABLE_ADVANCED_AUDIO, True):
        entities.extend(
            SoundbarSwitch(coordinator, device_id, defn)
            for defn in SWITCH_DEFINITIONS
        )
    # Power on/off as a plain switch, for Apple Home (where the media
    # player isn't bridged) and for simple dashboard/automation control.
    if coordinator.options.get(OPT_ENABLE_HOMEKIT_COMPAT, False):
        entities.append(SoundbarPowerSwitch(coordinator, device_id))

    if entities:
        async_add_entities(entities, update_before_add=False)


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
        # Clear optimistic state once the coordinator has fresh readback.
        # Features without readback keep their optimistic state so the
        # toggle doesn't revert to "off" on the next poll.
        if self._defn.has_readback:
            self._optimistic_state = None
        super()._handle_coordinator_update()


class SoundbarPowerSwitch(CoordinatorEntity[SoundbarCoordinator], SwitchEntity):
    """Soundbar power on/off as a standalone switch.

    The power state is read back from the device's switch capability, so
    no optimistic-state stickiness is needed.
    """

    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:power"

    def __init__(
        self,
        coordinator: SoundbarCoordinator,
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_power"

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
        data = self.coordinator.data
        return bool(data and data.power)

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self.coordinator.client.send_switch_command(self._device_id, True)
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, power=True)
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.coordinator.client.send_switch_command(self._device_id, False)
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, power=False)
            )
