"""Binary sensor platform for NZ WITS Spot Price analytics."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NzWitsConfigEntry
from .const import CONF_UPDATE_RTD, SCHEDULE_RTD
from .coordinator import WitsDataUpdateCoordinator
from .data_processing import get_price_alerts, get_trading_period_info
from .entity import NzWitsBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

# Binary sensor descriptions for price analytics
ANALYTICS_BINARY_SENSORS = [
    BinarySensorEntityDescription(
        key="high_price_alert",
        translation_key="high_price_alert",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="low_price_opportunity",
        translation_key="low_price_opportunity",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="peak_period",
        translation_key="peak_period",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    BinarySensorEntityDescription(
        key="forecast_high_price",
        translation_key="forecast_high_price",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NzWitsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator: WitsDataUpdateCoordinator = entry.runtime_data

    # Only create binary sensors if RTD is enabled (main price feed)
    update_rtd = entry.options.get(
        CONF_UPDATE_RTD, entry.data.get(CONF_UPDATE_RTD, True)
    )

    if not update_rtd:
        return

    entities = [
        WitsAnalyticsBinarySensor(coordinator, description)
        for description in ANALYTICS_BINARY_SENSORS
    ]

    async_add_entities(entities)


class WitsAnalyticsBinarySensor(NzWitsBaseEntity, BinarySensorEntity):
    """Representation of a WITS analytics binary sensor."""

    def __init__(
        self,
        coordinator: WitsDataUpdateCoordinator,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

        # Set unique ID using the base class node and description key
        self._attr_unique_id = (
            f"{coordinator.config_entry.unique_id or self._node}_{description.key}"
        )

        # Set translation key for proper naming
        self._attr_translation_key = description.key

    @property
    def available(self) -> bool:
        """Return if binary analytics entity is available."""
        # Override base class availability logic since analytics sensors
        # don't depend on specific schedule types in coordinator.data
        if not super().available:
            return False

        # Check if we have any data from the coordinator
        if not self.coordinator.data:
            return False

        # Binary sensors need RTD data as the primary source
        return "RTD" in self.coordinator.data and bool(self.coordinator.data["RTD"])

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not self.coordinator.data:
            return None

        try:
            if self.entity_description.key == "high_price_alert":
                return self._check_high_price_alert()
            if self.entity_description.key == "low_price_opportunity":
                return self._check_low_price_opportunity()
            if self.entity_description.key == "peak_period":
                return self._check_peak_period()
            if self.entity_description.key == "forecast_high_price":
                return self._check_forecast_high_price()
        except (KeyError, ValueError, TypeError) as exc:
            _LOGGER.debug(
                "Error calculating binary sensor state for %s: %s",
                self.entity_description.key,
                exc,
            )

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes."""
        if not self.coordinator.data:
            return None

        try:
            base_attrs = {
                "node": self._node,
                "entity_type": "analytics_binary",
                "description_key": self.entity_description.key,
            }

            if self.entity_description.key == "high_price_alert":
                alerts = get_price_alerts(self.coordinator, 0.30, 0.05)
                base_attrs.update(
                    {
                        "current_alerts": alerts.get("high_price_alerts", []),
                        "threshold": 0.30,
                    }
                )
            elif self.entity_description.key == "low_price_opportunity":
                alerts = get_price_alerts(self.coordinator, 0.30, 0.05)
                base_attrs.update(
                    {
                        "current_opportunities": alerts.get("low_price_alerts", []),
                        "threshold": 0.05,
                    }
                )
            elif self.entity_description.key == "peak_period":
                trading_info = get_trading_period_info(self.coordinator)
                base_attrs.update(
                    {
                        "current_period": trading_info.get("current_trading_period"),
                        "peak_periods": "15-46 (7:00 AM - 11:00 PM)",
                    }
                )
            elif self.entity_description.key == "forecast_high_price":
                alerts = get_price_alerts(self.coordinator, 0.30, 0.05)
                base_attrs.update(
                    {
                        "forecast_alerts": alerts.get("forecast_alerts", []),
                        "threshold": 0.30,
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

    def _check_high_price_alert(self) -> bool:
        """Check if current price is above high threshold."""
        if SCHEDULE_RTD not in self.coordinator.data:
            return False

        rtd_data = self.coordinator.data[SCHEDULE_RTD]
        if not rtd_data or not isinstance(rtd_data, list):
            return False

        current_price = rtd_data[0].get("price")
        if current_price is None:
            return False

        try:
            price_kwh = float(current_price) / 1000
        except (ValueError, TypeError):
            return False
        else:
            return price_kwh >= 0.30  # High price threshold

    def _check_low_price_opportunity(self) -> bool:
        """Check if current price is below low threshold."""
        if SCHEDULE_RTD not in self.coordinator.data:
            return False

        rtd_data = self.coordinator.data[SCHEDULE_RTD]
        if not rtd_data or not isinstance(rtd_data, list):
            return False

        current_price = rtd_data[0].get("price")
        if current_price is None:
            return False

        try:
            price_kwh = float(current_price) / 1000
        except (ValueError, TypeError):
            return False
        else:
            return price_kwh <= 0.05  # Low price threshold

    def _check_peak_period(self) -> bool:
        """Check if current time is in peak period."""
        trading_info = get_trading_period_info(self.coordinator)
        return trading_info.get("is_peak_period", False)

    def _check_forecast_high_price(self) -> bool:
        """Check if any forecast periods show high prices."""
        alerts = get_price_alerts(self.coordinator, 0.30, 0.05)
        forecast_alerts = alerts.get("forecast_alerts", [])

        # Check if any forecast alerts are for high prices
        for alert in forecast_alerts:
            if alert.get("type") == "high_price_upcoming":
                return True

        return False
