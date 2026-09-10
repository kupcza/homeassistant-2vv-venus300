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
    entities.extend(
        Venus300FreecoolingConditionSensor(coordinator, entry, condition_key, translation_key)
        for condition_key, translation_key in (
            ("temp_ok", "freecooling_temperature_met"),
            ("season_ok", "freecooling_season_met"),
            ("hour_ok", "freecooling_hour_window_met"),
        )
    )
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
    ALL currently met, excluding switch.freecooling_enable (check that
    separately). See freecooling_conditions.py for the evaluated logic,
    confirmed against a real unit (wrap-past-midnight hour window,
    evaluated against the unit's own clock, not Home Assistant's).

    If this reads off, check the three individual condition sensors
    (Venus300FreecoolingConditionSensor below) to see which one failed.
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


class Venus300FreecoolingConditionSensor(Venus300Entity, BinarySensorEntity):
    """One individual Freecooling precondition (see freecooling_conditions.py),
    so it's obvious at a glance which one is currently failing instead of
    having to dig into the combined sensor's state.
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: Venus300Coordinator,
        entry: Venus300ConfigEntry,
        condition_key: str,
        translation_key: str,
    ) -> None:
        """Set up the sensor for one condition."""
        super().__init__(coordinator, entry)
        self._condition_key = condition_key
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_freecooling_{condition_key}"

    @property
    def is_on(self) -> bool | None:
        """Return whether this specific condition is currently met."""
        conditions = self.coordinator.data.get("freecooling_conditions")
        return conditions[self._condition_key] if conditions else None
