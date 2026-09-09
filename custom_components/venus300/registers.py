"""Declarative Modbus register map for the 2VV Venus 300 (AirGenio) HRU.

Addresses here are wire addresses (0-based), matching what modbus.yaml used:
already offset by -1 from the "PLC Addresses - BASE1" numbers documented in
MODBUS_V1_FW166_167.xlsx. Every register comment below carries the original
1-based doc address for cross-checking against that sheet.
"""

from __future__ import annotations

from dataclasses import dataclass


class RegisterKind:
    """Modbus function group a register belongs to."""

    INPUT = "input"
    HOLDING = "holding"


@dataclass(frozen=True)
class Register:
    """A single logical value mapped to one 16-bit Modbus register."""

    key: str
    address: int
    kind: str
    signed: bool = False
    scale: float = 1.0
    writable: bool = False


@dataclass(frozen=True)
class ReadBlock:
    """A contiguous run of registers read in a single Modbus transaction."""

    kind: str
    start: int
    count: int
    registers: tuple[Register, ...]

    def offset_of(self, register: Register) -> int:
        """Return this register's position within the block's result list."""
        return register.address - self.start


def decode_value(raw: int, register: Register) -> int | float:
    """Turn a raw 16-bit register value into its real-world value."""
    value = raw
    if register.signed and value >= 0x8000:
        value -= 0x10000
    if register.scale != 1.0:
        return round(value * register.scale, 2)
    return value


def encode_value(register: Register, value: float) -> int:
    """Turn a real-world value back into a raw 16-bit register value."""
    if register.scale != 1.0:
        return round(value / register.scale)
    return int(value)


# ---- Status / monitoring block (Input Registers, function 0x04) ----
# One read covers 14999..15044 (46 registers) in a single transaction.

GLOBAL_STATUS_RAW = Register("global_status_raw", 14999, RegisterKind.INPUT)  # doc 15000
GLOBAL_STATUS2_RAW = Register("global_status2_raw", 15000, RegisterKind.INPUT)  # doc 15001
SW_ERROR1_RAW = Register("sw_error1_raw", 15001, RegisterKind.INPUT)  # doc 15002
SW_ERROR2_RAW = Register("sw_error2_raw", 15002, RegisterKind.INPUT)  # doc 15003
INLET_FAN_POWER = Register(
    "inlet_fan_power", 15012, RegisterKind.INPUT, scale=0.1
)  # doc 15013, AirFlowInletFanManual, ‰ -> %
OUTLET_FAN_POWER = Register(
    "outlet_fan_power", 15013, RegisterKind.INPUT, scale=0.1
)  # doc 15014, AirFlowOutletFanManual, ‰ -> %
TEMP_OUTSIDE_TO_UNIT = Register(
    "temperature_outside_to_unit", 15016, RegisterKind.INPUT, signed=True, scale=0.1
)  # doc 15017, TempEXT1
TEMP_UNIT_TO_HOUSE = Register(
    "temperature_unit_to_house", 15017, RegisterKind.INPUT, signed=True, scale=0.1
)  # doc 15018, TempEXT2
TEMP_HOUSE_TO_UNIT = Register(
    "temperature_house_to_unit", 15021, RegisterKind.INPUT, signed=True, scale=0.1
)  # doc 15022, TempINT1
TEMP_UNIT_TO_OUTSIDE = Register(
    "temperature_unit_to_outside", 15022, RegisterKind.INPUT, signed=True, scale=0.1
)  # doc 15023, TempINT2
FILTER_PRESSURE_INLET = Register(
    "filter_pressure_inlet", 15026, RegisterKind.INPUT
)  # doc 15027, SensorFilterIn, Pa (only meaningful if a physical dP sensor is fitted)
FILTER_PRESSURE_OUTLET = Register(
    "filter_pressure_outlet", 15027, RegisterKind.INPUT
)  # doc 15028, SensorFilterOut, Pa (only meaningful if a physical dP sensor is fitted)
BYPASS_POSITION = Register("bypass_position", 15040, RegisterKind.INPUT)  # doc 15041
INLET_FILTER_LIFE = Register("inlet_filter_life", 15043, RegisterKind.INPUT)  # doc 15044
OUTLET_FILTER_LIFE = Register("outlet_filter_life", 15044, RegisterKind.INPUT)  # doc 15045
HEPA_FILTER_PRESSURE = Register(
    "hepa_filter_pressure", 15046, RegisterKind.INPUT
)  # doc 15047, SensorFilterhEPA, Pa (only meaningful if a HEPA stage is fitted)
HEPA_FILTER_LIFE = Register(
    "hepa_filter_life", 15047, RegisterKind.INPUT
)  # doc 15048, HepaFilterPercent (only meaningful if a HEPA stage is fitted)

