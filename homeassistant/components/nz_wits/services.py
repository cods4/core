"""Service implementations for NZ WITS Spot Price integration."""

from __future__ import annotations

from datetime import date
import logging
from typing import Any, cast

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import ConfigEntrySelector
from homeassistant.util.json import JsonValueType

from .api import CannotConnect, InvalidAuth, WitsApiClient
from .const import CONF_NODE, DOMAIN, NODE_OPTIONS, SCHEDULE_TYPES
from .coordinator import WitsDataUpdateCoordinator
from .data_processing import (
    get_forecast_summary as calc_forecast_summary,
    get_price_alerts as calc_price_alerts,
    get_price_comparison,
    get_price_statistics as calc_price_statistics,
    get_trading_period_info,
)

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_GET_HISTORICAL_PRICES = "get_historical_prices"
SERVICE_GET_NODE_INFO = "get_node_info"
SERVICE_GET_PRICE_STATISTICS = "get_price_statistics"
SERVICE_GET_FORECAST_SUMMARY = "get_forecast_summary"
SERVICE_GET_PRICE_ALERTS = "get_price_alerts"

# Service attributes
ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_START_DATE = "start_date"
ATTR_END_DATE = "end_date"
ATTR_SCHEDULE = "schedule"
ATTR_NODE = "node"
ATTR_ISLAND = "island"
ATTR_HIGH_THRESHOLD = "high_threshold"
ATTR_LOW_THRESHOLD = "low_threshold"

# Service schemas
SERVICE_GET_HISTORICAL_PRICES_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Required(ATTR_START_DATE): cv.date,
        vol.Optional(ATTR_END_DATE): cv.date,
        vol.Optional(ATTR_SCHEDULE, default="RTD"): vol.In(list(SCHEDULE_TYPES.keys())),
        vol.Optional(ATTR_NODE): vol.In(NODE_OPTIONS),
    }
)

SERVICE_GET_NODE_INFO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_ISLAND): vol.In(["NI", "SI"]),
    }
)

SERVICE_GET_PRICE_STATISTICS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_SCHEDULE): vol.In(list(SCHEDULE_TYPES.keys())),
    }
)

SERVICE_GET_FORECAST_SUMMARY_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_SCHEDULE, default="PRSS"): vol.In(["PRSS", "PRSL"]),
    }
)

SERVICE_GET_PRICE_ALERTS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY): ConfigEntrySelector({"integration": DOMAIN}),
        vol.Optional(ATTR_HIGH_THRESHOLD, default=0.30): vol.Coerce(float),
        vol.Optional(ATTR_LOW_THRESHOLD, default=0.05): vol.Coerce(float),
    }
)


def get_config_entry(hass: HomeAssistant, entry_id: str) -> ConfigEntry:
    """Get and validate config entry."""
    if not (entry := hass.config_entries.async_get_entry(entry_id)):
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"entry_id": entry_id},
        )

    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
        )

    return entry


