"""Sensor entities for the Venus 300."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Venus300ConfigEntry, time_sync
from .coordinator import Venus300Coordinator
from .entity import Venus300Entity
from .registers import (
    BYPASS_POSITION,
    BYPASS_TYPE_OPTIONS,
    BYPASS_TYPE_RAW,
    FILTER_DISABLE_STATUS_OPTIONS,
    FILTER_DISABLE_STATUS_RAW,
    FILTER_PRESSURE_INLET,
    FILTER_PRESSURE_OUTLET,
    GLOBAL_STATUS2_RAW,
    GLOBAL_STATUS_RAW,
    HEPA_FILTER_LIFE,
    HEPA_FILTER_PRESSURE,
    INLET_FAN_POWER,
    INLET_FILTER_LIFE,
    MODBUS_PORT,
    OUTLET_FAN_POWER,
    OUTLET_FILTER_LIFE,
    Register,
    SW_ERROR1_RAW,
    SW_ERROR2_RAW,
    TEMP_HOUSE_TO_UNIT,
    TEMP_OUTSIDE_TO_UNIT,
    TEMP_SENSOR_SELECTION_OPTIONS,
    TEMP_SENSOR_SELECTION_RAW,
    TEMP_UNIT_TO_HOUSE,
    TEMP_UNIT_TO_OUTSIDE,
    VENTILATION_MODE_OPTIONS,
    VENTILATION_MODE_RAW,
)


@dataclass(frozen=True)
class Venus300SensorSpec:
    """Describes one read-only register as a sensor entity."""

    register: Register
    translation_key: str
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    native_unit_of_measurement: str | None = None
    entity_category: EntityCategory | None = None
    suggested_display_precision: int | None = None
    options: dict[int, str] | None = None


_TEMP_KWARGS = {
    "device_class": SensorDeviceClass.TEMPERATURE,
    "state_class": SensorStateClass.MEASUREMENT,
    "native_unit_of_measurement": UnitOfTemperature.CELSIUS,
    "suggested_display_precision": 1,
}
_PERCENT_KWARGS = {
    "state_class": SensorStateClass.MEASUREMENT,
    "native_unit_of_measurement": PERCENTAGE,
}
_PRESSURE_KWARGS = {
    "device_class": SensorDeviceClass.PRESSURE,
    "state_class": SensorStateClass.MEASUREMENT,
    "native_unit_of_measurement": UnitOfPressure.PA,
    "entity_category": EntityCategory.DIAGNOSTIC,
}

SENSORS = (
    Venus300SensorSpec(TEMP_OUTSIDE_TO_UNIT, "temperature_outside_to_unit", **_TEMP_KWARGS),
    Venus300SensorSpec(TEMP_UNIT_TO_HOUSE, "temperature_unit_to_house", **_TEMP_KWARGS),
    Venus300SensorSpec(TEMP_HOUSE_TO_UNIT, "temperature_house_to_unit", **_TEMP_KWARGS),
    Venus300SensorSpec(TEMP_UNIT_TO_OUTSIDE, "temperature_unit_to_outside", **_TEMP_KWARGS),
    Venus300SensorSpec(
        INLET_FAN_POWER, "inlet_fan_power", suggested_display_precision=0, **_PERCENT_KWARGS
    ),
    Venus300SensorSpec(
        OUTLET_FAN_POWER, "outlet_fan_power", suggested_display_precision=0, **_PERCENT_KWARGS
    ),
    Venus300SensorSpec(INLET_FILTER_LIFE, "inlet_filter_life", **_PERCENT_KWARGS),
    Venus300SensorSpec(OUTLET_FILTER_LIFE, "outlet_filter_life", **_PERCENT_KWARGS),
    # Only meaningful if the corresponding dP sensor is physically fitted
    # (FACTORY_SET SensorFilterIn/SensorFilterOut) — otherwise reads ~0.
    Venus300SensorSpec(FILTER_PRESSURE_INLET, "filter_pressure_inlet", **_PRESSURE_KWARGS),
    Venus300SensorSpec(FILTER_PRESSURE_OUTLET, "filter_pressure_outlet", **_PRESSURE_KWARGS),
    # Only meaningful if a HEPA stage is fitted (FACTORY_SET HEPA_filter_used).
    Venus300SensorSpec(
        HEPA_FILTER_LIFE,
        "hepa_filter_life",
        entity_category=EntityCategory.DIAGNOSTIC,
        **_PERCENT_KWARGS,
    ),
    Venus300SensorSpec(HEPA_FILTER_PRESSURE, "hepa_filter_pressure", **_PRESSURE_KWARGS),
    Venus300SensorSpec(BYPASS_POSITION, "bypass_position", **_PERCENT_KWARGS),
    Venus300SensorSpec(
        BYPASS_TYPE_RAW,
        "bypass_type",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=BYPASS_TYPE_OPTIONS,
    ),
    Venus300SensorSpec(
        FILTER_DISABLE_STATUS_RAW,
        "filter_disable_status",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=FILTER_DISABLE_STATUS_OPTIONS,
    ),
    Venus300SensorSpec(
        TEMP_SENSOR_SELECTION_RAW,
        "temp_sensor_selection",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=TEMP_SENSOR_SELECTION_OPTIONS,
    ),
    Venus300SensorSpec(
        VENTILATION_MODE_RAW,
        "ventilation_mode",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        options=VENTILATION_MODE_OPTIONS,
    ),
    Venus300SensorSpec(
        MODBUS_PORT, "modbus_port", entity_category=EntityCategory.DIAGNOSTIC
    ),
    Venus300SensorSpec(
        GLOBAL_STATUS_RAW, "global_status_raw", entity_category=EntityCategory.DIAGNOSTIC
    ),
    Venus300SensorSpec(
        GLOBAL_STATUS2_RAW, "global_status2_raw", entity_category=EntityCategory.DIAGNOSTIC
    ),
    Venus300SensorSpec(
        SW_ERROR1_RAW, "sw_error1_raw", entity_category=EntityCategory.DIAGNOSTIC
    ),
    Venus300SensorSpec(
        SW_ERROR2_RAW, "sw_error2_raw", entity_category=EntityCategory.DIAGNOSTIC
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Venus300ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Venus 300 sensors."""
    coordinator = entry.runtime_data
    entities: list[SensorEntity] = [
        Venus300Sensor(coordinator, entry, spec) for spec in SENSORS
    ]
    entities.append(Venus300FilterUsageHoursSensor(coordinator, entry))
    entities.append(Venus300FilterUsagePercentSensor(coordinator, entry))
    entities.append(Venus300FilterUsageResetAtSensor(coordinator, entry))
    entities.append(Venus300ClockDriftSensor(coordinator, entry))
    async_add_entities(entities)


