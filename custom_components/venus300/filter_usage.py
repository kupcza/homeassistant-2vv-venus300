"""Tracks estimated filter usage hours in Home Assistant.

Some Venus 300 units have no physical filter differential-pressure sensor
fitted; on those, the unit's own inlet_filter_life/outlet_filter_life
percentage stays at 0% indefinitely regardless of filter_working_hours_enabled
or filter_max_hours (see README's "Known caveat"). This tracks operating
hours independently — counting only while the unit is powered on, matching
"FilterMaxHours"/"FilterWoringHours" naming — against filter_max_hours read
live from the unit, persisted across Home Assistant restarts.

This only resets when button.filter_timer_reset is pressed. If a filter is
replaced and reset only via the unit's own control panel, this counter has
no way to know and will keep counting past the real reset point.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

STORAGE_VERSION = 1


class FilterUsageTracker:
    """Accumulates operating hours since the last filter reset."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Set up the tracker and its persistent store."""
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"venus300_filter_usage_{entry_id}"
        )
        self.accumulated_hours: float = 0.0
        self.last_reset_at: datetime = dt_util.utcnow()
        self._last_tick: datetime | None = None

    async def async_load(self) -> None:
        """Restore state saved before a Home Assistant restart, if any."""
        data = await self._store.async_load()
        if not data:
            return
        self.accumulated_hours = data["accumulated_hours"]
        if restored := dt_util.parse_datetime(data["last_reset_at"]):
            self.last_reset_at = restored

    async def async_tick(self, running: bool) -> float:
        """Advance the accumulator for the elapsed time since the last tick."""
        now = dt_util.utcnow()
        if self._last_tick is not None and running:
            self.accumulated_hours += (now - self._last_tick).total_seconds() / 3600
        self._last_tick = now
        await self._async_save()
        return self.accumulated_hours

    async def async_reset(self) -> None:
        """Zero the accumulator, e.g. after physically replacing a filter."""
        self.accumulated_hours = 0.0
        self.last_reset_at = dt_util.utcnow()
        self._last_tick = self.last_reset_at
        await self._async_save()

    async def _async_save(self) -> None:
        """Persist the current state."""
        await self._store.async_save(
            {
                "accumulated_hours": self.accumulated_hours,
                "last_reset_at": self.last_reset_at.isoformat(),
            }
        )