STATUS_BLOCK = ReadBlock(
    RegisterKind.INPUT,
    14999,
    49,
    (
        GLOBAL_STATUS_RAW,
        GLOBAL_STATUS2_RAW,
        SW_ERROR1_RAW,
        SW_ERROR2_RAW,
        INLET_FAN_POWER,
        OUTLET_FAN_POWER,
        TEMP_OUTSIDE_TO_UNIT,
        TEMP_UNIT_TO_HOUSE,
        TEMP_HOUSE_TO_UNIT,
        TEMP_UNIT_TO_OUTSIDE,
        FILTER_PRESSURE_INLET,
        FILTER_PRESSURE_OUTLET,
        BYPASS_POSITION,
        INLET_FILTER_LIFE,
        OUTLET_FILTER_LIFE,
        HEPA_FILTER_PRESSURE,
        HEPA_FILTER_LIFE,
    ),
)

MODBUS_PORT = Register("modbus_port", 16020, RegisterKind.INPUT)  # doc 16021, INFO: ModbusPort
PORT_BLOCK = ReadBlock(RegisterKind.INPUT, 16020, 1, (MODBUS_PORT,))

# ---- Control block (Holding Registers, SHARE sheet) ----
# One read/write-relevant read covers 21000..21002 in a single transaction.

SWITCH_ON = Register("switch_on", 21000, RegisterKind.HOLDING, writable=True)  # doc 21001
FAN_POWER_SETPOINT = Register(
    "fan_power_setpoint", 21001, RegisterKind.HOLDING, scale=0.1, writable=True
)  # doc 21002, AirFlowManual, ‰ -> %
TEMPERATURE_SETPOINT = Register(
    "temperature_setpoint", 21002, RegisterKind.HOLDING, writable=True
)  # doc 21003, target house temp

CONTROL_BLOCK = ReadBlock(
    RegisterKind.HOLDING, 21000, 3, (SWITCH_ON, FAN_POWER_SETPOINT, TEMPERATURE_SETPOINT)
)

# ---- Freecooling + Boost timer config block (Holding Registers, SERVICE) ----
# SHARE's FreecoolingMode (below) only *requests* freecooling. Whether the
# unit actually engages it also depends on this block: a master enable, an
# outdoor-temperature threshold, and a daily/seasonal allowed-hours window.
# BoostTimer happens to sit immediately before these on the SERVICE sheet,
# so it's fetched in the same transaction; it's otherwise unrelated to
# freecooling — see its own comment below.
# One read covers 20011..20023 (13 registers) in a single transaction.

