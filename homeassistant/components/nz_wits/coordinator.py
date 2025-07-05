"""DataUpdateCoordinator for the NZ WITS integration."""

import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import CannotConnect, InvalidAuth, WitsApiClient
from .const import (
    CONF_UPDATE_INTERIM,
    CONF_UPDATE_PRSL,
    CONF_UPDATE_PRSS,
    CONF_UPDATE_RTD,
    DOMAIN,
    SCHEDULE_INTERIM,
    SCHEDULE_PRSL,
    SCHEDULE_PRSS,
    SCHEDULE_RTD,
    SCHEDULE_TYPES,
)

_LOGGER = logging.getLogger(__name__)


class WitsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching WITS data from the API."""

    def __init__(
        self, hass: HomeAssistant, api_client: WitsApiClient, config_entry: ConfigEntry
    ) -> None:
        """Initialize."""
        self.api_client = api_client
        self.config_entry: ConfigEntry = config_entry
        # Define a default update interval, e.g., 5 minutes.
        # This can be made configurable later if needed.
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({api_client.node})",
            update_interval=timedelta(minutes=5),
            config_entry=config_entry,
        )
        _LOGGER.warning(
            "WitsDataUpdateCoordinator initialized for node %s with 5-minute update interval",
            api_client.node,
        )

    def _get_enabled_schedules(self) -> dict[str, dict]:
        """Get the enabled schedules based on config entry options."""
        enabled_schedules = {}

        # Check which schedules are enabled
        options = self.config_entry.options
        data = self.config_entry.data

        # Get from options first, then data, then default to True
        if options.get(CONF_UPDATE_RTD, data.get(CONF_UPDATE_RTD, True)):
            enabled_schedules[SCHEDULE_RTD] = SCHEDULE_TYPES[SCHEDULE_RTD]
        if options.get(CONF_UPDATE_INTERIM, data.get(CONF_UPDATE_INTERIM, True)):
            enabled_schedules[SCHEDULE_INTERIM] = SCHEDULE_TYPES[SCHEDULE_INTERIM]
        if options.get(CONF_UPDATE_PRSS, data.get(CONF_UPDATE_PRSS, True)):
            enabled_schedules[SCHEDULE_PRSS] = SCHEDULE_TYPES[SCHEDULE_PRSS]
        if options.get(CONF_UPDATE_PRSL, data.get(CONF_UPDATE_PRSL, True)):
            enabled_schedules[SCHEDULE_PRSL] = SCHEDULE_TYPES[SCHEDULE_PRSL]

        return enabled_schedules

    async def _async_update_data(self):
        """Fetch data from API endpoint.

        This is the place to pre-process the data to lookup tables
        so entities can quickly look up their data.
        """
        _LOGGER.warning(
            "WitsDataUpdateCoordinator: Starting scheduled update for node %s",
            self.api_client.node,
        )
        try:
            # Using asyncio.timeout protects against API hangs indefinitely.
            # Adjust timeout as necessary for your API.
            async with asyncio.timeout(30):
                # Get only enabled schedules
                enabled_schedules = self._get_enabled_schedules()
                _LOGGER.warning(
                    "Coordinator updating data for enabled schedules: %s",
                    list(enabled_schedules.keys()),
                )

                # Fetch data for enabled schedule types only.
                # The API client is expected to fetch data for its configured node.
                # We will store data for all schedules under a common structure.
                all_schedule_data = {}
                for schedule_key in enabled_schedules:
                    _LOGGER.warning("Fetching data for schedule: %s", schedule_key)
                    price_data = await self.api_client.get_price_data(schedule_key)
                    _LOGGER.warning(
                        "Received %d price records for schedule %s",
                        len(price_data) if price_data else 0,
                        schedule_key,
                    )
                    all_schedule_data[schedule_key] = price_data

                if enabled_schedules and not any(
                    all_schedule_data.values()
                ):  # Check if all enabled schedules returned empty data
                    # This could indicate an issue with the node or API returning no data
                    # even if the calls were successful.
                    _LOGGER.warning(
                        "No price data received for node %s across enabled schedules: %s",
                        self.api_client.node,
                        list(enabled_schedules.keys()),
                    )
                    # Depending on desired behavior, you might raise UpdateFailed here
                    # or return the empty structure. For now, returning it.

                # Add a timestamp for when the API call was successful
                all_schedule_data["last_api_success_utc"] = dt_util.utcnow()

                _LOGGER.warning(
                    "Coordinator update complete. Final data keys: %s",
                    list(all_schedule_data.keys()),
                )

                return all_schedule_data
        except InvalidAuth as err:
            # Raising ConfigEntryAuthFailed will direct user to reconfigure the integration.
            # This is for cases where credentials are no longer valid.
            _LOGGER.error("Authentication failed while updating WITS data: %s", err)
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except CannotConnect as err:
            # Temporary connection issues should raise UpdateFailed to retry later.
            _LOGGER.error("Error connecting to WITS API while updating data: %s", err)
            raise UpdateFailed(f"Error communicating with API: {err}") from err
        except Exception as err:
            # Catch any other unexpected errors.
            _LOGGER.exception(
                "Unexpected error fetching WITS data for node %s",
                self.api_client.node,
            )
            raise UpdateFailed(f"An unexpected error occurred: {err}") from err
