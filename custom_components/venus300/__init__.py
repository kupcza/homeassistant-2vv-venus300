"""The 2VV Venus 300 recuperation unit integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .const import CONF_SLAVE_ID
from .coordinator import Venus300Coordinator
from .modbus_client import Venus300ModbusClient, Venus300ModbusError

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]

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
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: Venus300ConfigEntry) -> bool:
    """Unload a config entry and close its Modbus connection."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        entry.runtime_data.client.close()
    return unload_ok
