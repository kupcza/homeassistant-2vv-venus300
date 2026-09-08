"""Switch entities for the Venus 300."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import Venus300ConfigEntry
from .coordinator import Venus300Coordinator
from .entity import Venus300Entity
from .modbus_client import Venus300ModbusError
from .registers import (
    BOOST_MODE,
    FILTER_WORKING_HOURS_ENABLED,
    FREECOOLING_ENABLE,
    FREECOOLING_MODE,
    SWITCH_ON,
    Register,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Venus300ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Venus 300 switches."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            Venus300Switch(coordinator, entry, SWITCH_ON, "power"),
            Venus300Switch(coordinator, entry, FREECOOLING_MODE, "freecooling_mode"),
            Venus300Switch(
                coordinator,
                entry,
                FREECOOLING_ENABLE,
                "freecooling_enable",
                EntityCategory.CONFIG,
            ),
            Venus300Switch(
                coordinator,
                entry,
                FILTER_WORKING_HOURS_ENABLED,
                "filter_working_hours_enabled",
                EntityCategory.CONFIG,
            ),
            Venus300BoostSwitch(coordinator, entry),
        ]
    )


class Venus300Switch(Venus300Entity, SwitchEntity):
    """A single writable on/off holding register."""

    def __init__(
        self,
        coordinator: Venus300Coordinator,
        entry: Venus300ConfigEntry,
        register: Register,
        translation_key: str,
        entity_category: EntityCategory | None = None,
    ) -> None:
        """Set up the switch for one register."""
        super().__init__(coordinator, entry)
        self._register = register
        self._attr_translation_key = translation_key
        self._attr_unique_id = f"{entry.entry_id}_{register.key}"
        self._attr_entity_category = entity_category

    @property
    def is_on(self) -> bool | None:
        """Return the current on/off state."""
        value = self.coordinator.data.get(self._register.key)
        return None if value is None else bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the register on."""
        await self._async_write(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the register off."""
        await self._async_write(0)

    async def _async_write(self, value: int) -> None:
        """Write the register and refresh state from the unit."""
        try:
            await self.coordinator.client.write_register(self._register, value)
        except Venus300ModbusError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()


class Venus300BoostSwitch(Venus300Entity, SwitchEntity):
    """Turns on the unit's real boost airflow for a limited, self-clearing time.

    Writes SHARE's BoostMode (doc 21009) directly, then schedules its own
    turn-off after coordinator.boost_timer_minutes (number.boost_timer_minutes)
    — simulating a "boost button" without needing an external Home Assistant
    automation to manage the countdown. Turning it off manually cancels the
    countdown immediately. State isn't restored across Home Assistant
    restarts: a boost in progress at restart time comes back "off" here,
    though the unit itself keeps running boost until it's told otherwise.
    """

    _attr_translation_key = "boost_active"

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the boost switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_boost_active"
        self._attr_is_on = False
        self._cancel_timer: Callable[[], None] | None = None

    @property
    def is_on(self) -> bool:
        """Return whether a boost is currently running."""
        return self._attr_is_on

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Activate boost on the unit and schedule its automatic turn-off."""
        await self._async_write(1)
        self._attr_is_on = True
        self._schedule_auto_off()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Deactivate boost on the unit immediately."""
        self._cancel_pending_timer()
        await self._async_write(0)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending auto-off callback."""
        self._cancel_pending_timer()

    def _schedule_auto_off(self) -> None:
        """(Re)schedule the auto-off callback for the configured duration."""
        self._cancel_pending_timer()
        minutes = self.coordinator.boost_timer_minutes
        self._cancel_timer = async_call_later(self.hass, minutes * 60, self._async_auto_off)

    def _cancel_pending_timer(self) -> None:
        """Cancel a scheduled auto-off callback, if any."""
        if self._cancel_timer is not None:
            self._cancel_timer()
            self._cancel_timer = None

    async def _async_auto_off(self, _now: Any) -> None:
        """Turn boost back off once the configured duration has elapsed."""
        self._cancel_timer = None
        try:
            await self.coordinator.client.write_register(BOOST_MODE, 0)
        except Venus300ModbusError as err:
            _LOGGER.error("Failed to auto turn off boost: %s", err)
        self._attr_is_on = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def _async_write(self, value: int) -> None:
        """Write the boost register and refresh state from the unit."""
        try:
            await self.coordinator.client.write_register(BOOST_MODE, value)
        except Venus300ModbusError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
