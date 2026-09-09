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
    entities: list[BinarySensorEntity] = [
        Venus300BitSensor(coordinator, entry, spec) for spec in ALL_BITS
    ]
    entities.append(Venus300FreecoolingConditionsMetSensor(coordinator, entry))
    async_add_entities(entities)


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


class Venus300FreecoolingConditionsMetSensor(Venus300Entity, BinarySensorEntity):
    """Whether Freecooling's temperature/season/hour-window conditions are
    currently met, excluding switch.freecooling_enable (check that
    separately). See freecooling_conditions.py for the evaluated logic,
    confirmed against a real unit (wrap-past-midnight hour window,
    evaluated against the unit's own clock, not Home Assistant's).
    """

    _attr_translation_key = "freecooling_conditions_met"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_freecooling_conditions_met"

    @property
    def is_on(self) -> bool | None:
        """Return whether every evaluated condition is currently met."""
        conditions = self.coordinator.data.get("freecooling_conditions")
        return conditions["all_met"] if conditions else None

    @property
    def extra_state_attributes(self) -> dict[str, bool] | None:
        """Break down which individual condition(s) are met."""
        conditions = self.coordinator.data.get("freecooling_conditions")
        if not conditions:
            return None
        return {
            "temperature_ok": conditions["temp_ok"],
            "season_ok": conditions["season_ok"],
            "hour_window_ok": conditions["hour_ok"],
        }
