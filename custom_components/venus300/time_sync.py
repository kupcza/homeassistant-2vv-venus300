"""Keeps the unit's own real-time clock synced to Home Assistant's.

CONFIRMED by live testing: the unit has its own RTC (registers.py's
TIME_BLOCK), previously never set (found sitting at factory defaults,
2000-01-01 00:00:00) and drifting freely. Schedule-based features
(Freecooling's season/allowed-hours window) are evaluated against THIS
clock, not Home Assistant's, so keeping it accurate matters. Writing
TIME_DRIVER's Set* fields plus SET_TIME_FLAG=1 commits a new time
immediately -- confirmed the flag self-clears back to 0 once applied.
"""

from __future__ import annotations

from datetime import datetime

from homeassistant.util import dt as dt_util

from .modbus_client import Venus300ModbusClient
from .registers import (
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

DRIFT_THRESHOLD_SECONDS = 60


def current_drift_seconds(data: dict) -> float | None:
    """How far off the unit's clock is from Home Assistant's, in seconds.

    Positive means the unit is ahead; negative means it's behind. None if
    the unit's clock hasn't been read yet.
    """
    try:
        unit_time = datetime(
            data[ACTUAL_YEAR.key],
            data[ACTUAL_MONTH.key],
            data[ACTUAL_DAY.key],
            data[ACTUAL_HOUR.key],
            data[ACTUAL_MIN.key],
            data[ACTUAL_SEC.key],
        )
    except (KeyError, ValueError):
        return None
    now = dt_util.now().replace(tzinfo=None)
    return (unit_time - now).total_seconds()


async def async_force_sync(client: Venus300ModbusClient) -> None:
    """Write Home Assistant's current time to the unit unconditionally."""
    now = dt_util.now()
    for register, value in (
        (SET_YEAR, now.year),
        (SET_MONTH, now.month),
        (SET_DAY, now.day),
        (SET_DAY_OF_WEEK, now.isoweekday()),
        (SET_HOUR, now.hour),
        (SET_MIN, now.minute),
        (SET_SEC, now.second),
    ):
        await client.write_register(register, value)
    await client.write_register(SET_TIME_FLAG, 1)


async def async_sync_if_needed(client: Venus300ModbusClient, data: dict) -> bool:
    """Sync the unit's clock only if it has drifted beyond the threshold.

    Returns whether a sync was actually performed.
    """
    drift = current_drift_seconds(data)
    if drift is not None and abs(drift) < DRIFT_THRESHOLD_SECONDS:
        return False
    await async_force_sync(client)
    return True
