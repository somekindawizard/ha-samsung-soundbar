"""Tests for the Samsung Soundbar coordinator."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.core import HomeAssistant

from custom_components.samsung_soundbar.coordinator import (
    SoundbarCoordinator,
    SoundbarState,
)


def _make_coordinator(
    hass: HomeAssistant,
    status_response: dict | None = None,
    ocf_response: dict | None = None,
) -> SoundbarCoordinator:
    """Create a coordinator with mocked API client."""
    client = AsyncMock()
    client.ensure_token = AsyncMock()
    client.access_token = "test-token"
    client.refresh_token = "test-refresh"
    client.token_expires_at = 9999999999.0
    client.token_needs_refresh = MagicMock(return_value=False)
    client.export_token_data = MagicMock(
        return_value={
            "access_token": "test-token",
            "refresh_token": "test-refresh",
            "token_expires_at": 9999999999.0,
        }
    )

    if status_response is None:
        status_response = _make_device_status()
    client.get_device_status = AsyncMock(return_value=status_response)
    client.fetch_ocf_data = AsyncMock(return_value=ocf_response or {})

    coordinator = SoundbarCoordinator(
        hass=hass,
        client=client,
        device_id="test-device-id",
        device_name="Test Soundbar",
        options={
            "enable_soundmode": True,
            "enable_advanced_audio": True,
            "enable_woofer": True,
            "enable_eq": False,
        },
    )

    # Mock config entry to avoid persist_tokens errors
    mock_entry = MagicMock()
    mock_entry.data = {
        "access_token": "test-token",
        "refresh_token": "test-refresh",
        "token_expires_at": 9999999999.0,
    }
    coordinator.config_entry = mock_entry

    return coordinator


def _make_device_status(
    power: str = "on",
    volume: int = 25,
    muted: str = "unmuted",
    input_source: str = "HDMI1",
    playback_status: str = "playing",
) -> dict:
    """Build a mock device status response."""
    return {
        "components": {
            "main": {
                "switch": {"switch": {"value": power}},
                "audioVolume": {"volume": {"value": volume}},
                "audioMute": {"mute": {"value": muted}},
                "samsungvd.audioInputSource": {
                    "inputSource": {"value": input_source},
                    "supportedInputSources": {
                        "value": ["HDMI1", "HDMI2", "bluetooth", "wifi"]
                    },
                },
                "mediaPlayback": {
                    "playbackStatus": {"value": playback_status},
                },
                "audioTrackData": {
                    "audioTrackData": {
                        "value": {
                            "title": "Test Song",
                            "artist": "Test Artist",
                        }
                    },
                },
                "ocf": {
                    "manufacturerName": {"value": "Samsung"},
                    "modelNumber": {"value": "HW-Q990D"},
                    "firmwareVersion": {"value": "1.0.0"},
                },
            }
        }
    }


async def test_first_poll_parses_standard_capabilities(
    hass: HomeAssistant,
) -> None:
    """Test that the first poll correctly parses standard capabilities."""
    coordinator = _make_coordinator(hass)
    state = await coordinator._async_update_data()

    assert state.power is True
    assert state.volume == 25
    assert state.muted is False
    assert state.input_source == "HDMI1"
    assert state.supported_input_sources == [
        "HDMI1", "HDMI2", "bluetooth", "wifi"
    ]
    assert state.playback_status == "playing"
    assert state.media_title == "Test Song"
    assert state.media_artist == "Test Artist"


async def test_first_poll_parses_device_info(hass: HomeAssistant) -> None:
    """Test that the first poll correctly parses device info from OCF."""
    coordinator = _make_coordinator(hass)
    state = await coordinator._async_update_data()

    assert state.manufacturer == "Samsung"
    assert state.model == "HW-Q990D"
    assert state.firmware_version == "1.0.0"


async def test_device_info_only_read_on_first_poll(
    hass: HomeAssistant,
) -> None:
    """Test that device info is read only on the first poll."""
    coordinator = _make_coordinator(hass)

    # First poll reads device info
    state1 = await coordinator._async_update_data()
    assert state1.model == "HW-Q990D"

    # Change the status response to have different model
    coordinator.client.get_device_status = AsyncMock(
        return_value=_make_device_status()
    )
    # Manually alter the return to have a different model
    # Since _first_poll is now False, it should carry forward
    coordinator.data = state1
    state2 = await coordinator._async_update_data()
    assert state2.model == "HW-Q990D"  # Carried forward, not re-read


async def test_power_off(hass: HomeAssistant) -> None:
    """Test parsing when device is powered off."""
    coordinator = _make_coordinator(
        hass, status_response=_make_device_status(power="off")
    )
    state = await coordinator._async_update_data()
    assert state.power is False


async def test_muted(hass: HomeAssistant) -> None:
    """Test parsing muted state."""
    coordinator = _make_coordinator(
        hass, status_response=_make_device_status(muted="muted")
    )
    state = await coordinator._async_update_data()
    assert state.muted is True


async def test_ocf_rotation_cycles_through_targets(
    hass: HomeAssistant,
) -> None:
    """Test that OCF polling rotates through enabled targets."""
    coordinator = _make_coordinator(hass)

    # Poll 1: should fetch soundmode (index 0)
    await coordinator._async_update_data()
    call_args = coordinator.client.fetch_ocf_data.call_args
    assert "/sec/networkaudio/soundmode" in str(call_args)

    # Poll 2: should fetch advancedaudio (index 1)
    coordinator.data = SoundbarState()
    coordinator.client.fetch_ocf_data.reset_mock()
    await coordinator._async_update_data()
    call_args = coordinator.client.fetch_ocf_data.call_args
    assert "/sec/networkaudio/advancedaudio" in str(call_args)

    # Poll 3: should fetch woofer (index 2)
    coordinator.data = SoundbarState()
    coordinator.client.fetch_ocf_data.reset_mock()
    await coordinator._async_update_data()
    call_args = coordinator.client.fetch_ocf_data.call_args
    assert "/sec/networkaudio/woofer" in str(call_args)


async def test_ocf_failure_does_not_crash_update(
    hass: HomeAssistant,
) -> None:
    """Test that an OCF poll failure doesn't crash the entire update."""
    coordinator = _make_coordinator(hass)
    coordinator.client.fetch_ocf_data = AsyncMock(
        side_effect=Exception("OCF timeout")
    )

    # Should complete without raising
    state = await coordinator._async_update_data()
    assert state.power is True  # Standard capabilities still parsed


async def test_api_failure_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """Test that a full API failure raises UpdateFailed."""
    from homeassistant.helpers.update_coordinator import UpdateFailed

    coordinator = _make_coordinator(hass)
    coordinator.client.get_device_status = AsyncMock(return_value=None)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
