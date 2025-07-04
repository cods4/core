"""The NZ WITS Spot Price integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .api import WitsApiClient
from .const import DOMAIN
from .coordinator import WitsDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type NzWitsConfigEntry = ConfigEntry[WitsDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: NzWitsConfigEntry) -> bool:
    """Set up NZ WITS Spot Price from a config entry."""
    session = aiohttp_client.async_get_clientsession(hass)

    # Create API client
    api_client = WitsApiClient(
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        node=entry.data["node"],
        session=session,
    )

    # Create coordinator
    coordinator = WitsDataUpdateCoordinator(hass, api_client)

    # Fetch initial data so we have something to work with
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: NzWitsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)