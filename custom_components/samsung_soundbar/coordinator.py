"""DataUpdateCoordinator for Samsung Soundbar.

Single coordinator fetches all device state and OCF data, then distributes
it to every entity via CoordinatorEntity.  Replaces YASSI's per-entity
update() calls.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SmartThingsClient
from .const import (
    DEFAULT_POLL_INTERVAL,
    HREF_ADVANCED_AUDIO,
    HREF_EQ,
    HREF_SOUNDMODE,
    HREF_WOOFER,
    OPT_ENABLE_ADVANCED_AUDIO,
    OPT_ENABLE_EQ,
    OPT_ENABLE_SOUNDMODE,
    OPT_ENABLE_WOOFER,
    PROP_BASS_BOOST,
    PROP_EQ_ACTION,
    PROP_EQ_BANDS,
    PROP_EQ_NAME,
    PROP_EQ_SUPPORTED,
    PROP_NIGHTMODE,
    PROP_SOUNDMODE,
    PROP_SUPPORTED_SOUNDMODE,
    PROP_VOICE_AMP,
    PROP_WOOFER,
    PROP_WOOFER_CONNECTION,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SoundbarState:
    """Snapshot of all soundbar state returned by the coordinator."""

    # Power / switch
    power: bool = False

    # Volume
    volume: int = 0
    muted: bool = False

    # Input
    input_source: str = ""
    supported_input_sources: list[str] = field(default_factory=list)

    # Sound mode
    sound_mode: str = ""
    supported_sound_modes: list[str] = field(default_factory=lambda: ["adaptive sound", "standard", "surround", "game"])

    # Advanced audio
    night_mode: bool = False
    voice_amplifier: bool = False
    bass_boost: bool = False

    # Woofer
    woofer_level: int = 0
    woofer_connection: str = ""

    # Equalizer
    eq_preset: str = ""
    supported_eq_presets: list[str] = field(default_factory=list)
    eq_action: str = ""
    eq_bands: list[dict] = field(default_factory=list)

    # Media
    media_title: str = ""
    media_artist: str = ""
    playback_status: str = ""

    # Device info (set once on first poll)
    manufacturer: str = "Samsung"
    model: str = ""
    firmware_version: str = ""


class SoundbarCoordinator(DataUpdateCoordinator[SoundbarState]):
    """Coordinates polling of a single Samsung soundbar."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: SmartThingsClient,
        device_id: str,
        device_name: str,
        options: dict[str, bool],
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"Samsung Soundbar ({device_name})",
            update_interval=timedelta(seconds=DEFAULT_POLL_INTERVAL),
            always_update=False,
        )
        self.client = client
        self.device_id = device_id
        self.device_name = device_name
        self.options = options
        self._first_poll = True
        self._ocf_index = 0

    async def _async_update_data(self) -> SoundbarState:
        """Fetch all device data in one coordinator cycle."""
        try:
            # Ensure token is fresh before any API calls
            await self.client.ensure_token()

            # Persist refreshed tokens back to the config entry
            self._persist_tokens()

            status = await self.client.get_device_status(self.device_id)
            if not status:
                raise UpdateFailed("Could not reach SmartThings API")

            state = SoundbarState()
            main = status.get("components", {}).get("main", {})

            # ── Standard capabilities ────────────────────────────
            # Power
            switch_val = _nested(main, "switch", "switch", "value")
            state.power = switch_val == "on" if switch_val else False

            # Volume
            vol = _nested(main, "audioVolume", "volume", "value")
            state.volume = vol if isinstance(vol, int) else 0
            mute = _nested(main, "audioMute", "mute", "value")
            state.muted = mute == "muted" if mute else False

            # Input source
            source = _nested(main, "samsungvd.audioInputSource", "inputSource", "value")
            state.input_source = source or ""
            supported = _nested(
                main, "samsungvd.audioInputSource", "supportedInputSources", "value"
            )
            state.supported_input_sources = supported if isinstance(supported, list) else []

            # Media
            state.playback_status = _nested(main, "mediaPlayback", "playbackStatus", "value") or ""
            track_data = _nested(main, "audioTrackData", "audioTrackData", "value")
            if isinstance(track_data, dict):
                state.media_title = track_data.get("title", "")
                state.media_artist = track_data.get("artist", "")

            # Device info (first poll only)
            if self._first_poll:
                state.manufacturer = _nested(main, "ocf", "mnfv", "value") or "Samsung"
                state.model = _nested(main, "ocf", "mnmo", "value") or ""
                state.firmware_version = _nested(main, "ocf", "mnfv", "value") or ""
                # Try the proper fields
                mfr = _nested(main, "ocf", "manufacturerName", "value")
                if mfr:
                    state.manufacturer = mfr
                mdl = _nested(main, "ocf", "modelNumber", "value")
                if mdl:
                    state.model = mdl
                fw = _nested(main, "ocf", "firmwareVersion", "value")
                if fw:
                    state.firmware_version = fw
                self._first_poll = False
            else:
                # Carry forward from previous data
                prev = self.data
                if prev:
                    state.manufacturer = prev.manufacturer
                    state.model = prev.model
                    state.firmware_version = prev.firmware_version

            # ── OCF custom capabilities ──────────────────────────
            # Rotate through one OCF endpoint per poll cycle to avoid
            # SmartThings 429 rate limiting. Each cycle fetches at most
            # one OCF endpoint, so a full refresh takes ~2 minutes.
            ocf_targets = []
            if self.options.get(OPT_ENABLE_SOUNDMODE, True):
                ocf_targets.append("soundmode")
            if self.options.get(OPT_ENABLE_ADVANCED_AUDIO, True):
                ocf_targets.append("advancedaudio")
            if self.options.get(OPT_ENABLE_WOOFER, True):
                ocf_targets.append("woofer")
            if self.options.get(OPT_ENABLE_EQ, False):
                ocf_targets.append("eq")

            if ocf_targets:
                idx = self._ocf_index % len(ocf_targets)
                target = ocf_targets[idx]
                self._ocf_index += 1

                try:
                    if target == "soundmode":
                        sm_data = await self.client.fetch_ocf_data(
                            self.device_id, HREF_SOUNDMODE,
                            PROP_SUPPORTED_SOUNDMODE, max_retries=2,
                        )
                        if sm_data:
                            state.sound_mode = sm_data.get(PROP_SOUNDMODE, state.sound_mode)
                            modes = sm_data.get(PROP_SUPPORTED_SOUNDMODE, [])
                            if modes:
                                state.supported_sound_modes = modes

                    elif target == "advancedaudio":
                        aa_data = await self.client.fetch_ocf_data(
                            self.device_id, HREF_ADVANCED_AUDIO,
                            PROP_NIGHTMODE, max_retries=2,
                        )
                        if aa_data:
                            state.night_mode = aa_data.get(PROP_NIGHTMODE, 0) == 1
                            state.voice_amplifier = aa_data.get(PROP_VOICE_AMP, 0) == 1
                            state.bass_boost = aa_data.get(PROP_BASS_BOOST, 0) == 1

                    elif target == "woofer":
                        wf_data = await self.client.fetch_ocf_data(
                            self.device_id, HREF_WOOFER,
                            PROP_WOOFER, max_retries=2,
                        )
                        if wf_data:
                            state.woofer_level = wf_data.get(PROP_WOOFER, 0)
                            state.woofer_connection = wf_data.get(PROP_WOOFER_CONNECTION, "")

                    elif target == "eq":
                        eq_data = await self.client.fetch_ocf_data(
                            self.device_id, HREF_EQ,
                            PROP_EQ_NAME, max_retries=2,
                        )
                        if eq_data:
                            state.eq_preset = eq_data.get(PROP_EQ_NAME, "")
                            state.supported_eq_presets = eq_data.get(PROP_EQ_SUPPORTED, [])
                            state.eq_action = eq_data.get(PROP_EQ_ACTION, "")
                            state.eq_bands = eq_data.get(PROP_EQ_BANDS, [])
                except Exception:
                    _LOGGER.debug("OCF poll for %s failed, will retry next cycle", target)

            # Carry forward OCF state from previous poll for endpoints
            # not fetched this cycle
            prev = self.data
            if prev:
                if not state.sound_mode and prev.sound_mode:
                    state.sound_mode = prev.sound_mode
                if not state.supported_sound_modes and prev.supported_sound_modes:
                    state.supported_sound_modes = prev.supported_sound_modes
                if state.woofer_level == 0 and prev.woofer_level != 0:
                    state.woofer_level = prev.woofer_level
                if not state.night_mode and prev.night_mode:
                    state.night_mode = prev.night_mode
                if not state.voice_amplifier and prev.voice_amplifier:
                    state.voice_amplifier = prev.voice_amplifier
                if not state.bass_boost and prev.bass_boost:
                    state.bass_boost = prev.bass_boost
                if not state.woofer_connection and prev.woofer_connection:
                    state.woofer_connection = prev.woofer_connection
                if not state.eq_preset and prev.eq_preset:
                    state.eq_preset = prev.eq_preset
                if not state.supported_eq_presets and prev.supported_eq_presets:
                    state.supported_eq_presets = prev.supported_eq_presets

            return state

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Error communicating with soundbar: {err}") from err

    def _persist_tokens(self) -> None:
        """Write refreshed tokens back into the config entry so they survive restarts."""
        if not self.config_entry:
            return
        new_data = {**self.config_entry.data, **self.client.export_token_data()}
        if new_data != self.config_entry.data:
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )


def _nested(d: dict, *keys: str) -> Any:
    """Safely walk nested dicts."""
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)  # type: ignore[assignment]
        if d is None:
            return None
    return d
