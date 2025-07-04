"""API for NZ WITS Spot Price using client credentials."""

import logging
from typing import Any

from aiohttp import ClientSession

from .const import (
    OAUTH2_TOKEN,
    PRICES_URL,
    SCHEDULE_TYPES,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate there is invalid auth."""


class WitsApiClient:
    """Client for WITS API using client credentials flow."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        node: str,
        session: ClientSession,
    ) -> None:
        """Initialize the WITS API client."""
        self._client_id = client_id
        self._client_secret = client_secret
        self.node = node
        self._session = session
        self._access_token: str | None = None

    async def _get_access_token(self) -> str:
        """Get access token using client credentials flow."""
        data = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }

        try:
            async with self._session.post(
                OAUTH2_TOKEN, data=data, timeout=10
            ) as response:
                if response.status == 401:
                    raise InvalidAuth("Invalid client credentials")
                response.raise_for_status()
                token_data = await response.json()
                return token_data["access_token"]
        except TimeoutError as exc:
            raise CannotConnect("Timeout getting access token") from exc
        except Exception as exc:
            raise CannotConnect(f"Error getting access token: {exc}") from exc

    async def _request(self, method: str, url: str, params: dict | None = None) -> Any:
        """Make an authenticated request to the API."""
        if not self._access_token:
            self._access_token = await self._get_access_token()

        headers = {"Authorization": f"Bearer {self._access_token}"}

        try:
            async with self._session.request(
                method, url, headers=headers, params=params, timeout=15
            ) as response:
                if response.status == 401:
                    # Token might be expired, try to get a new one
                    self._access_token = await self._get_access_token()
                    headers = {"Authorization": f"Bearer {self._access_token}"}
                    async with self._session.request(
                        method, url, headers=headers, params=params, timeout=15
                    ) as retry_response:
                        if retry_response.status == 401:
                            raise InvalidAuth("Token is invalid")
                        retry_response.raise_for_status()
                        return await retry_response.json()
                response.raise_for_status()
                return await response.json()
        except TimeoutError as exc:
            raise CannotConnect("Timeout during API request") from exc
        except InvalidAuth:
            raise
        except Exception as exc:
            raise CannotConnect(f"Error during API request: {exc}") from exc

    async def test_authentication(self) -> None:
        """Test if we can authenticate with the API."""
        await self._get_access_token()

    async def get_price_data(self, schedule_type: str) -> list[dict[str, Any]]:
        """Fetch price data for a given schedule."""
        if schedule_type not in SCHEDULE_TYPES:
            _LOGGER.error("Unknown schedule type: %s", schedule_type)
            return []

        params = SCHEDULE_TYPES[schedule_type]["params"].copy()
        params["nodes"] = self.node

        _LOGGER.debug(
            "Fetching price data for schedule '%s' with params: %s",
            schedule_type,
            params,
        )
        data = await self._request("GET", PRICES_URL, params=params)

        if not data or not isinstance(data, list) or "prices" not in data[0]:
            _LOGGER.warning(
                "Received empty or malformed price data for %s", schedule_type
            )
            return []

        return data[0]["prices"]