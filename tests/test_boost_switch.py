"""Tests for the Boost switch's snapshot/restore-on-end safety net.

Bypasses __init__/hass/coordinator (not needed for this logic) by
constructing the entity without them and stubbing async_call_later and the
Modbus client, then exercising the on/off/auto-off paths directly.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from custom_components.venus300 import switch
from custom_components.venus300.registers import BOOST_MODE, FAN_POWER_SETPOINT, SWITCH_ON


class _FakeCoordinator:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.client = AsyncMock()
        self.async_request_refresh = AsyncMock()
        self.boost_timer_minutes = 5


def _make_switch(monkeypatch: pytest.MonkeyPatch, data: dict) -> switch.Venus300BoostSwitch:
    monkeypatch.setattr(switch, "async_call_later", lambda hass, delay, cb: (lambda: None))

    boost = object.__new__(switch.Venus300BoostSwitch)
    boost.hass = object()
    boost.coordinator = _FakeCoordinator(data)
    boost._attr_is_on = False
    boost._cancel_timer = None
    boost._pre_boost_state = None
    boost.async_write_ha_state = lambda: None
    return boost


def test_turn_on_snapshots_state_and_writes_boost_mode_on(monkeypatch: pytest.MonkeyPatch):
    boost = _make_switch(monkeypatch, {SWITCH_ON.key: 1, FAN_POWER_SETPOINT.key: 45.0})

    asyncio.run(boost.async_turn_on())

    assert boost.is_on is True
    assert boost._pre_boost_state == {SWITCH_ON.key: 1, FAN_POWER_SETPOINT.key: 45.0}
    boost.coordinator.client.write_register.assert_awaited_once_with(BOOST_MODE, 1)


def test_turn_off_writes_boost_mode_off_and_restores_snapshot(monkeypatch: pytest.MonkeyPatch):
    boost = _make_switch(monkeypatch, {SWITCH_ON.key: 1, FAN_POWER_SETPOINT.key: 45.0})
    asyncio.run(boost.async_turn_on())
    boost.coordinator.client.write_register.reset_mock()

    asyncio.run(boost.async_turn_off())

    assert boost.is_on is False
    assert boost._pre_boost_state is None
    calls = boost.coordinator.client.write_register.call_args_list
    assert calls[0].args == (BOOST_MODE, 0)
    written = {call.args[0].key: call.args[1] for call in calls[1:]}
    assert written[SWITCH_ON.key] == 1
    assert written[FAN_POWER_SETPOINT.key] == 450  # 45.0% encoded at scale 0.1


def test_auto_off_restores_snapshot_after_timer_elapses(monkeypatch: pytest.MonkeyPatch):
    boost = _make_switch(monkeypatch, {SWITCH_ON.key: 0, FAN_POWER_SETPOINT.key: 20.0})
    asyncio.run(boost.async_turn_on())
    boost.coordinator.client.write_register.reset_mock()

    asyncio.run(boost._async_auto_off(None))

    assert boost.is_on is False
    assert boost._pre_boost_state is None
    calls = boost.coordinator.client.write_register.call_args_list
    assert calls[0].args == (BOOST_MODE, 0)
    written = {call.args[0].key: call.args[1] for call in calls[1:]}
    assert written[SWITCH_ON.key] == 0
    assert written[FAN_POWER_SETPOINT.key] == 200  # 20.0% encoded at scale 0.1
