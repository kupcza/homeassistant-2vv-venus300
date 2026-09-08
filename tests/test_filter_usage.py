"""Tests for the Home-Assistant-side filter usage tracker.

These bypass Store/hass entirely (not needed for the pure accumulation
logic) by constructing the tracker without __init__ and stubbing
persistence, then controlling the clock via monkeypatch.
"""

import asyncio
from datetime import datetime, timezone

import pytest

from custom_components.venus300.filter_usage import FilterUsageTracker


def _make_tracker() -> FilterUsageTracker:
    tracker = object.__new__(FilterUsageTracker)
    tracker.accumulated_hours = 0.0
    tracker.last_reset_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    tracker._last_tick = None

    async def _noop_save() -> None:
        return None

    tracker._async_save = _noop_save
    return tracker


def _patch_clock(monkeypatch: pytest.MonkeyPatch, *times: datetime) -> None:
    iterator = iter(times)
    monkeypatch.setattr(
        "custom_components.venus300.filter_usage.dt_util.utcnow", lambda: next(iterator)
    )


def test_first_tick_seeds_the_clock_without_accumulating(monkeypatch: pytest.MonkeyPatch):
    tracker = _make_tracker()
    now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
    _patch_clock(monkeypatch, now)

    result = asyncio.run(tracker.async_tick(running=True))

    assert result == 0.0
    assert tracker._last_tick == now


def test_accumulates_only_while_running(monkeypatch: pytest.MonkeyPatch):
    tracker = _make_tracker()
    _patch_clock(
        monkeypatch,
        datetime(2026, 1, 1, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 1, 1, tzinfo=timezone.utc),  # +1h, running
        datetime(2026, 1, 1, 3, tzinfo=timezone.utc),  # +2h, NOT running
        datetime(2026, 1, 1, 4, tzinfo=timezone.utc),  # +1h, running
    )

    asyncio.run(tracker.async_tick(running=True))  # seeds the clock only
    asyncio.run(tracker.async_tick(running=True))
    asyncio.run(tracker.async_tick(running=False))
    result = asyncio.run(tracker.async_tick(running=True))

    assert result == pytest.approx(2.0)


def test_reset_zeroes_the_accumulator_and_bumps_last_reset_at(monkeypatch: pytest.MonkeyPatch):
    tracker = _make_tracker()
    tracker.accumulated_hours = 42.0
    now = datetime(2026, 2, 1, tzinfo=timezone.utc)
    _patch_clock(monkeypatch, now)

    asyncio.run(tracker.async_reset())

    assert tracker.accumulated_hours == 0.0
    assert tracker.last_reset_at == now