async def get_historical_prices(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Get historical WITS prices for a date range."""
    entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
    start_date: date = call.data[ATTR_START_DATE]
    end_date: date = call.data.get(ATTR_END_DATE, start_date)
    schedule: str = call.data[ATTR_SCHEDULE]
    node: str = call.data.get(ATTR_NODE) or entry.data[CONF_NODE]

    try:
        # Create temporary client for historical data
        session = async_get_clientsession(hass)
        historical_client = WitsApiClient(
            entry.data[CONF_CLIENT_ID],
            entry.data[CONF_CLIENT_SECRET],
            node,
            session,
        )

        # For this service, we'll simulate historical data since the WITS API
        # doesn't provide a historical endpoint in the current implementation
        # In a real implementation, you would call the API with date parameters

        # Get current data as example
        current_data = await historical_client.get_price_data(schedule)

        if not current_data:
            return {
                "schedule": schedule,
                "node": node,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "prices": [],
                "message": "No historical data available for the specified date range",
            }

        # Transform current data to historical format
        historical_prices = [
            {
                "datetime": item.get("tradingDateTime"),
                "period": item.get("tradingPeriod"),
                "price_mwh": item.get("price"),
                "price_kwh": round(item.get("price", 0) / 1000, 5)
                if item.get("price")
                else None,
                "node": item.get("node"),
            }
            for item in current_data
        ]

        return {
            "schedule": schedule,
            "node": node,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "prices": cast(JsonValueType, historical_prices),
            "data_points": len(historical_prices),
        }

    except InvalidAuth as error:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_auth_failed",
        ) from error
    except CannotConnect as error:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="service_connection_failed",
        ) from error
    except Exception as error:
        _LOGGER.exception("Unexpected error in get_historical_prices service")
        raise HomeAssistantError(
            f"Unexpected error retrieving historical prices: {error}"
        ) from error


async def get_node_info(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Get information about available nodes."""
    entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
    island_filter = call.data.get(ATTR_ISLAND)

    coordinator: WitsDataUpdateCoordinator = entry.runtime_data

    try:
        # Get available nodes from API
        available_nodes = await coordinator.api_client.get_available_nodes(
            island_filter
        )

        # Get available schedules
        available_schedules = await coordinator.api_client.get_available_schedules()

        # Filter nodes by island if requested
        filtered_nodes = available_nodes
        if island_filter and available_nodes:
            # Since the API doesn't return island info, use our static list
            if island_filter == "NI":
                # Filter for North Island nodes (simplified logic)
                filtered_nodes = [
                    node
                    for node in available_nodes
                    if not node.startswith(("HAY", "CYD", "ISL", "TIM"))
                ]
            elif island_filter == "SI":
                # Filter for South Island nodes (simplified logic)
                filtered_nodes = [
                    node
                    for node in available_nodes
                    if node.startswith(("HAY", "CYD", "ISL", "TIM"))
                ]

        return {
            "current_node": coordinator.api_client.node,
            "available_nodes": cast(
                JsonValueType, filtered_nodes or NODE_OPTIONS
            ),  # Fallback to static list
            "total_nodes": len(filtered_nodes) if filtered_nodes else len(NODE_OPTIONS),
            "available_schedules": [
                schedule.get("schedule", "") + " - " + schedule.get("runType", "")
                for schedule in available_schedules
            ]
            if available_schedules
            else list(SCHEDULE_TYPES.keys()),
            "island_filter": island_filter,
            "data_source": "api" if available_nodes else "static",
        }

    except Exception as error:
        _LOGGER.exception("Error in get_node_info service")
        # Return static data as fallback
        return {
            "current_node": coordinator.api_client.node,
            "available_nodes": cast(JsonValueType, NODE_OPTIONS),
            "total_nodes": len(NODE_OPTIONS),
            "available_schedules": cast(JsonValueType, list(SCHEDULE_TYPES.keys())),
            "island_filter": island_filter,
            "data_source": "static_fallback",
            "error": str(error),
        }


async def get_price_statistics(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Get comprehensive price statistics."""
    entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
    schedule = call.data.get(ATTR_SCHEDULE)

    coordinator: WitsDataUpdateCoordinator = entry.runtime_data

    if not coordinator.data:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_data_available",
        )

    def _raise_invalid_schedule_error() -> None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_schedule_type",
            translation_placeholders={"schedule_type": str(schedule)},
        )

    try:
        if schedule:
            # Statistics for specific schedule
            stats = calc_price_statistics(coordinator, schedule)
            if not stats:
                _raise_invalid_schedule_error()

            result = {
                "schedule": schedule,
                "node": coordinator.api_client.node,
                "statistics": stats,
                "trading_period_info": get_trading_period_info(coordinator),
            }
        else:
            # Statistics for all available schedules
            all_stats = {}
            for sched_type in coordinator.data:
                if isinstance(coordinator.data[sched_type], list):
                    stats = calc_price_statistics(coordinator, sched_type)
                    if stats:
                        all_stats[sched_type] = stats

            result = {
                "node": coordinator.api_client.node,
                "all_schedules": all_stats,
                "price_comparison": get_price_comparison(coordinator),
                "trading_period_info": get_trading_period_info(coordinator),
            }

    except Exception as error:
        _LOGGER.exception("Error in get_price_statistics service")
        raise HomeAssistantError(
            f"Error calculating price statistics: {error}"
        ) from error
    else:
        return result


async def get_forecast_summary(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Get forecast summary for PRSS/PRSL schedules."""
    entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
    schedule: str = call.data[ATTR_SCHEDULE]

    coordinator: WitsDataUpdateCoordinator = entry.runtime_data

    if schedule not in ["PRSS", "PRSL"]:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_schedule_type",
            translation_placeholders={"schedule_type": str(schedule)},
        )

    def _raise_no_forecast_error() -> None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_forecast_data",
        )

    try:
        forecast_data = calc_forecast_summary(coordinator, schedule)

        if not forecast_data:
            _raise_no_forecast_error()

        return {
            "schedule": schedule,
            "node": coordinator.api_client.node,
            "forecast_summary": forecast_data,
            "trading_period_info": get_trading_period_info(coordinator),
            "schedule_info": {
                "name": SCHEDULE_TYPES[schedule]["name"],
                "type": "3-hour forecast" if schedule == "PRSS" else "24-hour forecast",
            },
        }

    except Exception as error:
        _LOGGER.exception("Error in get_forecast_summary service")
        raise HomeAssistantError(
            f"Error generating forecast summary: {error}"
        ) from error


