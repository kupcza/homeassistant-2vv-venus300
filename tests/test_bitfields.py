"""Tests for status/error bitfield decoding."""

from custom_components.venus300 import bitfields
from custom_components.venus300.registers import GLOBAL_STATUS_RAW


def test_bit_indices_are_valid_for_a_16_bit_register():
    for spec in bitfields.ALL_BITS:
        assert 0 <= spec.bit <= 15, spec.translation_key


def test_no_duplicate_register_bit_pairs():
    pairs = [(spec.register.key, spec.bit) for spec in bitfields.ALL_BITS]
    assert len(pairs) == len(set(pairs))


def test_no_duplicate_translation_keys():
    keys = [spec.translation_key for spec in bitfields.ALL_BITS]
    assert len(keys) == len(set(keys))


def test_freecooling_active_is_tracked_separately_from_the_request_switch():
    """Regression test.

    bit 8 of GLOBAL_STATUS_RAW is the unit's *actual* freecooling status,
    distinct from the `freecooling_mode` switch (which only writes a
    request register). Losing this bit previously masked why freecooling
    appeared to do nothing.
    """
    matches = [
        spec
        for spec in bitfields.ALL_BITS
        if spec.register is GLOBAL_STATUS_RAW and spec.bit == 8
    ]
    assert len(matches) == 1
    assert matches[0].translation_key == "freecooling_active"
