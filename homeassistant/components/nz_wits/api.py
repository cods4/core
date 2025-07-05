"""API for NZ WITS Spot Price using client credentials."""

import logging
from typing import Any, cast

from aiohttp import ClientSession, ClientTimeout

from homeassistant.util import dt as dt_util

from .const import NODES_URL, OAUTH2_TOKEN, PRICES_URL, SCHEDULE_TYPES, SCHEDULES_URL

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

        def _raise_auth_error() -> None:
            raise InvalidAuth("Invalid client credentials")

        try:
            async with self._session.post(
                OAUTH2_TOKEN, data=data, timeout=ClientTimeout(total=10)
            ) as response:
                if response.status == 401:
                    _raise_auth_error()
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

        def _raise_token_error() -> None:
            raise InvalidAuth("Token is invalid")

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=ClientTimeout(total=15),
            ) as response:
                if response.status == 401:
                    # Token might be expired, try to get a new one
                    self._access_token = await self._get_access_token()
                    headers = {"Authorization": f"Bearer {self._access_token}"}
                    async with self._session.request(
                        method,
                        url,
                        headers=headers,
                        params=params,
                        timeout=ClientTimeout(total=15),
                    ) as retry_response:
                        if retry_response.status == 401:
                            _raise_token_error()
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

    async def get_available_nodes(self, island: str | None = None) -> list[str]:
        """Fetch available nodes from the API, optionally filtered by island."""
        try:
            params = {}
            if island:
                params["island"] = island

            _LOGGER.debug("Making API request to %s with params: %s", NODES_URL, params)
            data = await self._request("GET", NODES_URL, params=params)
            _LOGGER.debug(
                "Raw API response for nodes (island=%s): %s", island or "all", data
            )

            if isinstance(data, list):
                # Handle both string nodes and object nodes
                node_list = []
                for i, node in enumerate(data):
                    if isinstance(node, str):
                        node_list.append(node)
                        _LOGGER.debug("Added string node: %s", node)
                    elif isinstance(node, dict) and "node" in node:
                        node_list.append(node["node"])
                        _LOGGER.debug("Added node from 'node' field: %s", node["node"])
                    elif isinstance(node, dict) and any(
                        key in node for key in ("id", "name", "code")
                    ):
                        # Try common node identifier fields
                        node_id = node.get("id") or node.get("name") or node.get("code")
                        if node_id:
                            node_list.append(str(node_id))
                            _LOGGER.debug(
                                "Added node from id/name/code field: %s", node_id
                            )
                    else:
                        _LOGGER.warning(
                            "Unhandled node format at index %d: %s", i, node
                        )

                _LOGGER.info(
                    "Parsed %d nodes from API response for island %s: %s",
                    len(node_list),
                    island or "all",
                    node_list,
                )
                return node_list if node_list else []

        except (InvalidAuth, CannotConnect) as exc:
            _LOGGER.error(
                "Failed to fetch nodes for island %s: %s", island or "all", exc
            )
            return []
        else:
            _LOGGER.warning(
                "Received unexpected node data format: %s, data: %s", type(data), data
            )
            return []

    async def get_available_schedules(self) -> list[dict[str, Any]]:
        """Fetch available schedules from the API."""
        try:
            data = await self._request("GET", SCHEDULES_URL)
            if isinstance(data, list):
                return data

        except (InvalidAuth, CannotConnect) as exc:
            _LOGGER.error("Failed to fetch schedules: %s", exc)
            return []
        else:
            _LOGGER.warning("Received unexpected schedule data format")
            return []

    async def get_price_data(self, schedule_type: str) -> list[dict[str, Any]]:
        """Fetch price data for a given schedule."""
        if schedule_type not in SCHEDULE_TYPES:
            _LOGGER.error("Unknown schedule type: %s", schedule_type)
            return []

        base_params = cast(dict[str, Any], SCHEDULE_TYPES[schedule_type]["params"])
        params = dict(base_params)
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

    async def get_historical_price_data(
        self, start_date: str, end_date: str, schedule_type: str
    ) -> list[dict[str, Any]]:
        """Fetch historical price data for a date range.

        Note: This is a placeholder implementation since the WITS API documentation
        doesn't specify a historical data endpoint. In a real implementation,
        this would use date parameters in the API call.
        """
        # For now, return current data as a placeholder
        # In a real implementation, you would modify the params to include date filters
        _LOGGER.debug(
            "Fetching historical data for %s from %s to %s (placeholder implementation)",
            schedule_type,
            start_date,
            end_date,
        )

        # This would be enhanced to use actual historical API endpoints
        # when they become available in the WITS API
        return await self.get_price_data(schedule_type)

    async def validate_node(self, node: str) -> bool:
        """Validate if a node is available and returns data."""
        try:
            # Try to get data for this node
            original_node = self.node
            self.node = node

            # Test if we can get RTD data for this node
            data = await self.get_price_data("RTD")

            # Restore original node
            self.node = original_node

            return len(data) > 0 if data else False

        except (InvalidAuth, CannotConnect) as exc:
            _LOGGER.debug("Node validation failed for %s: %s", node, exc)
            # Restore original node on error
            self.node = original_node
            return False

    async def get_system_status(self) -> dict[str, Any]:
        """Get API system status and availability."""
        try:
            # Test basic connectivity
            await self.test_authentication()

            # Try to get schedules
            schedules = await self.get_available_schedules()

            # Try to get nodes
            nodes = await self.get_available_nodes()

            return {
                "api_available": True,
                "authentication_valid": True,
                "schedules_available": len(schedules) if schedules else 0,
                "nodes_available": len(nodes) if nodes else 0,
                "last_check": dt_util.utcnow().isoformat(),
            }

        except InvalidAuth:
            return {
                "api_available": True,
                "authentication_valid": False,
                "error": "Invalid authentication credentials",
                "last_check": dt_util.utcnow().isoformat(),
            }
        except CannotConnect:
            return {
                "api_available": False,
                "authentication_valid": None,
                "error": "Cannot connect to WITS API",
                "last_check": dt_util.utcnow().isoformat(),
            }
        except (InvalidAuth, CannotConnect) as exc:
            return {
                "api_available": False,
                "authentication_valid": None,
                "error": f"Unexpected error: {exc}",
                "last_check": dt_util.utcnow().isoformat(),
            }
