"""Diagnostics support for NZ WITS Spot Price."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant

from . import NzWitsConfigEntry
from .const import CONF_NODE

# Fields to redact from diagnostics for security
TO_REDACT = [CONF_CLIENT_SECRET]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NzWitsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # Basic config entry information
    config_data = {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "domain": entry.domain,
        "state": entry.state.value,
        "version": entry.version,
        "minor_version": entry.minor_version,
        "unique_id": entry.unique_id,
    }

    # Redacted entry data (removes sensitive information)
    entry_data = async_redact_data(entry.data, TO_REDACT)

    # Add non-sensitive data explicitly
    entry_data["client_id_length"] = len(entry.data.get(CONF_CLIENT_ID, ""))
    entry_data["client_secret_configured"] = bool(entry.data.get(CONF_CLIENT_SECRET))
    entry_data["node"] = entry.data.get(CONF_NODE)

    # Options configuration
    options_data = dict(entry.options)

    # Coordinator status and performance data
    coordinator_data = {
        "last_update_success": coordinator.last_update_success,
        "last_update_success_time": (
            coordinator.last_update_success.isoformat()
            if coordinator.last_update_success is not None
            and hasattr(coordinator.last_update_success, "isoformat")
            else str(coordinator.last_update_success)
            if coordinator.last_update_success is not None
            else None
        ),
        "last_exception": str(coordinator.last_exception)
        if coordinator.last_exception
        else None,
        "update_interval": coordinator.update_interval.total_seconds()
        if coordinator.update_interval
        else None,
        "update_count": getattr(coordinator, "update_count", 0),
        "data_available": bool(coordinator.data),
    }

    # Available schedules and data summary
    data_summary = {}
    if coordinator.data:
        for schedule_type, schedule_data in coordinator.data.items():
            if isinstance(schedule_data, list) and schedule_data:
                # Get first and last data points for each schedule
                first_item = schedule_data[0]
                last_item = schedule_data[-1]

                data_summary[schedule_type] = {
                    "data_points": len(schedule_data),
                    "first_trading_period": first_item.get("tradingPeriod"),
                    "last_trading_period": last_item.get("tradingPeriod"),
                    "first_datetime": first_item.get("tradingDateTime"),
                    "last_datetime": last_item.get("tradingDateTime"),
                    "price_range": {
                        "min": min(
                            item.get("price", 0)
                            for item in schedule_data
                            if item.get("price") is not None
                        ),
                        "max": max(
                            item.get("price", 0)
                            for item in schedule_data
                            if item.get("price") is not None
                        ),
                        "avg": sum(
                            item.get("price", 0)
                            for item in schedule_data
                            if item.get("price") is not None
                        )
                        / len(
                            [
                                item
                                for item in schedule_data
                                if item.get("price") is not None
                            ]
                        ),
                    },
                    "sample_data_point": {
                        "tradingDateTime": first_item.get("tradingDateTime"),
                        "tradingPeriod": first_item.get("tradingPeriod"),
                        "price": first_item.get("price"),
                        "node": first_item.get("node"),
                    },
                }
            else:
                data_summary[schedule_type] = {
                    "data_points": 0,
                    "error": "No valid data available",
                }

    # API client information
    api_client_data = {
        "node": coordinator.api_client.node,
        "base_url": "https://api.electricityinfo.co.nz",
        "has_access_token": bool(
            getattr(coordinator.api_client, "_access_token", None)
        ),
    }

    # System information
    system_data = {
        "integration_version": "1.0.0",
        "home_assistant_version": hass.config.as_dict().get("version", "unknown"),
        "timezone": str(hass.config.time_zone),
    }

    return {
        "config_entry": config_data,
        "entry_data": entry_data,
        "options": options_data,
        "coordinator": coordinator_data,
        "data_summary": data_summary,
        "api_client": api_client_data,
        "system": system_data,
    }
