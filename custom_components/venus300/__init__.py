"""The 2VV Venus 300 recuperation unit integration."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from . import time_sync
from .const import CONF_SLAVE_ID
from .coordinator import Venus300Coordinator
from .modbus_client import Venus300ModbusClient, Venus300ModbusError

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
]

CLOCK_SYNC_INTERVAL = timedelta(hours=24)

type Venus300ConfigEntry = ConfigEntry[Venus300Coordinator]


async def async_setup_entry(hass: HomeAssistant, entry: Venus300ConfigEntry) -> bool:
    """Set up the Venus 300 from a config entry."""
    client = Venus300ModbusClient(
        entry.data[CONF_HOST], entry.data[CONF_PORT], entry.data[CONF_SLAVE_ID]
    )
    try:
        await client.connect()
    except Venus300ModbusError as err:
        client.close()
        raise ConfigEntryNotReady(str(err)) from err

    coordinator = Venus300Coordinator(hass, entry, client)
    await coordinator.filter_usage.async_load()
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def _async_periodic_clock_sync(_now) -> None:
        """Correct the unit's clock if it has drifted (see time_sync.py)."""
        try:
            if await time_sync.async_sync_if_needed(client, coordinator.data):
                _LOGGER.info("Corrected clock drift on %s", entry.title)
        except Venus300ModbusError as err:
            _LOGGER.error("Failed to sync clock on %s: %s", entry.title, err)

    await _async_periodic_clock_sync(None)  # once now, then periodically
    entry.async_on_unload(
        async_track_time_interval(hass, _async_periodic_clock_sync, CLOCK_SYNC_INTERVAL)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: Venus300ConfigEntry) -> bool:
    """Unload a config entry and close its Modbus connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.client.close()
    return unload_ok
