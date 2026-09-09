"""Evaluates Freecooling's temperature/season/hour-window preconditions.

Confirmed by live debugging against a real unit (see README):
  - The daily allowed-hours window wraps past midnight
    (now >= on_hour OR now < off_hour), not a same-day range.
  - These conditions are evaluated against the unit's OWN real-time clock
    (registers.py's TIME_BLOCK), not Home Assistant's.

Deliberately excludes freecooling_enable -- that's already its own
switch.freecooling_enable entity, checked separately.
"""

from __future__ import annotations

from typing import Any

from .registers import (
    ACTUAL_DAY,
    ACTUAL_HOUR,
    ACTUAL_MIN,
    ACTUAL_MONTH,
    FREECOOLING_OFF_DAY,
    FREECOOLING_OFF_HOUR,
    FREECOOLING_OFF_MIN,
    FREECOOLING_OFF_MONTH,
    FREECOOLING_ON_DAY,
    FREECOOLING_ON_HOUR,
    FREECOOLING_ON_MIN,
    FREECOOLING_ON_MONTH,
    FREECOOLING_TEMP_THRESHOLD,
    TEMP_OUTSIDE_TO_UNIT,
)


def _in_season(data: dict[str, Any]) -> bool:
    """Whether the unit's current date falls within the season window."""
    start = (data[FREECOOLING_ON_MONTH.key], data[FREECOOLING_ON_DAY.key])
    end = (data[FREECOOLING_OFF_MONTH.key], data[FREECOOLING_OFF_DAY.key])
    now = (data[ACTUAL_MONTH.key], data[ACTUAL_DAY.key])
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end  # wraps across the new year


def _in_hour_window(data: dict[str, Any]) -> bool:
    """Whether the unit's current time falls within the daily hour window."""
    start = (data[FREECOOLING_ON_HOUR.key], data[FREECOOLING_ON_MIN.key])
    end = (data[FREECOOLING_OFF_HOUR.key], data[FREECOOLING_OFF_MIN.key])
    now = (data[ACTUAL_HOUR.key], data[ACTUAL_MIN.key])
    if start <= end:
        return start <= now < end
    return now >= start or now < end  # confirmed: wraps past midnight


def evaluate(data: dict[str, Any]) -> dict[str, bool]:
    """Return each sub-condition plus the combined result."""
    temp_ok = data[TEMP_OUTSIDE_TO_UNIT.key] < data[FREECOOLING_TEMP_THRESHOLD.key]
    season_ok = _in_season(data)
    hour_ok = _in_hour_window(data)
    return {
        "temp_ok": temp_ok,
        "season_ok": season_ok,
        "hour_ok": hour_ok,
        "all_met": temp_ok and season_ok and hour_ok,
    }
