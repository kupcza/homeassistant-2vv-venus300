"""Binary sensor entities decoding the Venus 300's status/error bitfields."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Venus300ConfigEntry
from .bitfields import ALL_BITS, BitSensorSpec
from .coordinator import Venus300Coordinator
from .entity import Venus300Entity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Venus300ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Venus 300 status/error bit sensors."""
    coordinator = entry.runtime_data
    async_add_entities(Venus300BitSensor(coordinator, entry, spec) for spec in ALL_BITS)


class Venus300BitSensor(Venus300Entity, BinarySensorEntity):
    """One documented bit of a status/error register."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Venus300Coordinator,
        entry: Venus300ConfigEntry,
        spec: BitSensorSpec,
    ) -> None:
        """Set up the binary sensor for one bit."""
        super().__init__(coordinator, entry)
        self._spec = spec
        self._attr_translation_key = spec.translation_key
        self._attr_unique_id = f"{entry.entry_id}_{spec.register.key}_bit{spec.bit}"
        self._attr_device_class = spec.device_class

    @property
    def is_on(self) -> bool | None:
        """Return whether this bit is set."""
        raw = self.coordinator.data.get(self._spec.register.key)
        if raw is None:
            return None
        return bool(int(raw) >> self._spec.bit & 1)