BOOST_TIMER = Register(
    "boost_timer", 20011, RegisterKind.HOLDING, writable=True
)  # doc 20012, SERVICE: BoostTimer (minutes) — the UNIT's own boost
# auto-off duration, applied no matter what activates boost: the physical
# DI-5 wired switch, the control panel, or Modbus. Distinct from
# number.boost_timer_minutes (switch.py), which only times out
# button.boost's own Home-Assistant-managed activation.
FREECOOLING_ENABLE = Register(
    "freecooling_enable", 20013, RegisterKind.HOLDING, writable=True
)  # doc 20014, SERVICE: FreecoolingEnable, master enable for freecooling
FREECOOLING_AIRFLOW = Register(
    "freecooling_airflow", 20014, RegisterKind.HOLDING, writable=True
)  # doc 20015, SERVICE: FreecoolingAirFlow, % (50-100)
FREECOOLING_TEMP_THRESHOLD = Register(
    "freecooling_temp_threshold", 20015, RegisterKind.HOLDING, writable=True
)  # doc 20016, SERVICE: FreecoolingTempEU, °C (12-25)
FREECOOLING_ON_MONTH = Register(
    "freecooling_on_month", 20016, RegisterKind.HOLDING, writable=True
)  # doc 20017, SERVICE: FreecoolingOnMonth, season start month (1-12)
FREECOOLING_ON_DAY = Register(
    "freecooling_on_day", 20017, RegisterKind.HOLDING, writable=True
)  # doc 20018, SERVICE: FreecoolingOnDay, season start day (1-31)
FREECOOLING_ON_HOUR = Register(
    "freecooling_on_hour", 20018, RegisterKind.HOLDING, writable=True
)  # doc 20019, SERVICE: FreecoolingOnHour, daily allowed-from hour (0-23)
FREECOOLING_ON_MIN = Register(
    "freecooling_on_min", 20019, RegisterKind.HOLDING, writable=True
)  # doc 20020, SERVICE: FreecoolingOnMin, daily allowed-from minute (0-59)
FREECOOLING_OFF_MONTH = Register(
    "freecooling_off_month", 20020, RegisterKind.HOLDING, writable=True
)  # doc 20021, SERVICE: FreecoolingOffMonth, season end month (1-12)
FREECOOLING_OFF_DAY = Register(
    "freecooling_off_day", 20021, RegisterKind.HOLDING, writable=True
)  # doc 20022, SERVICE: FreecoolingOffDay, season end day (1-31)
FREECOOLING_OFF_HOUR = Register(
    "freecooling_off_hour", 20022, RegisterKind.HOLDING, writable=True
)  # doc 20023, SERVICE: FreecoolingOffHour, daily allowed-until hour (0-23)
FREECOOLING_OFF_MIN = Register(
    "freecooling_off_min", 20023, RegisterKind.HOLDING, writable=True
)  # doc 20024, SERVICE: FreecoolingOffMin, daily allowed-until minute (0-59)

FREECOOLING_BLOCK = ReadBlock(
    RegisterKind.HOLDING,
    20011,
    13,
    (
        BOOST_TIMER,
        FREECOOLING_ENABLE,
        FREECOOLING_AIRFLOW,
        FREECOOLING_TEMP_THRESHOLD,
        FREECOOLING_ON_MONTH,
        FREECOOLING_ON_DAY,
        FREECOOLING_ON_HOUR,
        FREECOOLING_ON_MIN,
        FREECOOLING_OFF_MONTH,
        FREECOOLING_OFF_DAY,
        FREECOOLING_OFF_HOUR,
        FREECOOLING_OFF_MIN,
    ),
)

# ---- Filter lifetime config block (Holding Registers, SERVICE_HARD sheet) ----
# FilterMaxHours is the actual configurable filter lifetime; the % sensors
# (INLET_FILTER_LIFE / OUTLET_FILTER_LIFE above) count down against it (when
# hour-based tracking is enabled) or against a pressure-sensor reading.
# One read covers 25018..25019 (2 registers) in a single transaction.

FILTER_WORKING_HOURS_ENABLED = Register(
    "filter_working_hours_enabled", 25018, RegisterKind.HOLDING, writable=True
)  # doc 25019, SERVICE_HARD: FilterWoringHours, hour-based tracking on/off
FILTER_MAX_HOURS = Register(
    "filter_max_hours", 25019, RegisterKind.HOLDING, writable=True
)  # doc 25020, SERVICE_HARD: FilterMaxHours, lifetime in hours (200-3000)

