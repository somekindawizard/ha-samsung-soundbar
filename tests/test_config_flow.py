"""Tests for the Samsung Soundbar config flow."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.samsung_soundbar.const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_MAX_VOLUME,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DOMAIN,
)


MOCK_DEVICES = [
    {
        "deviceId": "device-123",
        "name": "Samsung HW-Q990D",
        "label": "Living Room Soundbar",
    },
]


async def test_full_oauth_flow(hass: HomeAssistant) -> None:
    """Test the complete OAuth config flow from start to finish."""
    # Step 1: User selects OAuth
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"auth_method": "oauth"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "oauth_creds"

    # Step 2: Enter OAuth credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CLIENT_ID: "test-client-id", CONF_CLIENT_SECRET: "test-secret"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authorize"

    # Step 3: Exchange auth code for tokens
    mock_token_data = MagicMock()
    mock_token_data.access_token = "test-access-token"
    mock_token_data.refresh_token = "test-refresh-token"
    mock_token_data.expires_at = 9999999999.0

    with (
        patch(
            "custom_components.samsung_soundbar.config_flow.exchange_code_for_tokens",
            new_callable=AsyncMock,
            return_value=mock_token_data,
        ),
        patch(
            "custom_components.samsung_soundbar.config_flow.SmartThingsClient",
        ) as mock_client_cls,
    ):
        mock_client = AsyncMock()
        mock_client.list_devices = AsyncMock(return_value=MOCK_DEVICES)
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"auth_code": "test-auth-code"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "device"

    # Step 4: Select device
    with patch(
        "custom_components.samsung_soundbar.async_setup_entry",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_DEVICE_ID: "device-123", CONF_MAX_VOLUME: 80},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Living Room Soundbar"
    assert result["data"][CONF_DEVICE_ID] == "device-123"
    assert result["data"][CONF_MAX_VOLUME] == 80
    assert result["data"][CONF_ACCESS_TOKEN] == "test-access-token"


async def test_pat_flow(hass: HomeAssistant) -> None:
    """Test config flow with Personal Access Token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"auth_method": "pat"},
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "pat"

    with patch(
        "custom_components.samsung_soundbar.config_flow.SmartThingsClient",
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.list_devices = AsyncMock(return_value=MOCK_DEVICES)
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"personal_access_token": "test-pat-token"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "device"


async def test_pat_flow_no_devices(hass: HomeAssistant) -> None:
    """Test PAT flow when no devices are found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"auth_method": "pat"},
    )

    with patch(
        "custom_components.samsung_soundbar.config_flow.SmartThingsClient",
    ) as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.list_devices = AsyncMock(return_value=[])
        mock_client_cls.return_value = mock_client

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"personal_access_token": "test-pat-token"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "no_devices"}


async def test_oauth_invalid_auth_code(hass: HomeAssistant) -> None:
    """Test OAuth flow with an invalid authorization code."""
    import aiohttp

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"auth_method": "oauth"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_CLIENT_ID: "test-id", CONF_CLIENT_SECRET: "test-secret"},
    )

    with patch(
        "custom_components.samsung_soundbar.config_flow.exchange_code_for_tokens",
        new_callable=AsyncMock,
        side_effect=aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=400,
            message="Bad Request",
        ),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"auth_code": "bad-code"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth_code"}
