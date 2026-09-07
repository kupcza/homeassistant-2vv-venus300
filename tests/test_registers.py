"""Tests for the declarative register map."""

from custom_components.venus300 import registers


def test_block_offsets_are_within_range():
    for block in registers.ALL_BLOCKS:
        for register in block.registers:
            offset = block.offset_of(register)
            assert 0 <= offset < block.count, (
                f"{register.key} offset {offset} out of range for block "
                f"{block.kind} {block.start}-{block.start + block.count - 1}"
            )


def test_block_registers_are_within_declared_address_range():
    for block in registers.ALL_BLOCKS:
        end = block.start + block.count - 1
        for register in block.registers:
            assert block.start <= register.address <= end


def test_all_register_keys_are_unique():
    all_registers = []
    for block in registers.ALL_BLOCKS:
        all_registers.extend(block.registers)
    all_registers.extend(registers.SINGLE_HOLDING_REGISTERS)
    keys = [r.key for r in all_registers]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert len(keys) == len(set(keys)), f"duplicate register keys: {dupes}"


def test_encode_decode_roundtrip_for_scaled_register():
    register = registers.FAN_POWER_SETPOINT
    for value in (0, 12.5, 45, 100):
        raw = registers.encode_value(register, value)
        assert registers.decode_value(raw, register) == value


def test_decode_signed_negative_temperature():
    register = registers.TEMP_OUTSIDE_TO_UNIT
    raw = 0x10000 - 55  # two's complement of -55 -> -5.5 C at scale 0.1
    assert registers.decode_value(raw, register) == -5.5


def test_control_and_freecooling_writable_flags():
    for register in (
        registers.SWITCH_ON,
        registers.FREECOOLING_MODE,
        registers.FREECOOLING_ENABLE,
        registers.FAN_POWER_SETPOINT,
        registers.TEMPERATURE_SETPOINT,
        registers.BYPASS_TEMP_THRESHOLD,
    ):
        assert register.writable, register.key

    for register in (
        registers.MODBUS_PORT,
        registers.GLOBAL_STATUS_RAW,
        registers.GLOBAL_STATUS2_RAW,
        registers.SW_ERROR1_RAW,
        registers.SW_ERROR2_RAW,
        registers.VENTILATION_MODE_RAW,
        registers.TEMP_SENSOR_SELECTION_RAW,
        registers.BYPASS_TYPE_RAW,
    ):
        assert not register.writable, register.key


def test_enum_option_values_match_documented_bounds():
    assert set(registers.BYPASS_TYPE_OPTIONS) == {0, 1, 2}
    assert set(registers.TEMP_SENSOR_SELECTION_OPTIONS) == {0, 1, 2}
    assert set(registers.VENTILATION_MODE_OPTIONS) == {0, 1, 2, 3, 4, 5}
