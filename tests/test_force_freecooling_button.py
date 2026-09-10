"""Tests for the Force Freecooling button's snapshot/re-arm/restore logic.

Bypasses __init__/hass/coordinator (not needed for this logic) by
constructing the entity without them and stubbing async_call_later and the
Modbus client, mirroring test_boost_button.py's approach.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from custom_components.venus300 import button, freecooling_force
from custom_components.venus300.registers import (
    ACTUAL_HOUR,
    ACTUAL_MIN,
    FREECOOLING_ON_HOUR,
    FREECOOLING_ON_MIN,
)


def test_next_minute_normal_case():
    assert freecooling_force.next_minute(14, 30) == (14, 31)


def test_next_minute_wraps_minute():
    assert freecooling_force.next_minute(14, 59) == (15, 0)


def test_next_minute_wraps_hour_at_midnight():
    assert freecooling_force.next_minute(23, 59) == (0, 0)


class _FakeCoordinator:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.client = AsyncMock()
        self.async_request_refresh = AsyncMock()


def _make_button(
    monkeypatch: pytest.MonkeyPatch, data: dict
) -> button.Venus300ForceFreecoolingButton:
    monkeypatch.setattr(button, "async_call_later", lambda hass, delay, cb: (lambda: None))

    force = object.__new__(button.Venus300ForceFreecoolingButton)
    force.hass = object()
    force.coordinator = _FakeCoordinator(data)
    force._cancel_timer = None
    force._pre_force_state = None
    return force


def _data(actual_hour: int, actual_min: int, on_hour: int, on_min: int) -> dict:
    return {
        ACTUAL_HOUR.key: actual_hour,
        ACTUAL_MIN.key: actual_min,
        FREECOOLING_ON_HOUR.key: on_hour,
        FREECOOLING_ON_MIN.key: on_min,
    }


def test_first_press_snapshots_start_time_and_writes_now_plus_one_minute(
    monkeypatch: pytest.MonkeyPatch,
):
    force = _make_button(monkeypatch, _data(13, 45, 22, 0))

    asyncio.run(force.async_press())

    assert force._pre_force_state == {FREECOOLING_ON_HOUR.key: 22, FREECOOLING_ON_MIN.key: 0}
    calls = force.coordinator.client.write_register.call_args_list
    written = {call.args[0].key: call.args[1] for call in calls}
    assert written == {FREECOOLING_ON_HOUR.key: 13, FREECOOLING_ON_MIN.key: 46}


def test_second_press_before_restore_rearms_without_resnapshotting(
    monkeypatch: pytest.MonkeyPatch,
):
    force = _make_button(monkeypatch, _data(13, 45, 22, 0))
    asyncio.run(force.async_press())
    force.coordinator.client.write_register.reset_mock()

    # Simulate the unit's clock (and the start time we just wrote) having moved on.
    force.coordinator.data = _data(13, 46, 13, 46)
    asyncio.run(force.async_press())

    assert force._pre_force_state == {FREECOOLING_ON_HOUR.key: 22, FREECOOLING_ON_MIN.key: 0}
    calls = force.coordinator.client.write_register.call_args_list
    written = {call.args[0].key: call.args[1] for call in calls}
    assert written == {FREECOOLING_ON_HOUR.key: 13, FREECOOLING_ON_MIN.key: 47}


def test_restore_writes_back_original_start_time_after_delay(monkeypatch: pytest.MonkeyPatch):
    force = _make_button(monkeypatch, _data(13, 45, 22, 30))
    asyncio.run(force.async_press())
    force.coordinator.client.write_register.reset_mock()

    asyncio.run(force._async_restore(None))

    assert force._pre_force_state is None
    calls = force.coordinator.client.write_register.call_args_list
    written = {call.args[0].key: call.args[1] for call in calls}
    assert written == {FREECOOLING_ON_HOUR.key: 22, FREECOOLING_ON_MIN.key: 30}
