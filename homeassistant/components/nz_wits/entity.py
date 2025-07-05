"""Base entity for NZ WITS Spot Price integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_NODE, DOMAIN
from .coordinator import WitsDataUpdateCoordinator


class NzWitsBaseEntity(CoordinatorEntity[WitsDataUpdateCoordinator]):
    """Base entity for NZ WITS sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: WitsDataUpdateCoordinator,
        schedule_type: str,
    ) -> None:
        """Initialize NZ WITS base entity."""
        super().__init__(coordinator)

        self.schedule_type = schedule_type
        self._node = coordinator.config_entry.data[CONF_NODE]

        # Set up device info for service-type integration
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.unique_id or self._node)},
            name=f"WITS ({self._node})",
            manufacturer="New Zealand Electricity Market",
            model=f"Grid Node {self._node}",
            configuration_url="https://www2.electricityinfo.co.nz/",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not super().available:
            return False

        # Check if we have data for this specific schedule type
        if not self.coordinator.data:
            return False

        return self.schedule_type in self.coordinator.data

    def _get_schedule_data(self) -> list[dict] | None:
        """Get data for this entity's schedule type."""
        if not self.coordinator.data:
            return None

        return self.coordinator.data.get(self.schedule_type)

    def _get_latest_price_data(self) -> dict | None:
        """Get the latest price data point for this schedule."""
        schedule_data = self._get_schedule_data()
        if not schedule_data:
            return None

        # Return the first item (most recent)
        return schedule_data[0] if schedule_data else None

    def _get_price_in_kwh(self, price_mwh: float | None) -> float | None:
        """Convert price from MWh to kWh."""
        if price_mwh is None:
            return None
        return round(price_mwh / 1000, 5)