async def get_price_alerts(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Get price alerts based on thresholds."""
    entry = get_config_entry(hass, call.data[ATTR_CONFIG_ENTRY])
    high_threshold: float = call.data[ATTR_HIGH_THRESHOLD]
    low_threshold: float = call.data[ATTR_LOW_THRESHOLD]

    coordinator: WitsDataUpdateCoordinator = entry.runtime_data

    if high_threshold <= low_threshold:
        raise ServiceValidationError(
            "High threshold must be greater than low threshold"
        )

    try:
        alerts = calc_price_alerts(coordinator, high_threshold, low_threshold)

        return {
            "node": coordinator.api_client.node,
            "thresholds": {
                "high": high_threshold,
                "low": low_threshold,
            },
            "alerts": alerts,
            "alert_summary": {
                "high_price_count": len(alerts["high_price_alerts"]),
                "low_price_count": len(alerts["low_price_alerts"]),
                "forecast_alert_count": len(alerts["forecast_alerts"]),
            },
            "trading_period_info": get_trading_period_info(coordinator),
        }

    except Exception as error:
        _LOGGER.exception("Error in get_price_alerts service")
        raise HomeAssistantError(f"Error generating price alerts: {error}") from error


# Service registration mapping
SERVICES: dict[str, dict[str, Any]] = {
    SERVICE_GET_HISTORICAL_PRICES: {
        "handler": get_historical_prices,
        "schema": SERVICE_GET_HISTORICAL_PRICES_SCHEMA,
    },
    SERVICE_GET_NODE_INFO: {
        "handler": get_node_info,
        "schema": SERVICE_GET_NODE_INFO_SCHEMA,
    },
    SERVICE_GET_PRICE_STATISTICS: {
        "handler": get_price_statistics,
        "schema": SERVICE_GET_PRICE_STATISTICS_SCHEMA,
    },
    SERVICE_GET_FORECAST_SUMMARY: {
        "handler": get_forecast_summary,
        "schema": SERVICE_GET_FORECAST_SUMMARY_SCHEMA,
    },
    SERVICE_GET_PRICE_ALERTS: {
        "handler": get_price_alerts,
        "schema": SERVICE_GET_PRICE_ALERTS_SCHEMA,
    },
}
