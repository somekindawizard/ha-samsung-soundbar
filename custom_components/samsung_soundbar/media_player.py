"""Media player platform for Samsung Soundbar."""

from __future__ import annotations

import logging
from dataclasses import replace
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_MAX_VOLUME,
    DOMAIN,
    HREF_SOUNDMODE,
    PROP_SOUNDMODE,
)
from .coordinator import SoundbarCoordinator, SoundbarState

_LOGGER = logging.getLogger(__name__)

# Fallback sound modes shown in the UI before the first OCF poll completes.
_DEFAULT_SOUND_MODES = [
    "adaptive sound",
    "standard",
    "surround",
    "game",
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SoundbarCoordinator = hass.data[DOMAIN][entry.entry_id]
    max_volume = entry.data.get(CONF_MAX_VOLUME, 100)
    async_add_entities(
        [SoundbarMediaPlayer(coordinator, entry, max_volume)],
        update_before_add=False,
    )


class SoundbarMediaPlayer(CoordinatorEntity[SoundbarCoordinator], MediaPlayerEntity):
    """Representation of the soundbar as a media player."""

    _attr_has_entity_name = True
    _attr_name = None  # Use device name directly
    _attr_device_class = MediaPlayerDeviceClass.SPEAKER
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.SELECT_SOUND_MODE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(
        self,
        coordinator: SoundbarCoordinator,
        entry: ConfigEntry,
        max_volume: int,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = entry.data[CONF_DEVICE_ID]
        self._max_volume = max_volume
        self._attr_unique_id = f"{self._device_id}_media_player"

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
    def _state(self) -> SoundbarState:
        return self.coordinator.data

    # ── Power ────────────────────────────────────────────────────────

    @property
    def state(self) -> MediaPlayerState:
        if not self._state or not self._state.power:
            return MediaPlayerState.OFF
        if self._state.playback_status == "playing":
            return MediaPlayerState.PLAYING
        if self._state.playback_status == "paused":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.ON

    async def async_turn_on(self) -> None:
        await self.coordinator.client.send_switch_command(self._device_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self.coordinator.client.send_switch_command(self._device_id, False)
        await self.coordinator.async_request_refresh()

    # ── Volume ───────────────────────────────────────────────────────

    @property
    def volume_level(self) -> float | None:
        if not self._state:
            return None
        vol = self._state.volume
        if vol > self._max_volume:
            return 1.0
        return vol / self._max_volume

    @property
    def is_volume_muted(self) -> bool | None:
        return self._state.muted if self._state else None

    async def async_set_volume_level(self, volume: float) -> None:
        target = int(volume * self._max_volume)
        await self.coordinator.client.send_standard_command(
            self._device_id, "audioVolume", "setVolume", [target]
        )
        # Optimistic update
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, volume=target)
            )

    async def async_volume_up(self) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "audioVolume", "volumeUp"
        )
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "audioVolume", "volumeDown"
        )
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        cmd = "mute" if mute else "unmute"
        await self.coordinator.client.send_standard_command(
            self._device_id, "audioMute", cmd
        )
        # Optimistic update
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, muted=mute)
            )

    # ── Input source ─────────────────────────────────────────────────

    @property
    def source(self) -> str | None:
        return self._state.input_source if self._state else None

    @property
    def source_list(self) -> list[str] | None:
        return self._state.supported_input_sources if self._state else None

    async def async_select_source(self, source: str) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "samsungvd.audioInputSource", "setInputSource", [source]
        )
        # Optimistic update
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, input_source=source)
            )

    # ── Sound mode ───────────────────────────────────────────────────

    @property
    def sound_mode(self) -> str | None:
        return self._state.sound_mode if self._state else None

    @property
    def sound_mode_list(self) -> list[str] | None:
        if not self._state:
            return _DEFAULT_SOUND_MODES
        return self._state.supported_sound_modes or _DEFAULT_SOUND_MODES

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        await self.coordinator.client.send_execute_command(
            self._device_id, HREF_SOUNDMODE, {PROP_SOUNDMODE: sound_mode}
        )
        # Optimistic update via coordinator so all listeners are notified
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, sound_mode=sound_mode)
            )

    # ── Media info ───────────────────────────────────────────────────

    @property
    def media_title(self) -> str | None:
        return self._state.media_title if self._state else None

    @property
    def media_artist(self) -> str | None:
        return self._state.media_artist if self._state else None

    # ── Media transport ──────────────────────────────────────────────

    async def async_media_play(self) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "mediaPlayback", "play"
        )
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, playback_status="playing")
            )

    async def async_media_pause(self) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "mediaPlayback", "pause"
        )
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, playback_status="paused")
            )

    async def async_media_stop(self) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "mediaPlayback", "stop"
        )
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, playback_status="stopped")
            )

    async def async_media_next_track(self) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "mediaPlayback", "fastForward"
        )
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        await self.coordinator.client.send_standard_command(
            self._device_id, "mediaPlayback", "rewind"
        )
        await self.coordinator.async_request_refresh()