FILTER_CONFIG_BLOCK = ReadBlock(
    RegisterKind.HOLDING, 25018, 2, (FILTER_WORKING_HOURS_ENABLED, FILTER_MAX_HOURS)
)

# ---- Isolated holding registers, each its own transaction ----

BOOST_MODE = Register(
    "boost_mode", 21008, RegisterKind.HOLDING, writable=True
)  # doc 21009, SHARE: BoostMode — activates the unit's own boost airflow.
# Write-only from our side: button.boost manages its own on/off state
# in Home Assistant (see switch.py), so this isn't polled every cycle.
FREECOOLING_MODE = Register(
    "freecooling_mode", 21010, RegisterKind.HOLDING, writable=True
)  # doc 21011, SHARE: FreecoolingMode, manual activation request.
# CONFIRMED (live testing against a real unit) that writing this does NOT
# reliably override the unit's own scheduler: the write succeeds at the
# protocol level, but an immediate readback already shows 0 again, even
# with freecooling_enable/threshold/season/hour-window all satisfied. The
# automatic scheduler (see the other freecooling_* registers) is what
# actually works — see README's "Freecooling: what actually controls it".
FILTER_CLOGGED_TIMER_RESET = Register(
    "filter_clogged_timer_reset", 21015, RegisterKind.HOLDING, writable=True
)  # doc 21016, SHARE: FilterClogedTimerReset — write 1 after replacing a filter
BYPASS_TYPE_RAW = Register(
    "bypass_type_raw", 10128, RegisterKind.HOLDING
)  # doc 10129, FACTORY_SET: Bypass
FILTER_DISABLE_STATUS_RAW = Register(
    "filter_disable_status_raw", 10162, RegisterKind.HOLDING
)  # doc 10163, FACTORY_SET: FilterDisableStatus
BYPASS_TEMP_THRESHOLD = Register(
    "bypass_temp_threshold", 20036, RegisterKind.HOLDING, writable=True
)  # doc 20037, SERVICE: BypassTemperature
VENTILATION_MODE_RAW = Register(
    "ventilation_mode_raw", 24999, RegisterKind.HOLDING
)  # doc 25000, SERVICE_HARD: VentilationMode
TEMP_SENSOR_SELECTION_RAW = Register(
    "temp_sensor_selection_raw", 25008, RegisterKind.HOLDING
)  # doc 25009, SERVICE_HARD: TempSensorSelection

SINGLE_HOLDING_REGISTERS = (
    FREECOOLING_MODE,
    BYPASS_TYPE_RAW,
    FILTER_DISABLE_STATUS_RAW,
    BYPASS_TEMP_THRESHOLD,
    VENTILATION_MODE_RAW,
    TEMP_SENSOR_SELECTION_RAW,
)

ALL_BLOCKS = (STATUS_BLOCK, PORT_BLOCK, CONTROL_BLOCK, FREECOOLING_BLOCK, FILTER_CONFIG_BLOCK)

# ---- Enum decodings for read-only raw registers ----
# Bit-level meanings of GLOBAL_STATUS_RAW / GLOBAL_STATUS2_RAW / SW_ERROR1_RAW
# / SW_ERROR2_RAW are documented in MODBUS_V1_FW166_167.xlsx, sheet
# STATUS_AHU, and decoded per-bit in bitfields.py. The raw integers are also
# kept as diagnostic sensors below for troubleshooting.

BYPASS_TYPE_OPTIONS = {0: "none", 1: "stepless_0_10v", 2: "open_close"}
FILTER_DISABLE_STATUS_OPTIONS = {0: "all_active", 1: "inlet_disabled", 2: "outlet_disabled"}
TEMP_SENSOR_SELECTION_OPTIONS = {0: "supply_duct", 1: "extract_duct", 2: "room"}
VENTILATION_MODE_OPTIONS = {
    0: "manual",
    1: "dcv",
    2: "cav",
    3: "vav",
    4: "vavc4",
    5: "pco",
}