class Venus300Sensor(Venus300Entity, SensorEntity):
    """A read-only Modbus register exposed as a sensor."""

    def __init__(
        self,
        coordinator: Venus300Coordinator,
        entry: Venus300ConfigEntry,
        spec: Venus300SensorSpec,
    ) -> None:
        """Set up the sensor entity for one register."""
        super().__init__(coordinator, entry)
        self._spec = spec
        self._attr_translation_key = spec.translation_key
        self._attr_unique_id = f"{entry.entry_id}_{spec.register.key}"
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class
        self._attr_native_unit_of_measurement = spec.native_unit_of_measurement
        self._attr_entity_category = spec.entity_category
        self._attr_suggested_display_precision = spec.suggested_display_precision
        if spec.options:
            self._attr_options = list(spec.options.values())

    @property
    def native_value(self) -> str | int | float | None:
        """Return the register's current, decoded (and enum-mapped) value."""
        raw = self.coordinator.data.get(self._spec.register.key)
        if raw is None:
            return None
        if self._spec.options:
            return self._spec.options.get(int(raw))
        return raw


class Venus300FilterUsageHoursSensor(Venus300Entity, SensorEntity):
    """Operating hours accumulated in Home Assistant since the last reset.

    See filter_usage.py: independent of the unit's own (sometimes
    non-functional) inlet_filter_life/outlet_filter_life percentage.
    """

    _attr_translation_key = "filter_usage_hours"
    _attr_native_unit_of_measurement = UnitOfTime.HOURS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 1

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_filter_usage_hours"

    @property
    def native_value(self) -> float | None:
        """Return the accumulated hours."""
        return self.coordinator.data.get("filter_usage_hours")


class Venus300FilterUsagePercentSensor(Venus300Entity, SensorEntity):
    """Estimated filter usage: accumulated hours vs. filter_max_hours."""

    _attr_translation_key = "filter_usage_percent"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_filter_usage_percent"

    @property
    def native_value(self) -> float | None:
        """Return the estimated usage percentage."""
        return self.coordinator.data.get("filter_usage_percent")


class Venus300FilterUsageResetAtSensor(Venus300Entity, SensorEntity):
    """When the Home-Assistant-side filter usage tracker was last reset."""

    _attr_translation_key = "filter_usage_reset_at"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_filter_usage_reset_at"

    @property
    def native_value(self):
        """Return the last-reset timestamp."""
        return self.coordinator.data.get("filter_usage_reset_at")


class Venus300ClockDriftSensor(Venus300Entity, SensorEntity):
    """How far the unit's own clock has drifted from Home Assistant's.

    Positive means the unit is ahead; negative means it's behind. See
    time_sync.py: this is corrected automatically (once at startup and
    every 24h) whenever it exceeds time_sync.DRIFT_THRESHOLD_SECONDS, and
    on demand via button.sync_unit_clock.
    """

    _attr_translation_key = "unit_clock_drift"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the sensor."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_unit_clock_drift"

    @property
    def native_value(self) -> float | None:
        """Return the current drift, in seconds."""
        return time_sync.current_drift_seconds(self.coordinator.data)
