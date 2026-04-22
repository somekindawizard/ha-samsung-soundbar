"""Config flow for Samsung Soundbar integration.

Uses self-managed OAuth (same pattern as homebridge-q990d-soundbar):
1. User provides client_id + client_secret
2. We build the SmartThings authorize URL and send the user there
3. User pastes back the authorization code
4. We exchange it for access + refresh tokens
5. User picks their soundbar from discovered devices
"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    SmartThingsClient,
    TokenData,
    build_authorize_url,
    exchange_code_for_tokens,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_MAX_VOLUME,
    CONF_REFRESH_TOKEN,
    CONF_TOKEN_EXPIRES_AT,
    DOMAIN,
    OPT_ENABLE_ADVANCED_AUDIO,
    OPT_ENABLE_EQ,
    OPT_ENABLE_SOUNDMODE,
    OPT_ENABLE_WOOFER,
)

_LOGGER = logging.getLogger(__name__)

# SmartThings redirects here after user authorizes — user copies the code
# from the URL.  This is the same approach the Homebridge plugin uses.
REDIRECT_URI = "https://api.smartthings.com/oauth/callback"
SCOPES = "r:devices:* x:devices:* r:locations:*"


class SamsungSoundbarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Samsung Soundbar."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the flow."""
        self._client_id: str = ""
        self._client_secret: str = ""
        self._token_data: TokenData | None = None
        self._devices: list[dict[str, Any]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 1: Collect OAuth client credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._client_id = user_input[CONF_CLIENT_ID]
            self._client_secret = user_input[CONF_CLIENT_SECRET]
            return await self.async_step_authorize()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                }
            ),
            description_placeholders={
                "oauth_url": "https://smartthings.developer.samsung.com/workspace/projects",
            },
            errors=errors,
        )

    async def async_step_authorize(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 2: Show the authorize URL, collect the code."""
        errors: dict[str, str] = {}

        if user_input is not None:
            code = user_input["auth_code"].strip()
            session = async_get_clientsession(self.hass)
            try:
                self._token_data = await exchange_code_for_tokens(
                    session=session,
                    client_id=self._client_id,
                    client_secret=self._client_secret,
                    code=code,
                    redirect_uri=REDIRECT_URI,
                )
            except aiohttp.ClientResponseError:
                errors["base"] = "invalid_auth_code"
            except Exception:
                _LOGGER.exception("Token exchange failed")
                errors["base"] = "unknown"
            else:
                return await self.async_step_device()

        auth_url = build_authorize_url(
            client_id=self._client_id,
            redirect_uri=REDIRECT_URI,
            scopes=SCOPES,
        )

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema(
                {
                    vol.Required("auth_code"): str,
                }
            ),
            description_placeholders={"auth_url": auth_url},
            errors=errors,
        )

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Step 3: Pick the soundbar from discovered devices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]

            # Check we haven't already configured this device
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()

            # Find the device label for a friendly name
            device_name = device_id
            for dev in self._devices:
                if dev.get("deviceId") == device_id:
                    device_name = dev.get("label") or dev.get("name", device_id)
                    break

            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_CLIENT_ID: self._client_id,
                    CONF_CLIENT_SECRET: self._client_secret,
                    CONF_DEVICE_ID: device_id,
                    CONF_DEVICE_NAME: device_name,
                    CONF_MAX_VOLUME: user_input.get(CONF_MAX_VOLUME, 100),
                    CONF_ACCESS_TOKEN: self._token_data.access_token,
                    CONF_REFRESH_TOKEN: self._token_data.refresh_token,
                    CONF_TOKEN_EXPIRES_AT: self._token_data.expires_at,
                },
            )

        # Fetch the device list so the user can pick their soundbar
        if not self._devices:
            session = async_get_clientsession(self.hass)
            client = SmartThingsClient(
                session=session,
                client_id=self._client_id,
                client_secret=self._client_secret,
                token_data=self._token_data,
            )
            all_devices = await client.list_devices()
            # Filter to devices that have the 'execute' capability
            # (soundbars expose the OCF endpoints through this)
            self._devices = [
                d
                for d in all_devices
                if _device_has_capability(d, "execute")
            ]
            if not self._devices:
                # Fall back to showing all devices
                self._devices = all_devices

        device_options = {
            d["deviceId"]: d.get("label") or d.get("name", d["deviceId"])
            for d in self._devices
        }

        if not device_options:
            return self.async_abort(reason="no_devices")

        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_ID): vol.In(device_options),
                    vol.Optional(CONF_MAX_VOLUME, default=100): vol.All(
                        int, vol.Range(min=1, max=100)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> SamsungSoundbarOptionsFlow:
        """Return the options flow handler."""
        return SamsungSoundbarOptionsFlow(config_entry)


class SamsungSoundbarOptionsFlow(config_entries.OptionsFlow):
    """Options flow to toggle feature groups on/off."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        OPT_ENABLE_SOUNDMODE,
                        default=self._config_entry.options.get(
                            OPT_ENABLE_SOUNDMODE, True
                        ),
                    ): bool,
                    vol.Optional(
                        OPT_ENABLE_ADVANCED_AUDIO,
                        default=self._config_entry.options.get(
                            OPT_ENABLE_ADVANCED_AUDIO, True
                        ),
                    ): bool,
                    vol.Optional(
                        OPT_ENABLE_WOOFER,
                        default=self._config_entry.options.get(
                            OPT_ENABLE_WOOFER, True
                        ),
                    ): bool,
                    vol.Optional(
                        OPT_ENABLE_EQ,
                        default=self._config_entry.options.get(
                            OPT_ENABLE_EQ, False
                        ),
                    ): bool,
                }
            ),
        )


def _device_has_capability(device: dict, capability: str) -> bool:
    """Check if a device JSON has a given capability in any component."""
    for component in device.get("components", []):
        for cap in component.get("capabilities", []):
            cap_id = cap if isinstance(cap, str) else cap.get("id", "")
            if cap_id == capability:
                return True
    return False
