"""Sensor platform for NZ WITS Spot Price."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import NzWitsConfigEntry
from .const import (
    CONF_UPDATE_INTERIM,
    CONF_UPDATE_PRSL,
    CONF_UPDATE_PRSS,
    CONF_UPDATE_RTD,
    SCHEDULE_INTERIM,
    SCHEDULE_PRSL,
    SCHEDULE_PRSS,
    SCHEDULE_RTD,
    SCHEDULE_TYPES,
)
from .coordinator import WitsDataUpdateCoordinator
from .data_processing import get_forecast_summary, get_price_statistics
from .entity import NzWitsBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Advanced entity descriptions for analytics sensors
ADVANCED_SENSOR_DESCRIPTIONS = [
    SensorEntityDescription(
        key="current_price",
        translation_key="current_price",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"NZD/{UnitOfEnergy.KILO_WATT_HOUR}",
        # Note: Monetary sensors should not use state_class per Home Assistant guidelines
    ),
    SensorEntityDescription(
        key="average_price",
        translation_key="average_price",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"NZD/{UnitOfEnergy.KILO_WATT_HOUR}",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="forecast_next_hour",
        translation_key="forecast_next_hour",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"NZD/{UnitOfEnergy.KILO_WATT_HOUR}",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="forecast_summary",
        translation_key="forecast_summary",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement=f"NZD/{UnitOfEnergy.KILO_WATT_HOUR}",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NzWitsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    # Get the coordinator from entry runtime data
    coordinator: WitsDataUpdateCoordinator = entry.runtime_data

    # Get options for which sensors to create - check options first, then data, then default to True
    update_options = {
        SCHEDULE_RTD: entry.options.get(
            CONF_UPDATE_RTD, entry.data.get(CONF_UPDATE_RTD, True)
        ),
        SCHEDULE_INTERIM: entry.options.get(
            CONF_UPDATE_INTERIM, entry.data.get(CONF_UPDATE_INTERIM, True)
        ),
        SCHEDULE_PRSS: entry.options.get(
            CONF_UPDATE_PRSS, entry.data.get(CONF_UPDATE_PRSS, True)
        ),
        SCHEDULE_PRSL: entry.options.get(
            CONF_UPDATE_PRSL, entry.data.get(CONF_UPDATE_PRSL, True)
        ),
    }

    entities: list[SensorEntity] = []

    # Create a sensor for each schedule type that is enabled
    for schedule_type, details in SCHEDULE_TYPES.items():
        if update_options.get(
            schedule_type, True
        ):  # Default to True for backward compatibility
            schedule_name = str(details["name"])  # Ensure it's a string
            entities.append(WitsPriceSensor(coordinator, schedule_type, schedule_name))

    # Add advanced analytics entities if RTD is enabled (main price feed)
    if update_options.get(SCHEDULE_RTD, True):
        _LOGGER.warning(
            "Creating %d analytics sensors", len(ADVANCED_SENSOR_DESCRIPTIONS)
        )
        for description in ADVANCED_SENSOR_DESCRIPTIONS:
            _LOGGER.warning("Creating analytics sensor: %s", description.key)
            entities.append(WitsAnalyticsSensor(coordinator, description))
    else:
        _LOGGER.warning("RTD is disabled, skipping analytics sensors")

    async_add_entities(entities)


class WitsPriceSensor(NzWitsBaseEntity, SensorEntity):
    """Representation of a WITS Spot Price Sensor."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_suggested_display_precision = 5
    # Note: Monetary sensors should not use state_class per Home Assistant guidelines

    # The API gives price per MWh, we want price per kWh
    _attr_native_unit_of_measurement = f"NZD/{UnitOfEnergy.KILO_WATT_HOUR}"

    def __init__(
        self,
        coordinator: WitsDataUpdateCoordinator,
        schedule_type: str,
        schedule_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, schedule_type)

        # Set translation key for entity name
        self._attr_translation_key = f"{schedule_type.lower()}_price"

        # Set unique ID using the base class node and schedule type
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id or self._node}_{schedule_type}"
        )

        # Keep the schedule name for backward compatibility
        self._schedule_name = schedule_name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        latest_data = self._get_latest_price_data()
        if not latest_data:
            return None

        price_mwh = latest_data.get("price")
        if price_mwh is None:
            return None

        try:
            return self._get_price_in_kwh(float(price_mwh))
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Could not parse price '%s' for %s schedule for node %s",
                price_mwh,
                self.schedule_type,
                self._node,
            )
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        latest_data = self._get_latest_price_data()
        if not latest_data:
            return None

        schedule_data = self._get_schedule_data()

        attributes = {
            "node": latest_data.get("node"),
            "schedule_type": self.schedule_type,
            "schedule_name": SCHEDULE_TYPES[self.schedule_type]["name"],
            "trading_period": latest_data.get("tradingPeriod"),
            "trading_datetime": latest_data.get("tradingDateTime"),
            "last_updated_from_coordinator": (
                dt_util.as_local(
                    self.coordinator.data["last_api_success_utc"]
                ).isoformat()
                if self.coordinator.data
                and "last_api_success_utc" in self.coordinator.data
                and self.coordinator.data["last_api_success_utc"]
                else None
            ),
        }

        # For forecast schedules, add the full forecast list
        if self.schedule_type in [SCHEDULE_PRSS, SCHEDULE_PRSL] and schedule_data:
            attributes["forecast_data"] = schedule_data

        return attributes


