"""DataUpdateCoordinator for the Venus 300."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DEFAULT_BOOST_TIMER_MINUTES, DEFAULT_SCAN_INTERVAL
from .filter_usage import FilterUsageTracker
from .modbus_client import Venus300ModbusClient, Venus300ModbusError
from .registers import ALL_BLOCKS, FILTER_MAX_HOURS, SINGLE_HOLDING_REGISTERS, SWITCH_ON

_LOGGER = logging.getLogger(__name__)


class Venus300Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls every known Venus 300 register on one shared connection."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: Venus300ModbusClient
    ) -> None:
        """Set up the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{entry.title} ({entry.data['host']})",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        self.client = client
        self.filter_usage = FilterUsageTracker(hass, entry.entry_id)
        # Shared with number.Venus300BoostTimerNumber (sets it, restoring its
        # last value across restarts) and switch.Venus300BoostSwitch (reads
        # it when starting the auto-off countdown).
        self.boost_timer_minutes: float = DEFAULT_BOOST_TIMER_MINUTES

    async def _async_update_data(self) -> dict[str, Any]:
        """Poll every register block and isolated register."""
        data: dict[str, Any] = {}
        try:
            if not self.client.connected:
                await self.client.connect()
            for block in ALL_BLOCKS:
                data.update(await self.client.read_block(block))
            for register in SINGLE_HOLDING_REGISTERS:
                data[register.key] = await self.client.read_register(register)
        except Venus300ModbusError as err:
            raise UpdateFailed(str(err)) from err

        usage_hours = await self.filter_usage.async_tick(running=bool(data[SWITCH_ON.key]))
        data["filter_usage_hours"] = round(usage_hours, 2)
        max_hours = data.get(FILTER_MAX_HOURS.key)
        data["filter_usage_percent"] = (
            round(min(100.0, usage_hours / max_hours * 100), 1) if max_hours else None
        )
        data["filter_usage_reset_at"] = self.filter_usage.last_reset_at

        return data
