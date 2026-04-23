"""SmartThings REST API client with self-managed OAuth tokens.

Ported from the homebridge-q990d-soundbar SmartThingsClient / TokenManager.
Talks directly to the SmartThings v1 API -- no pysmartthings dependency.
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from base64 import b64encode
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from homeassistant.exceptions import HomeAssistantError

from .const import (
    ST_API_BASE,
    ST_TOKEN_URL,
    TOKEN_REFRESH_BUFFER,
)

_LOGGER = logging.getLogger(__name__)

# How long a cached status response is considered fresh (seconds).
STATUS_CACHE_TTL = 2.0

# Rate-limit retry configuration
MAX_RETRIES = 3
BACKOFF_BASE = 1.0  # seconds
BACKOFF_MAX = 30.0  # seconds
JITTER_MAX = 0.5  # seconds


class SoundbarAuthError(HomeAssistantError):
    """Raised when SmartThings returns 401/403 (re-authentication required)."""


class SoundbarCommandError(HomeAssistantError):
    """Raised when a device command or API request fails."""


@dataclass
class TokenData:
    """In-memory representation of OAuth tokens."""

    access_token: str
    refresh_token: str
    expires_at: float  # epoch seconds


@dataclass
class _CacheEntry:
    data: dict[str, Any]
    expires_at: float


class SmartThingsClient:
    """Async client for the SmartThings v1 REST API with OAuth management."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
        token_data: TokenData,
    ) -> None:
        self._session = session
        self._client_id = client_id
        self._client_secret = client_secret
        self._tokens = token_data

        # Coalesce concurrent token refreshes
        self._refresh_lock = asyncio.Lock()

        # Serialize OCF execute+status reads per device to avoid
        # interleaved payloads (the execute status endpoint returns the
        # last response device-wide).
        self._ocf_locks: dict[str, asyncio.Lock] = {}

        # Status cache (device_id -> cached response)
        self._status_cache: dict[str, _CacheEntry] = {}

    # ── Token helpers ────────────────────────────────────────────────

    @property
    def access_token(self) -> str:
        return self._tokens.access_token

    @property
    def refresh_token(self) -> str:
        return self._tokens.refresh_token

    @property
    def token_expires_at(self) -> float:
        return self._tokens.expires_at

    def token_needs_refresh(self) -> bool:
        return time.time() >= (self._tokens.expires_at - TOKEN_REFRESH_BUFFER)

    async def ensure_token(self) -> None:
        """Refresh the access token if it is near expiry.

        Raises SoundbarAuthError if the refresh fails.
        """
        if not self._tokens.refresh_token or not self.token_needs_refresh():
            return
        async with self._refresh_lock:
            # Double-check after acquiring the lock
            if not self._tokens.refresh_token or not self.token_needs_refresh():
                return
            await self._refresh_tokens()

    async def _refresh_tokens(self) -> None:
        basic = b64encode(
            f"{self._client_id}:{self._client_secret}".encode()
        ).decode()
        data = aiohttp.FormData()
        data.add_field("grant_type", "refresh_token")
        data.add_field("refresh_token", self._tokens.refresh_token)

        _LOGGER.debug("Refreshing SmartThings OAuth token")
        try:
            async with self._session.post(
                ST_TOKEN_URL,
                data=data,
                headers={
                    "Authorization": f"Basic {basic}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
            ) as resp:
                if resp.status in (401, 403):
                    raise SoundbarAuthError(
                        f"Token refresh failed with HTTP {resp.status}. "
                        "Re-authentication required."
                    )
                resp.raise_for_status()
                body = await resp.json()

            expires_in = body.get("expires_in", 86400)
            _LOGGER.debug(
                "Token refreshed, expires_in=%s seconds", expires_in
            )
            self._tokens = TokenData(
                access_token=body["access_token"],
                refresh_token=body.get(
                    "refresh_token", self._tokens.refresh_token
                ),
                expires_at=time.time() + expires_in,
            )
            _LOGGER.info("SmartThings token refreshed successfully")
        except SoundbarAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Failed to refresh SmartThings token: %s", err)
            raise SoundbarAuthError(
                f"Token refresh failed: {err}"
            ) from err

    def export_token_data(self) -> dict[str, Any]:
        """Return a dict suitable for persisting in a HA config entry."""
        return {
            "access_token": self._tokens.access_token,
            "refresh_token": self._tokens.refresh_token,
            "token_expires_at": self._tokens.expires_at,
        }

    # ── HTTP helpers ─────────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._tokens.access_token}",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
    ) -> dict[str, Any] | None:
        """Make an API request with automatic retry on 429 rate limits.

        Raises SoundbarAuthError on 401/403.
        Raises SoundbarCommandError on other failures.
        Respects the Retry-After header when present. Falls back to
        exponential backoff with jitter.
        """
        await self.ensure_token()
        url = f"{ST_API_BASE}{path}"

        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                async with self._session.request(
                    method, url, json=json, headers=self._headers()
                ) as resp:
                    # Auth failures surface immediately for reauth handling
                    if resp.status in (401, 403):
                        raise SoundbarAuthError(
                            f"SmartThings API returned {resp.status} for "
                            f"{method} {path}. Re-authentication required."
                        )

                    if resp.status == 429:
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                delay = float(retry_after)
                            except ValueError:
                                delay = BACKOFF_BASE * (2 ** attempt)
                        else:
                            delay = BACKOFF_BASE * (2 ** attempt)
                        delay = min(delay, BACKOFF_MAX)
                        jitter = random.uniform(0, JITTER_MAX)
                        total_delay = delay + jitter
                        _LOGGER.debug(
                            "SmartThings 429 on %s %s, retry %d/%d in %.1fs",
                            method, path, attempt + 1, MAX_RETRIES, total_delay,
                        )
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(total_delay)
                            continue
                        # Final attempt exhausted, raise
                        resp.raise_for_status()

                    resp.raise_for_status()
                    if resp.content_type and "json" in resp.content_type:
                        return await resp.json()
                    return None
            except SoundbarAuthError:
                raise
            except aiohttp.ClientResponseError as err:
                last_error = err
                if err.status != 429 or attempt >= MAX_RETRIES:
                    _LOGGER.error(
                        "SmartThings API %s %s -> %s", method, path, err.status
                    )
                    raise SoundbarCommandError(
                        f"SmartThings API error: {method} {path} returned {err.status}"
                    ) from err
            except SoundbarCommandError:
                raise
            except Exception as err:
                _LOGGER.exception(
                    "SmartThings API request failed: %s %s", method, path
                )
                raise SoundbarCommandError(
                    f"SmartThings API request failed: {method} {path}"
                ) from err

        # Should not reach here, but just in case
        if last_error:
            raise SoundbarCommandError(str(last_error)) from last_error
        return None

    # ── Device commands ──────────────────────────────────────────────

    async def send_execute_command(
        self,
        device_id: str,
        href: str,
        payload: dict[str, Any],
    ) -> None:
        """Send an OCF execute command (the undocumented /sec/networkaudio endpoints).

        Raises SoundbarAuthError on 401/403.
        Raises SoundbarCommandError on other failures.
        """
        body = {
            "commands": [
                {
                    "component": "main",
                    "capability": "execute",
                    "command": "execute",
                    "arguments": [href, payload],
                }
            ]
        }
        await self._request("POST", f"/devices/{device_id}/commands", json=body)
        _LOGGER.debug("Execute: %s %s", href, payload)

    async def send_standard_command(
        self,
        device_id: str,
        capability: str,
        command: str,
        args: list[Any] | None = None,
    ) -> None:
        """Send a standard SmartThings capability command.

        Raises SoundbarAuthError on 401/403.
        Raises SoundbarCommandError on other failures.
        """
        cmd: dict[str, Any] = {
            "component": "main",
            "capability": capability,
            "command": command,
        }
        if args:
            cmd["arguments"] = args
        body = {"commands": [cmd]}
        await self._request("POST", f"/devices/{device_id}/commands", json=body)
        _LOGGER.debug("Command: %s.%s(%s)", capability, command, args)

    async def send_switch_command(self, device_id: str, on: bool) -> None:
        """Send a switch on/off command.

        Raises SoundbarAuthError on 401/403.
        Raises SoundbarCommandError on other failures.
        """
        await self.send_standard_command(
            device_id, "switch", "on" if on else "off"
        )

    # ── Device status (cached) ───────────────────────────────────────

    async def get_device_status(self, device_id: str) -> dict[str, Any] | None:
        """Fetch full device status with a short TTL cache.

        Raises SoundbarAuthError on 401/403 so the coordinator can
        trigger re-authentication.
        """
        now = time.time()
        cached = self._status_cache.get(device_id)
        if cached and cached.expires_at > now:
            return cached.data

        try:
            result = await self._request("GET", f"/devices/{device_id}/status")
            if result:
                self._status_cache[device_id] = _CacheEntry(
                    data=result,
                    expires_at=now + STATUS_CACHE_TTL,
                )
            return result
        except SoundbarAuthError:
            raise
        except Exception:
            _LOGGER.debug("Failed to get device status for %s", device_id)
            return None

    async def get_execute_status(self, device_id: str) -> dict[str, Any] | None:
        """Read the execute capability status (OCF payload).

        Raises SoundbarAuthError on 401/403.
        """
        try:
            result = await self._request(
                "GET",
                f"/devices/{device_id}/components/main/capabilities/execute/status",
            )
            if result and "data" in result:
                return result["data"].get("value", {}).get("payload", {})
            return {}
        except SoundbarAuthError:
            raise
        except Exception:
            _LOGGER.debug("Failed to get execute status for %s", device_id)
            return None

    async def get_device_info(self, device_id: str) -> dict[str, Any] | None:
        """Fetch device metadata (name, label, manufacturer, model)."""
        try:
            return await self._request("GET", f"/devices/{device_id}")
        except Exception:
            return None

    async def list_devices(self) -> list[dict[str, Any]]:
        """List all devices visible to this token."""
        try:
            result = await self._request("GET", "/devices")
            return result.get("items", []) if result else []
        except Exception:
            return []

    # ── OCF data fetch with retry ────────────────────────────────────

    def _get_ocf_lock(self, device_id: str) -> asyncio.Lock:
        """Get or create a per-device lock for OCF reads."""
        if device_id not in self._ocf_locks:
            self._ocf_locks[device_id] = asyncio.Lock()
        return self._ocf_locks[device_id]

    async def fetch_ocf_data(
        self,
        device_id: str,
        href: str,
        expected_key: str,
        max_retries: int = 5,
    ) -> dict[str, Any]:
        """Request an OCF endpoint and poll execute status until the data appears.

        Serialized per-device with a lock to prevent interleaved execute
        commands from clobbering each other's status response.

        Raises SoundbarAuthError on 401/403 (propagated immediately).
        """
        async with self._get_ocf_lock(device_id):
            # Auth errors propagate immediately through the lock
            await self.send_execute_command(device_id, href, {})
            await asyncio.sleep(0.3)

            for attempt in range(max_retries):
                payload = await self.get_execute_status(device_id)
                if payload and expected_key in payload:
                    return payload
                delay = 0.5 * (attempt + 1)  # 0.5, 1.0, 1.5, 2.0, 2.5
                await asyncio.sleep(delay)

            _LOGGER.warning(
                "OCF data for %s not available after %d retries (key: %s)",
                href,
                max_retries,
                expected_key,
            )
            return {}


# ── Static helpers for initial OAuth token exchange ──────────────────


def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    scopes: str = "r:devices:* x:devices:* r:locations:*",
) -> str:
    """Build the SmartThings OAuth authorization URL."""
    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scopes,
    }
    return f"{ST_API_BASE.replace('/v1', '')}/oauth/authorize?{urlencode(params)}"


async def exchange_code_for_tokens(
    session: aiohttp.ClientSession,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> TokenData:
    """Exchange an authorization code for access + refresh tokens."""
    basic = b64encode(f"{client_id}:{client_secret}".encode()).decode()
    data = aiohttp.FormData()
    data.add_field("grant_type", "authorization_code")
    data.add_field("code", code)
    data.add_field("redirect_uri", redirect_uri)

    async with session.post(
        ST_TOKEN_URL,
        data=data,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    ) as resp:
        resp.raise_for_status()
        body = await resp.json()

    expires_in = body.get("expires_in", 86400)
    _LOGGER.debug("Initial token exchange, expires_in=%s seconds", expires_in)

    return TokenData(
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_at=time.time() + expires_in,
    )
