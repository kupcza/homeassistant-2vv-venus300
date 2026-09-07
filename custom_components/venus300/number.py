"""Number entities for the Venus 300."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Venus300ConfigEntry
from .coordinator import Venus300Coordinator
from .entity import Venus300Entity
from .modbus_client import Venus300ModbusError
from .registers import (
    BYPASS_TEMP_THRESHOLD,
    FAN_POWER_SETPOINT,
    FILTER_MAX_HOURS,
    FREECOOLING_AIRFLOW,
    FREECOOLING_OFF_DAY,
    FREECOOLING_OFF_HOUR,
    FREECOOLING_OFF_MIN,
    FREECOOLING_OFF_MONTH,
    FREECOOLING_ON_DAY,
    FREECOOLING_ON_HOUR,
    FREECOOLING_ON_MIN,
    FREECOOLING_ON_MONTH,
    FREECOOLING_TEMP_THRESHOLD,
    Register,
    TEMPERATURE_SETPOINT,
    encode_value,
)


@dataclass(frozen=True)
class Venus300NumberSpec:
    """Describes one writable holding register as a number entity."""

    register: Register
    translation_key: str
    native_min_value: float
    native_max_value: float
    native_step: float
    native_unit_of_measurement: str | None
    entity_category: EntityCategory | None = None


NUMBERS = (
    # doc 21002 "AirFlowManual": only meaningful while ventilation_mode is
    # Manual (SERVICE_HARD 25000); the unit itself computes airflow in
    # DCV/CAV/VAV/VAVC4/PCO modes.
    Venus300NumberSpec(FAN_POWER_SETPOINT, "fan_power_setpoint", 0, 100, 1, PERCENTAGE),
    # doc 21003 "Temperature": valid range depends on temp_sensor_selection
    # (SERVICE_HARD 25009) — 15-45 C for supply duct, 15-30 C for extract
    # duct/room. 15-45 covers every case; the unit itself clamps further.
    Venus300NumberSpec(
        TEMPERATURE_SETPOINT, "temperature_setpoint", 15, 45, 1, UnitOfTemperature.CELSIUS
    ),
    # doc 20037 "BypassTemperature": documented range 0-20 C, default 15 C.
    Venus300NumberSpec(
        BYPASS_TEMP_THRESHOLD,
        "bypass_temp_threshold",
        0,
        20,
        1,
        UnitOfTemperature.CELSIUS,
        EntityCategory.CONFIG,
    ),
    # Freecooling only engages if freecooling_enable (switch) is on, AND the
    # outdoor temperature is below this threshold, AND the current date/time
    # falls within the season and daily-hours window below. All from the
    # SERVICE sheet, doc 20015-20024.
    Venus300NumberSpec(
        FREECOOLING_AIRFLOW,
        "freecooling_airflow",
        50,
        100,
        1,
        PERCENTAGE,
        EntityCategory.CONFIG,
    ),
    Venus300NumberSpec(
        FREECOOLING_TEMP_THRESHOLD,
        "freecooling_temp_threshold",
        12,
        25,
        1,
        UnitOfTemperature.CELSIUS,
        EntityCategory.CONFIG,
    ),
    Venus300NumberSpec(FREECOOLING_ON_MONTH, "freecooling_on_month", 1, 12, 1, None, EntityCategory.CONFIG),
    Venus300NumberSpec(FREECOOLING_ON_DAY, "freecooling_on_day", 1, 31, 1, None, EntityCategory.CONFIG),
    Venus300NumberSpec(FREECOOLING_ON_HOUR, "freecooling_on_hour", 0, 23, 1, None, EntityCategory.CONFIG),
    Venus300NumberSpec(FREECOOLING_ON_MIN, "freecooling_on_min", 0, 59, 1, None, EntityCategory.CONFIG),
    Venus300NumberSpec(FREECOOLING_OFF_MONTH, "freecooling_off_month", 1, 12, 1, None, EntityCategory.CONFIG),
    Venus300NumberSpec(FREECOOLING_OFF_DAY, "freecooling_off_day", 1, 31, 1, None, EntityCategory.CONFIG),
    Venus300NumberSpec(FREECOOLING_OFF_HOUR, "freecooling_off_hour", 0, 23, 1, None, EntityCategory.CONFIG),
    Venus300NumberSpec(FREECOOLING_OFF_MIN, "freecooling_off_min", 0, 59, 1, None, EntityCategory.CONFIG),
    # doc 25020 "FilterMaxHours": the actual configurable filter lifetime.
    # inlet_filter_life / outlet_filter_life count down against this (when
    # filter_working_hours_enabled is on) toward 0%, at which point replace
    # the filters and press the "Reset filter timer" button.
    Venus300NumberSpec(
        FILTER_MAX_HOURS,
        "filter_max_hours",
        200,
        3000,
        10,
        UnitOfTime.HOURS,
        EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Venus300ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Venus 300 numbers."""
    coordinator = entry.runtime_data
    async_add_entities(Venus300Number(coordinator, entry, spec) for spec in NUMBERS)


class Venus300Number(Venus300Entity, NumberEntity):
    """A writable holding register exposed as a number."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinator: Venus300Coordinator,
        entry: Venus300ConfigEntry,
        spec: Venus300NumberSpec,
    ) -> None:
        """Set up the number entity for one register."""
        super().__init__(coordinator, entry)
        self._spec = spec
        self._attr_translation_key = spec.translation_key
        self._attr_unique_id = f"{entry.entry_id}_{spec.register.key}"
        self._attr_native_min_value = spec.native_min_value
        self._attr_native_max_value = spec.native_max_value
        self._attr_native_step = spec.native_step
        self._attr_native_unit_of_measurement = spec.native_unit_of_measurement
        self._attr_entity_category = spec.entity_category

    @property
    def native_value(self) -> float | None:
        """Return the register's current, decoded value."""
        return self.coordinator.data.get(self._spec.register.key)

    async def async_set_native_value(self, value: float) -> None:
        """Write a new value and refresh state from the unit."""
        raw = encode_value(self._spec.register, value)
        try:
            await self.coordinator.client.write_register(self._spec.register, raw)
        except Venus300ModbusError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
