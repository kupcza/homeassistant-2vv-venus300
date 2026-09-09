"""Tests for the Freecooling temperature/season/hour-window evaluation.

Confirmed against a real unit: the hour window wraps past midnight, and
everything is evaluated against the unit's own clock (registers.py's
TIME_BLOCK), not Home Assistant's -- see freecooling_conditions.py.
"""

from custom_components.venus300 import freecooling_conditions
from custom_components.venus300.registers import (
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


def _make_data(
    *,
    temp_outside: float = 15.0,
    temp_threshold: float = 20.0,
    on_month: int = 6,
    on_day: int = 1,
    off_month: int = 10,
    off_day: int = 1,
    now_month: int = 9,
    now_day: int = 9,
    on_hour: int = 22,
    on_min: int = 0,
    off_hour: int = 6,
    off_min: int = 0,
    now_hour: int = 0,
    now_min: int = 0,
) -> dict:
    return {
        TEMP_OUTSIDE_TO_UNIT.key: temp_outside,
        FREECOOLING_TEMP_THRESHOLD.key: temp_threshold,
        FREECOOLING_ON_MONTH.key: on_month,
        FREECOOLING_ON_DAY.key: on_day,
        FREECOOLING_OFF_MONTH.key: off_month,
        FREECOOLING_OFF_DAY.key: off_day,
        ACTUAL_MONTH.key: now_month,
        ACTUAL_DAY.key: now_day,
        FREECOOLING_ON_HOUR.key: on_hour,
        FREECOOLING_ON_MIN.key: on_min,
        FREECOOLING_OFF_HOUR.key: off_hour,
        FREECOOLING_OFF_MIN.key: off_min,
        ACTUAL_HOUR.key: now_hour,
        ACTUAL_MIN.key: now_min,
    }


def test_temperature_condition():
    assert freecooling_conditions.evaluate(_make_data(temp_outside=15, temp_threshold=20))[
        "temp_ok"
    ]
    assert not freecooling_conditions.evaluate(
        _make_data(temp_outside=25, temp_threshold=20)
    )["temp_ok"]


def test_season_window_same_year_range():
    in_season = _make_data(on_month=6, on_day=1, off_month=10, off_day=1, now_month=9, now_day=9)
    out_of_season = _make_data(
        on_month=6, on_day=1, off_month=10, off_day=1, now_month=11, now_day=1
    )
    assert freecooling_conditions.evaluate(in_season)["season_ok"]
    assert not freecooling_conditions.evaluate(out_of_season)["season_ok"]


def test_hour_window_wraps_past_midnight():
    # Confirmed empirically: on=22, off=6 means "22:00 through 06:00 the
    # next day", not an impossible same-day range.
    late_night = _make_data(on_hour=22, off_hour=6, now_hour=23, now_min=0)
    early_morning = _make_data(on_hour=22, off_hour=6, now_hour=5, now_min=0)
    midday = _make_data(on_hour=22, off_hour=6, now_hour=13, now_min=0)

    assert freecooling_conditions.evaluate(late_night)["hour_ok"]
    assert freecooling_conditions.evaluate(early_morning)["hour_ok"]
    assert not freecooling_conditions.evaluate(midday)["hour_ok"]


def test_hour_window_same_day_range():
    on_hour_boundary = _make_data(on_hour=8, off_hour=20, now_hour=8, now_min=0)
    within = _make_data(on_hour=8, off_hour=20, now_hour=12, now_min=0)
    after = _make_data(on_hour=8, off_hour=20, now_hour=21, now_min=0)

    assert freecooling_conditions.evaluate(on_hour_boundary)["hour_ok"]
    assert freecooling_conditions.evaluate(within)["hour_ok"]
    assert not freecooling_conditions.evaluate(after)["hour_ok"]


def test_all_met_requires_every_sub_condition():
    all_pass = _make_data(
        temp_outside=15,
        temp_threshold=20,
        on_month=6,
        off_month=10,
        now_month=9,
        now_day=9,
        on_hour=22,
        off_hour=6,
        now_hour=23,
    )
    result = freecooling_conditions.evaluate(all_pass)
    assert result == {
        "temp_ok": True,
        "season_ok": True,
        "hour_ok": True,
        "all_met": True,
    }

    temp_fails = _make_data(
        temp_outside=25,
        temp_threshold=20,
        on_month=6,
        off_month=10,
        now_month=9,
        now_day=9,
        on_hour=22,
        off_hour=6,
        now_hour=23,
    )
    assert freecooling_conditions.evaluate(temp_fails)["all_met"] is False
