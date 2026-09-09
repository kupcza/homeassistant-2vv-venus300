"""Documented bit-level meanings for the Venus 300's raw status/error words.

Sourced from MODBUS_V1_FW166_167.xlsx, sheet STATUS_AHU:
  - GLOBAL_STATUS_RAW  (doc 15000, "Unit global status1")
  - GLOBAL_STATUS2_RAW (doc 15001, "Unit global status2")
  - SW_ERROR1_RAW       (doc 15002, "Software error1")
  - SW_ERROR2_RAW       (doc 15003, "Software error2")

Bits documented with Min==Max==0 (CAV/VAV on this firmware) are omitted, as
are bits for hardware this unit doesn't have (water heaters, AQS sensor —
see the note at the top of modbus.yaml). bit0 (ON/OFF) of GLOBAL_STATUS_RAW
is also omitted: it duplicates the `power` switch, which already reads the
same state from the SHARE control block.

bit8 (Freecooling) reflects the unit's real, resulting state, which can
legitimately differ from SHARE's FreecoolingMode *request* register
(21010/doc 21011, registers.py's FREECOOLING_MODE) — confirmed by live
testing that writing that register doesn't reliably work anyway, which is
why it isn't exposed as an entity at all. Whether the unit actually enters
freecooling depends on FREECOOLING_ENABLE and the allowed-hours window in
FREECOOLING_BLOCK (see registers.py and freecooling_conditions.py).
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from .registers import GLOBAL_STATUS2_RAW, GLOBAL_STATUS_RAW, Register, SW_ERROR1_RAW, SW_ERROR2_RAW


@dataclass(frozen=True)
class BitSensorSpec:
    """One documented bit of a status/error register, as a binary sensor."""

    register: Register
    bit: int
    translation_key: str
    device_class: BinarySensorDeviceClass | None = None


STATUS1_BITS = (
    BitSensorSpec(GLOBAL_STATUS_RAW, 1, "manual_mode_active"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 4, "dcv_mode_active"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 5, "fire_mode_active", BinarySensorDeviceClass.SAFETY),
    BitSensorSpec(GLOBAL_STATUS_RAW, 6, "boost_mode_active"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 7, "nobody_mode_active"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 8, "freecooling_active", BinarySensorDeviceClass.RUNNING),
    BitSensorSpec(GLOBAL_STATUS_RAW, 9, "timeswitch_mode_active"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 10, "calibration_active"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 11, "cooldown_active"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 12, "direct_control_active"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 13, "filter_change_due"),
    BitSensorSpec(GLOBAL_STATUS_RAW, 14, "fw_update_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(GLOBAL_STATUS_RAW, 15, "fw_update_active", BinarySensorDeviceClass.RUNNING),
)

STATUS2_BITS = (
    BitSensorSpec(GLOBAL_STATUS2_RAW, 4, "recirculation_active"),
    BitSensorSpec(GLOBAL_STATUS2_RAW, 5, "simulation_active"),
    BitSensorSpec(GLOBAL_STATUS2_RAW, 6, "prefreecooling_active"),
    BitSensorSpec(GLOBAL_STATUS2_RAW, 7, "temp_flow_reduction_active"),
    BitSensorSpec(GLOBAL_STATUS2_RAW, 8, "passive_house_restriction_active"),
    BitSensorSpec(GLOBAL_STATUS2_RAW, 9, "adb_active"),
    BitSensorSpec(GLOBAL_STATUS2_RAW, 10, "vavc4_active"),
    BitSensorSpec(GLOBAL_STATUS2_RAW, 11, "pco_active"),
)
# bits 0-3 (water heater antifreeze / hot-water wait / supply-air wait / WCO)
# omitted: no water heater fitted.

ERROR1_BITS = (
    BitSensorSpec(SW_ERROR1_RAW, 0, "fan_inlet_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 1, "fan_outlet_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 2, "filter_inlet_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 3, "filter_outlet_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 4, "filter_inlet_warning", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 5, "filter_outlet_warning", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 11, "rotary_wheel_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 12, "adb_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 13, "dx_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR1_RAW, 14, "dx_defrost", BinarySensorDeviceClass.RUNNING),
    BitSensorSpec(SW_ERROR1_RAW, 15, "condensate_drain", BinarySensorDeviceClass.PROBLEM),
)
# bits 6-9 (pre/postheater 1+2 errors) and bit10 (AQS sensor error) omitted:
# no heaters and no AQS sensor fitted.

ERROR2_BITS = (
    BitSensorSpec(SW_ERROR2_RAW, 0, "g_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR2_RAW, 1, "global_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR2_RAW, 2, "k_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR2_RAW, 3, "filter_info_flag", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR2_RAW, 4, "cfg_file_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR2_RAW, 5, "filter_hepa_error", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR2_RAW, 6, "filter_hepa_warning", BinarySensorDeviceClass.PROBLEM),
    BitSensorSpec(SW_ERROR2_RAW, 7, "ibus_gateway_error", BinarySensorDeviceClass.PROBLEM),
)

ALL_BITS = STATUS1_BITS + STATUS2_BITS + ERROR1_BITS + ERROR2_BITS
