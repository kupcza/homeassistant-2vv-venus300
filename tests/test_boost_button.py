"""Tests for the Boost button's snapshot/restart/restore-on-end logic.

Bypasses __init__/hass/coordinator (not needed for this logic) by
constructing the entity without them and stubbing async_call_later and the
Modbus client, then exercising press/repeat-press/auto-off directly.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from custom_components.venus300 import button
from custom_components.venus300.registers import BOOST_MODE, FAN_POWER_SETPOINT, SWITCH_ON


class _FakeCoordinator:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.client = AsyncMock()
        self.async_request_refresh = AsyncMock()
        self.boost_timer_minutes = 5


def _make_button(monkeypatch: pytest.MonkeyPatch, data: dict) -> button.Venus300BoostButton:
    monkeypatch.setattr(button, "async_call_later", lambda hass, delay, cb: (lambda: None))

    boost = object.__new__(button.Venus300BoostButton)
    boost.hass = object()
    boost.coordinator = _FakeCoordinator(data)
    boost._active = False
    boost._cancel_timer = None
    boost._pre_boost_state = None
    return boost


def test_first_press_snapshots_state_and_activates_boost(monkeypatch: pytest.MonkeyPatch):
    boost = _make_button(monkeypatch, {SWITCH_ON.key: 1, FAN_POWER_SETPOINT.key: 45.0})

    asyncio.run(boost.async_press())

    assert boost._active is True
    assert boost._pre_boost_state == {SWITCH_ON.key: 1, FAN_POWER_SETPOINT.key: 45.0}
    boost.coordinator.client.write_register.assert_awaited_once_with(BOOST_MODE, 1)


def test_second_press_while_active_restarts_timer_without_resnapshotting(
    monkeypatch: pytest.MonkeyPatch,
):
    boost = _make_button(monkeypatch, {SWITCH_ON.key: 1, FAN_POWER_SETPOINT.key: 45.0})
    asyncio.run(boost.async_press())
    boost.coordinator.client.write_register.reset_mock()

    # Simulate the unit's own state having drifted while boost was running --
    # a re-snapshot here would incorrectly capture the *boosted* state.
    boost.coordinator.data = {SWITCH_ON.key: 1, FAN_POWER_SETPOINT.key: 100.0}
    asyncio.run(boost.async_press())

    assert boost._active is True
    assert boost._pre_boost_state == {SWITCH_ON.key: 1, FAN_POWER_SETPOINT.key: 45.0}
    boost.coordinator.client.write_register.assert_not_awaited()  # no second BOOST_MODE=1 write


def test_auto_off_restores_snapshot_after_timer_elapses(monkeypatch: pytest.MonkeyPatch):
    boost = _make_button(monkeypatch, {SWITCH_ON.key: 0, FAN_POWER_SETPOINT.key: 20.0})
    asyncio.run(boost.async_press())
    boost.coordinator.client.write_register.reset_mock()

    asyncio.run(boost._async_auto_off(None))

    assert boost._active is False
    assert boost._pre_boost_state is None
    calls = boost.coordinator.client.write_register.call_args_list
    assert calls[0].args == (BOOST_MODE, 0)
    written = {call.args[0].key: call.args[1] for call in calls[1:]}
    assert written[SWITCH_ON.key] == 0
    assert written[FAN_POWER_SETPOINT.key] == 200  # 20.0% encoded at scale 0.1
