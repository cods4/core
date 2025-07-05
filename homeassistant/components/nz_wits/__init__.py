"""The NZ WITS Spot Price integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers import aiohttp_client

from .api import WitsApiClient
from .const import CONF_NODE, DOMAIN
from .coordinator import WitsDataUpdateCoordinator
from .services import SERVICES

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)

type NzWitsConfigEntry = ConfigEntry[WitsDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NzWitsConfigEntry) -> bool:
    """Set up NZ WITS Spot Price from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)

    # Create API client
    api_client = WitsApiClient(
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        node=entry.data[CONF_NODE],
        session=session,
    )

    # Create coordinator
    coordinator = WitsDataUpdateCoordinator(hass, api_client, entry)

    # Fetch initial data so we have something to work with
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    # Add logging to confirm coordinator is set up
    _LOGGER.warning(
        "NZ WITS integration setup complete for node %s. Coordinator has %d data keys",
        api_client.node,
        len(coordinator.data) if coordinator.data else 0,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services when the first config entry is set up
    if not any(
        e.entry_id != entry.entry_id for e in hass.config_entries.async_entries(DOMAIN)
    ):
        for service_name, service_config in SERVICES.items():
            if not hass.services.has_service(DOMAIN, service_name):
                hass.services.async_register(
                    DOMAIN,
                    service_name,
                    service_config["handler"],
                    schema=service_config["schema"],
                    supports_response=SupportsResponse.ONLY,
                )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NzWitsConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    # Check if this is the last config entry for this domain
    remaining_entries = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != entry.entry_id and e.state.recoverable
    ]

    # If no more entries, unregister services
    if not remaining_entries:
        for service_name in SERVICES:
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)

    return unload_ok