class WitsAnalyticsSensor(NzWitsBaseEntity, SensorEntity):
    """Representation of an advanced WITS analytics sensor."""

    def __init__(
        self,
        coordinator: WitsDataUpdateCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the advanced analytics sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

        # Set unique ID using the base class node and description key
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id or self._node}_{description.key}"
        )

        _LOGGER.warning(
            "Initialized analytics sensor: %s with unique_id: %s",
            description.key,
            self._attr_unique_id,
        )

    @property
    def native_value(self) -> float | None:
        """Return the sensor value based on the entity key."""
        if not self.coordinator.data:
            _LOGGER.debug(
                "No coordinator data available for %s", self.entity_description.key
            )
            return None

        _LOGGER.debug(
            "Analytics sensor %s: coordinator data keys: %s",
            self.entity_description.key,
            list(self.coordinator.data.keys()),
        )

        try:
            if self.entity_description.key == "current_price":
                return self._get_current_price()
            if self.entity_description.key == "average_price":
                return self._get_average_price()
            if self.entity_description.key == "forecast_next_hour":
                return self._get_forecast_next_hour()
            if self.entity_description.key == "forecast_summary":
                return self._get_forecast_summary_value()
        except (KeyError, ValueError, TypeError) as exc:
            _LOGGER.debug(
                "Error calculating value for %s: %s", self.entity_description.key, exc
            )

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes based on the entity key."""
        if not self.coordinator.data:
            return None

        try:
            base_attrs = {
                "node": self._node,
                "entity_type": "analytics",
                "description_key": self.entity_description.key,
            }

            if self.entity_description.key == "current_price":
                base_attrs.update(self._get_current_price_attributes())
            elif self.entity_description.key == "average_price":
                base_attrs.update(get_price_statistics(self.coordinator, "RTD"))
            elif self.entity_description.key == "forecast_next_hour":
                base_attrs.update(
                    {
                        "forecast_type": "PRSS",
                        "forecast_data": get_forecast_summary(self.coordinator, "PRSS"),
                    }
                )
            elif self.entity_description.key == "forecast_summary":
                base_attrs.update(
                    {
                        "forecast_type": "PRSL",
                        "prss_summary": get_forecast_summary(self.coordinator, "PRSS"),
                        "prsl_summary": get_forecast_summary(self.coordinator, "PRSL"),
                    }
                )

        except (KeyError, ValueError, TypeError) as exc:
            _LOGGER.debug(
                "Error calculating attributes for %s: %s",
                self.entity_description.key,
                exc,
            )
            return {"node": self._node, "error": str(exc)}
        else:
            return base_attrs

    def _get_current_price(self) -> float | None:
        """Get current RTD price in kWh."""
        if "RTD" not in self.coordinator.data:
            return None

        rtd_data = self.coordinator.data["RTD"]
        if not rtd_data or not isinstance(rtd_data, list):
            return None

        price = rtd_data[0].get("price")
        if price is None:
            return None

        try:
            return float(price) / 1000
        except (ValueError, TypeError):
            return None

    def _get_current_price_attributes(self) -> dict[str, Any]:
        """Get attributes for current price sensor."""
        if "RTD" not in self.coordinator.data or not self.coordinator.data["RTD"]:
            return {}

        rtd_item = self.coordinator.data["RTD"][0]
        return {
            "price_mwh": rtd_item.get("price"),
            "trading_period": rtd_item.get("tradingPeriod"),
        }

    def _get_average_price(self) -> float | None:
        """Get average price from statistics."""
        stats = get_price_statistics(self.coordinator, "RTD")
        return stats.get("average_price") if stats else None

    def _get_forecast_next_hour(self) -> float | None:
        """Get next hour forecast price."""
        forecast = get_forecast_summary(self.coordinator, "PRSS")
        return forecast.get("next_hour_price") if forecast else None

    def _get_forecast_summary_value(self) -> float | None:
        """Get 6-hour average forecast price."""
        forecast = get_forecast_summary(self.coordinator, "PRSL")
        return forecast.get("avg_next_6h") if forecast else None

    @property
    def available(self) -> bool:
        """Return if analytics entity is available."""
        # Override base class availability logic since analytics sensors
        # don't depend on specific schedule types in coordinator.data
        if not super().available:
            _LOGGER.debug(
                "Analytics sensor %s: coordinator not available",
                self.entity_description.key,
            )
            return False

        # Check if we have any data from the coordinator
        if not self.coordinator.data:
            _LOGGER.warning(
                "Analytics sensor %s: no coordinator data", self.entity_description.key
            )
            return False

        _LOGGER.warning(
            "Analytics sensor %s availability check: data keys = %s",
            self.entity_description.key,
            list(self.coordinator.data.keys()),
        )

        # For analytics sensors, we need RTD data as the primary source
        if self.entity_description.key in ["current_price", "average_price"]:
            has_rtd = "RTD" in self.coordinator.data
            rtd_data = self.coordinator.data.get("RTD", []) if has_rtd else []
            available = has_rtd and bool(rtd_data)
            _LOGGER.warning(
                "Analytics sensor %s (RTD-based): has_rtd=%s, rtd_data_len=%s, available=%s",
                self.entity_description.key,
                has_rtd,
                len(rtd_data) if rtd_data else 0,
                available,
            )
            return available

        # For forecast analytics, we need PRSS or PRSL data
        if self.entity_description.key in ["forecast_next_hour", "forecast_summary"]:
            has_prss = "PRSS" in self.coordinator.data and bool(
                self.coordinator.data["PRSS"]
            )
            has_prsl = "PRSL" in self.coordinator.data and bool(
                self.coordinator.data["PRSL"]
            )
            available = has_prss or has_prsl
            _LOGGER.warning(
                "Analytics sensor %s (forecast-based): has_prss=%s, has_prsl=%s, available=%s",
                self.entity_description.key,
                has_prss,
                has_prsl,
                available,
            )
            return available

        # Default: available if we have any schedule data
        available = any(
            self.coordinator.data.get(schedule)
            for schedule in ("RTD", "Interim", "PRSS", "PRSL")
        )
        _LOGGER.warning(
            "Analytics sensor %s (default): available = %s",
            self.entity_description.key,
            available,
        )
        return available
