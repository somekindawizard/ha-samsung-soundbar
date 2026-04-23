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
    MediaType,
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

# Base features always available on the soundbar.
_BASE_FEATURES = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SELECT_SOUND_MODE
    | MediaPlayerEntityFeature.PLAY_MEDIA
)


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
    def supported_features(self) -> MediaPlayerEntityFeature:
        """Dynamically build supported features based on device capabilities.

        The SmartThings API exposes:
          - mediaPlayback.supportedPlaybackCommands: play, pause, stop,
            fastForward, rewind
          - mediaTrackControl.supportedTrackControlCommands: nextTrack,
            previousTrack

        We check the coordinator state to enable only features the
        device actually supports.
        """
        features = _BASE_FEATURES

        data = self.coordinator.data
        if not data:
            return features

        # Media transport controls from mediaPlayback capability
        playback_cmds = data.supported_playback_commands
        if "play" in playback_cmds:
            features |= MediaPlayerEntityFeature.PLAY
        if "pause" in playback_cmds:
            features |= MediaPlayerEntityFeature.PAUSE
        if "stop" in playback_cmds:
            features |= MediaPlayerEntityFeature.STOP

        # Track control from mediaTrackControl capability (NOT fastForward/rewind)
        track_cmds = data.supported_track_control_commands
        if "nextTrack" in track_cmds:
            features |= MediaPlayerEntityFeature.NEXT_TRACK
        if "previousTrack" in track_cmds:
            features |= MediaPlayerEntityFeature.PREVIOUS_TRACK

        return features

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

    # -- Power --------------------------------------------------------

    @property
    def state(self) -> MediaPlayerState:
        if not self._state or not self._state.power:
            return MediaPlayerState.OFF
        if self._state.playback_status == "playing":
            return MediaPlayerState.PLAYING
        if self._state.playback_status == "paused":
            return MediaPlayerState.PAUSED
        if self._state.playback_status == "buffering":
            return MediaPlayerState.BUFFERING
        return MediaPlayerState.ON

    async def async_turn_on(self) -> None:
        await self.coordinator.client.send_switch_command(self._device_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        await self.coordinator.client.send_switch_command(self._device_id, False)
        await self.coordinator.async_request_refresh()

    # -- Volume -------------------------------------------------------

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
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, muted=mute)
            )

    # -- Input source -------------------------------------------------

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
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, input_source=source)
            )

    # -- Sound mode ---------------------------------------------------

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
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(
                replace(self.coordinator.data, sound_mode=sound_mode)
            )
        # OCF write: schedule refresh to confirm the command took effect
        await self.coordinator.async_request_refresh()

    # -- Media info ---------------------------------------------------

    @property
    def media_title(self) -> str | None:
        return self._state.media_title if self._state else None

    @property
    def media_artist(self) -> str | None:
        return self._state.media_artist if self._state else None

    @property
    def media_position(self) -> int | None:
        """Elapsed time in seconds, from audioTrackData."""
        if self._state and self._state.media_elapsed_time is not None:
            return self._state.media_elapsed_time
        return None

    @property
    def media_duration(self) -> int | None:
        """Total time in seconds, from audioTrackData."""
        if self._state and self._state.media_total_time is not None:
            return self._state.media_total_time
        return None

    # -- Play media / TTS ---------------------------------------------

    async def async_play_media(
        self,
        media_type: MediaType | str,
        media_id: str,
        **kwargs: Any,
    ) -> None:
        """Play a media URL or TTS audio on the soundbar.

        Uses the SmartThings audioNotification capability:
          - playTrackAndResume(uri, level): plays then resumes previous track
          - playTrackAndRestore(uri, level): plays then restores volume
          - playTrack(uri, level): fire and forget

        Behavior:
          - If announce=True or media_type is "tts", use playTrackAndRestore
            so the volume returns to normal after the announcement.
          - If media_type is music/url, use playTrackAndResume so the
            previous track resumes after the clip finishes.
          - Otherwise fall back to plain playTrack.
        """
        announce = kwargs.get("announce", False)
        extra = kwargs.get("extra", {}) or {}
        volume = extra.get("volume")

        # Determine which audioNotification command to use
        media_type_str = str(media_type).lower()

        if announce or media_type_str == "tts":
            # Announcement: play and restore volume afterward
            command = "playTrackAndRestore"
        elif media_type_str in ("music", "url", MediaType.MUSIC.value, MediaType.URL.value):
            # Music: play and resume previous track
            command = "playTrackAndResume"
        else:
            # Generic fallback
            command = "playTrack"

        # Build the SmartThings command arguments
        args: list[Any] = [media_id]
        if volume is not None:
            args.append(int(volume))
        elif self._state and self._state.volume:
            # Pass current volume so restore/resume has a reference
            args.append(self._state.volume)

        _LOGGER.debug(
            "Playing media via audioNotification.%s: uri=%s, level=%s",
            command, media_id, args[1] if len(args) > 1 else "default",
        )

        await self.coordinator.client.send_standard_command(
            self._device_id, "audioNotification", command, args
        )

    # -- Media transport ----------------------------------------------

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
        """Skip to the next track using mediaTrackControl.nextTrack.

        This is the correct capability per the SmartThings API docs.
        The previous code incorrectly used mediaPlayback.fastForward
        which is a scrub/seek command, not a track skip.
        """
        await self.coordinator.client.send_standard_command(
            self._device_id, "mediaTrackControl", "nextTrack"
        )
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Skip to the previous track using mediaTrackControl.previousTrack.

        See async_media_next_track for rationale.
        """
        await self.coordinator.client.send_standard_command(
            self._device_id, "mediaTrackControl", "previousTrack"
        )
        await self.coordinator.async_request_refresh()
