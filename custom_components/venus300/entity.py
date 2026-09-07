"""Base entity for Venus 300 platforms."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import Venus300Coordinator


class Venus300Entity(CoordinatorEntity[Venus300Coordinator]):
    """Common device info for all Venus 300 entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: Venus300Coordinator, entry: ConfigEntry) -> None:
        """Attach this entity to the unit's device entry."""
        super().__init__(coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
        )
