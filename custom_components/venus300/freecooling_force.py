"""Computes a near-future clock time to edge-trigger Freecooling's start.

Confirmed live: Freecooling's start condition is edge-triggered on the
unit's own clock crossing freecooling_on_hour:freecooling_on_min, not a
level check re-evaluated continuously. Setting the allowed start time to
a time that's already passed does nothing -- even with every other
condition in freecooling_conditions.evaluate() already true -- but
nudging the start time to just past the unit's current clock and letting
it tick across that boundary engages Freecooling immediately (see
README's "Manually triggering Freecooling" section). This is the only
known way to trigger it on demand, since the manual override register
(FreecoolingMode, SHARE doc 21010) never sticks.
"""

from __future__ import annotations


def next_minute(hour: int, minute: int) -> tuple[int, int]:
    """Return (hour, minute) one minute after the given time, wrapping at midnight."""
    minute += 1
    if minute == 60:
        minute = 0
        hour = (hour + 1) % 24
    return hour, minute
