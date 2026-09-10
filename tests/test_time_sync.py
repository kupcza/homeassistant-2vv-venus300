"""Tests for keeping the unit's clock synced to Home Assistant's.

Bypasses a real Venus300ModbusClient (not needed for this logic) with an
AsyncMock, and controls the clock via monkeypatching time_sync's own
dt_util reference, so these run without any Modbus connection or hass.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from custom_components.venus300 import time_sync
from custom_components.venus300.registers import (
    ACTUAL_DAY,
    ACTUAL_HOUR,
    ACTUAL_MIN,
    ACTUAL_MONTH,
    ACTUAL_SEC,
    ACTUAL_YEAR,
    SET_DAY,
    SET_DAY_OF_WEEK,
    SET_HOUR,
    SET_MIN,
    SET_MONTH,
    SET_SEC,
    SET_TIME_FLAG,
    SET_YEAR,
)


def _unit_time_data(dt: datetime) -> dict:
    return {
        ACTUAL_YEAR.key: dt.year,
        ACTUAL_MONTH.key: dt.month,
        ACTUAL_DAY.key: dt.day,
        ACTUAL_HOUR.key: dt.hour,
        ACTUAL_MIN.key: dt.minute,
        ACTUAL_SEC.key: dt.second,
    }


def _patch_now(monkeypatch: pytest.MonkeyPatch, now: datetime) -> None:
    monkeypatch.setattr(time_sync.dt_util, "now", lambda: now)


def test_current_drift_seconds_is_near_zero_when_synced(monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 9, 10, 14, 0, 0)
    _patch_now(monkeypatch, now)

    assert time_sync.current_drift_seconds(_unit_time_data(now)) == 0.0


def test_current_drift_seconds_positive_when_unit_ahead(monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 9, 10, 14, 0, 0)
    unit_time = datetime(2026, 9, 10, 14, 5, 0)  # 5 minutes ahead
    _patch_now(monkeypatch, now)

    assert time_sync.current_drift_seconds(_unit_time_data(unit_time)) == 300.0


def test_current_drift_seconds_negative_when_unit_behind(monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 9, 10, 14, 5, 0)
    unit_time = datetime(2026, 9, 10, 14, 0, 0)  # 5 minutes behind
    _patch_now(monkeypatch, now)

    assert time_sync.current_drift_seconds(_unit_time_data(unit_time)) == -300.0


def test_current_drift_seconds_none_when_data_incomplete():
    assert time_sync.current_drift_seconds({}) is None


def test_async_force_sync_writes_every_field_and_commits(monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 9, 10, 14, 18, 49)  # Thursday
    _patch_now(monkeypatch, now)
    client = AsyncMock()

    asyncio.run(time_sync.async_force_sync(client))

    calls = client.write_register.call_args_list
    written = {call.args[0].key: call.args[1] for call in calls}
    assert written == {
        SET_YEAR.key: 2026,
        SET_MONTH.key: 9,
        SET_DAY.key: 10,
        SET_DAY_OF_WEEK.key: 4,  # Thursday, ISO weekday
        SET_HOUR.key: 14,
        SET_MIN.key: 18,
        SET_SEC.key: 49,
        SET_TIME_FLAG.key: 1,
    }
    # SET_TIME_FLAG must be committed last, after every field is written.
    assert calls[-1].args[0].key == SET_TIME_FLAG.key


def test_async_sync_if_needed_skips_write_when_within_threshold(monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 9, 10, 14, 0, 0)
    unit_time = datetime(2026, 9, 10, 14, 0, 30)  # 30s ahead, under the 60s threshold
    _patch_now(monkeypatch, now)
    client = AsyncMock()

    result = asyncio.run(time_sync.async_sync_if_needed(client, _unit_time_data(unit_time)))

    assert result is False
    client.write_register.assert_not_awaited()


def test_async_sync_if_needed_writes_when_beyond_threshold(monkeypatch: pytest.MonkeyPatch):
    now = datetime(2026, 9, 10, 14, 0, 0)
    unit_time = datetime(2026, 9, 10, 14, 5, 0)  # 5 minutes ahead, beyond the threshold
    _patch_now(monkeypatch, now)
    client = AsyncMock()

    result = asyncio.run(time_sync.async_sync_if_needed(client, _unit_time_data(unit_time)))

    assert result is True
    client.write_register.assert_awaited()


def test_async_sync_if_needed_writes_when_drift_unknown(monkeypatch: pytest.MonkeyPatch):
    _patch_now(monkeypatch, datetime(2026, 9, 10, 14, 0, 0))
    client = AsyncMock()

    result = asyncio.run(time_sync.async_sync_if_needed(client, {}))

    assert result is True
    client.write_register.assert_awaited()
