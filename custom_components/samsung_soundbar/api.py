"""SmartThings REST API client with self-managed OAuth tokens.

Ported from the homebridge-q990d-soundbar SmartThingsClient / TokenManager.
Talks directly to the SmartThings v1 API — no pysmartthings dependency.
"""

from __future__ import annotations

import asyncio
import logging
import time
from base64 import b64encode
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    ST_API_BASE,
    ST_TOKEN_URL,
    TOKEN_REFRESH_BUFFER,
)

_LOGGER = logging.getLogger(__name__)

# How long a cached status response is considered fresh (seconds).
STATUS_CACHE_TTL = 2.0


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

        # Status cache (device_id → cached response)
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
        """Refresh the access token if it is near expiry."""
        if not self.token_needs_refresh():
            return
        async with self._refresh_lock:
            # Double-check after acquiring the lock
            if not self.token_needs_refresh():
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
                resp.raise_for_status()
                body = await resp.json()

            expires_in = body.get("expires_in", 86400)
            self._tokens = TokenData(
                access_token=body["access_token"],
                refresh_token=body.get(
                    "refresh_token", self._tokens.refresh_token
                ),
                expires_at=time.time() + expires_in,
            )
            _LOGGER.info("SmartThings token refreshed successfully")
        except Exception:
            _LOGGER.exception("Failed to refresh SmartThings token")
            raise

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
        await self.ensure_token()
        url = f"{ST_API_BASE}{path}"
        try:
            async with self._session.request(
                method, url, json=json, headers=self._headers()
            ) as resp:
                resp.raise_for_status()
                if resp.content_length and resp.content_length > 0:
                    return await resp.json()
                return None
        except aiohttp.ClientResponseError as err:
            _LOGGER.error("SmartThings API %s %s → %s", method, path, err.status)
            raise
        except Exception:
            _LOGGER.exception("SmartThings API request failed: %s %s", method, path)
            raise

    # ── Device commands ──────────────────────────────────────────────

    async def send_execute_command(
        self,
        device_id: str,
        href: str,
        payload: dict[str, Any],
    ) -> bool:
        """Send an OCF execute command (the undocumented /sec/networkaudio endpoints)."""
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
        try:
            await self._request("POST", f"/devices/{device_id}/commands", json=body)
            _LOGGER.debug("Execute: %s %s", href, payload)
            return True
        except Exception:
            _LOGGER.error("Execute failed: %s", href)
            return False

    async def send_standard_command(
        self,
        device_id: str,
        capability: str,
        command: str,
        args: list[Any] | None = None,
    ) -> bool:
        """Send a standard SmartThings capability command."""
        cmd: dict[str, Any] = {
            "component": "main",
            "capability": capability,
            "command": command,
        }
        if args:
            cmd["arguments"] = args
        body = {"commands": [cmd]}
        try:
            await self._request("POST", f"/devices/{device_id}/commands", json=body)
            _LOGGER.debug("Command: %s.%s(%s)", capability, command, args)
            return True
        except Exception:
            _LOGGER.error("Command failed: %s.%s", capability, command)
            return False

    async def send_switch_command(self, device_id: str, on: bool) -> bool:
        return await self.send_standard_command(
            device_id, "switch", "on" if on else "off"
        )

    # ── Device status (cached) ───────────────────────────────────────

    async def get_device_status(self, device_id: str) -> dict[str, Any] | None:
        """Fetch full device status with a short TTL cache."""
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
        except Exception:
            _LOGGER.debug("Failed to get device status for %s", device_id)
            return None

    async def get_execute_status(self, device_id: str) -> dict[str, Any] | None:
        """Read the execute capability status (OCF payload)."""
        try:
            result = await self._request(
                "GET",
                f"/devices/{device_id}/components/main/capabilities/execute/status",
            )
            if result and "data" in result:
                return result["data"].get("value", {}).get("payload", {})
            return {}
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

    async def fetch_ocf_data(
        self,
        device_id: str,
        href: str,
        expected_key: str,
        max_retries: int = 5,
    ) -> dict[str, Any]:
        """Request an OCF endpoint and poll execute status until the data appears.

        This replaces YASSI's awful sleep-and-retry loops with bounded retries
        and shorter initial waits.
        """
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

    return TokenData(
        access_token=body["access_token"],
        refresh_token=body["refresh_token"],
        expires_at=time.time() + body.get("expires_in", 86400),
    )
