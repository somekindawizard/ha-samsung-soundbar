"""Config flow for Samsung Soundbar integration."""
from __future__ import annotations
import logging
from typing import Any
import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.zeroconf import ZeroconfServiceInfo
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
REDIRECT_URI = "https://api.smartthings.com/oauth/callback"
SCOPES = "r:devices:* x:devices:* r:locations:*"


class SamsungSoundbarConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._client_id = ""
        self._client_secret = ""
        self._token_data = None
        self._devices = []
        self._auth_method = ""
        self._discovered_name: str | None = None
        self._discovered_model: str | None = None

    # ── Zeroconf discovery ──────────────────────────────────────────

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle zeroconf discovery of a Samsung soundbar on the LAN.

        We can discover the device exists, but still need SmartThings
        credentials to control it. This step presents a confirmation
        and then routes to the normal OAuth/PAT auth flow.
        """
        # Extract device info from zeroconf properties
        name = discovery_info.name.split("._")[0] if discovery_info.name else "Samsung Soundbar"
        properties = discovery_info.properties or {}
        model = properties.get("model", properties.get("md", ""))
        manufacturer = properties.get("manufacturer", properties.get("mf", ""))

        # Use the host/mac as a preliminary unique ID to avoid duplicate
        # discovery prompts. The final unique_id is set to the
        # SmartThings device_id during the device selection step.
        unique_id = discovery_info.host or name
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured()

        self._discovered_name = name
        self._discovered_model = model

        self.context["title_placeholders"] = {
            "name": name,
            "model": model,
        }

        _LOGGER.info(
            "Discovered Samsung soundbar via zeroconf: %s (%s) at %s",
            name, model, discovery_info.host,
        )

        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Confirm the user wants to set up the discovered soundbar."""
        if user_input is not None:
            # User confirmed, route to auth method selection
            return await self.async_step_user()

        return self.async_show_form(
            step_id="zeroconf_confirm",
            description_placeholders={
                "name": self._discovered_name or "Samsung Soundbar",
                "model": self._discovered_model or "Unknown",
            },
        )

    # ── Manual setup ────────────────────────────────────────────────

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._auth_method = user_input["auth_method"]
            if self._auth_method == "oauth":
                return await self.async_step_oauth_creds()
            return await self.async_step_pat()
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required("auth_method", default="oauth"): vol.In({
                    "oauth": "OAuth (recommended)",
                    "pat": "Personal Access Token (24hr)",
                }),
            }),
        )

    async def async_step_oauth_creds(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._client_id = user_input[CONF_CLIENT_ID]
            self._client_secret = user_input[CONF_CLIENT_SECRET]
            return await self.async_step_authorize()
        return self.async_show_form(
            step_id="oauth_creds",
            data_schema=vol.Schema({
                vol.Required(CONF_CLIENT_ID): str,
                vol.Required(CONF_CLIENT_SECRET): str,
            }),
            errors=errors,
        )

    async def async_step_authorize(self, user_input=None):
        errors = {}
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
            except aiohttp.ClientResponseError as err:
                _LOGGER.error("Token exchange failed: %s", err)
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
            data_schema=vol.Schema({
                vol.Required("auth_code"): str,
            }),
            description_placeholders={"auth_url": auth_url},
            errors=errors,
        )

    async def async_step_pat(self, user_input=None):
        errors = {}
        if user_input is not None:
            pat = user_input["personal_access_token"].strip()
            self._token_data = TokenData(
                access_token=pat,
                refresh_token="",
                expires_at=0,
            )
            session = async_get_clientsession(self.hass)
            client = SmartThingsClient(
                session=session,
                client_id="",
                client_secret="",
                token_data=self._token_data,
            )
            try:
                self._devices = await client.list_devices()
            except Exception:
                _LOGGER.exception("Failed to list devices")
                errors["base"] = "cannot_connect"
            else:
                if self._devices:
                    return await self.async_step_device()
                errors["base"] = "no_devices"
        return self.async_show_form(
            step_id="pat",
            data_schema=vol.Schema({
                vol.Required("personal_access_token"): str,
            }),
            errors=errors,
        )

    async def async_step_device(self, user_input=None):
        errors = {}
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID]
            await self.async_set_unique_id(device_id)
            self._abort_if_unique_id_configured()
            device_name = device_id
            for dev in self._devices:
                if dev.get("deviceId") == device_id:
                    device_name = dev.get("label") or dev.get("name", device_id)
                    break
            return self.async_create_entry(
                title=device_name,
                data={
                    CONF_ACCESS_TOKEN: self._token_data.access_token,
                    CONF_REFRESH_TOKEN: self._token_data.refresh_token,
                    CONF_TOKEN_EXPIRES_AT: self._token_data.expires_at,
                    CONF_CLIENT_ID: self._client_id,
                    CONF_CLIENT_SECRET: self._client_secret,
                    CONF_DEVICE_ID: device_id,
                    CONF_DEVICE_NAME: device_name,
                    CONF_MAX_VOLUME: user_input.get(CONF_MAX_VOLUME, 100),
                },
            )
        if not self._devices:
            session = async_get_clientsession(self.hass)
            client = SmartThingsClient(
                session=session,
                client_id=self._client_id,
                client_secret=self._client_secret,
                token_data=self._token_data,
            )
            self._devices = await client.list_devices()
            if not self._devices:
                return self.async_abort(reason="no_devices")
        device_options = {
            d["deviceId"]: d.get("label") or d.get("name", d["deviceId"])
            for d in self._devices
        }
        return self.async_show_form(
            step_id="device",
            data_schema=vol.Schema({
                vol.Required(CONF_DEVICE_ID): vol.In(device_options),
                vol.Optional(CONF_MAX_VOLUME, default=100): vol.All(
                    int, vol.Range(min=1, max=100)
                ),
            }),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SamsungSoundbarOptionsFlow(config_entry)


class SamsungSoundbarOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(OPT_ENABLE_SOUNDMODE, default=self._config_entry.options.get(OPT_ENABLE_SOUNDMODE, True)): bool,
                vol.Optional(OPT_ENABLE_ADVANCED_AUDIO, default=self._config_entry.options.get(OPT_ENABLE_ADVANCED_AUDIO, True)): bool,
                vol.Optional(OPT_ENABLE_WOOFER, default=self._config_entry.options.get(OPT_ENABLE_WOOFER, True)): bool,
                vol.Optional(OPT_ENABLE_EQ, default=self._config_entry.options.get(OPT_ENABLE_EQ, False)): bool,
            }),
        )
