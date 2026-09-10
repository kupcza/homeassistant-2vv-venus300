"""Button entities for the Venus 300."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import Venus300ConfigEntry, time_sync
from .coordinator import Venus300Coordinator
from .entity import Venus300Entity
from .modbus_client import Venus300ModbusError
from .registers import (
    BOOST_MODE,
    FAN_POWER_SETPOINT,
    FILTER_CLOGGED_TIMER_RESET,
    SWITCH_ON,
    encode_value,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Venus300ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Venus 300 buttons."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            Venus300FilterTimerResetButton(coordinator, entry),
            Venus300BoostButton(coordinator, entry),
            Venus300SyncClockButton(coordinator, entry),
        ]
    )


class Venus300FilterTimerResetButton(Venus300Entity, ButtonEntity):
    """Reset the filter clog timer/counter after replacing a filter.

    Writes SHARE's FilterClogedTimerReset (doc 21016) and zeroes the
    Home-Assistant-side usage tracker (filter_usage.py) that estimates
    filter_usage_hours/filter_usage_percent independently of the unit's own
    (sometimes non-functional — see README) percentage registers.
    """

    _attr_translation_key = "filter_timer_reset"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the reset button."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_{FILTER_CLOGGED_TIMER_RESET.key}"

    async def async_press(self) -> None:
        """Tell the unit a filter was just replaced."""
        try:
            await self.coordinator.client.write_register(FILTER_CLOGGED_TIMER_RESET, 1)
        except Venus300ModbusError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.filter_usage.async_reset()
        await self.coordinator.async_request_refresh()


class Venus300BoostButton(Venus300Entity, ButtonEntity):
    """Press to activate the unit's real boost airflow for a limited time.

    Writes SHARE's BoostMode (doc 21009) directly, then schedules its own
    turn-off after coordinator.boost_timer_minutes (number.boost_timer_minutes)
    — simulating a physical boost push-button without needing an external
    Home Assistant automation to manage the countdown.

    Pressing again while a boost is already running restarts the countdown
    for a fresh full duration (like a physical push-button) rather than
    cancelling it — there's no "press to cancel early" here; use
    switch.power if you want to stop everything immediately.

    As a safety net (the datasheet doesn't confirm the unit restores its own
    prior fan speed/power state once BoostMode returns to 0 — it has its
    own, separate BoostFlow airflow setting, so it likely does, but this
    isn't confirmed), power and fan_power_setpoint are snapshotted on the
    *first* press of a sequence and explicitly written back once the
    countdown finally elapses — repeated presses restart the timer without
    re-snapshotting, so the true pre-boost state is preserved throughout.
    State isn't restored across Home Assistant restarts: a boost in
    progress at restart time has no snapshot to restore, though the unit
    itself keeps running boost until it's told otherwise.
    """

    _attr_translation_key = "boost"

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the boost button."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_boost"
        self._active = False
        self._cancel_timer: Callable[[], None] | None = None
        self._pre_boost_state: dict[str, Any] | None = None

    async def async_press(self) -> None:
        """Activate boost (if not already running) and (re)start its timer."""
        if not self._active:
            self._pre_boost_state = {
                SWITCH_ON.key: self.coordinator.data.get(SWITCH_ON.key),
                FAN_POWER_SETPOINT.key: self.coordinator.data.get(FAN_POWER_SETPOINT.key),
            }
            try:
                await self.coordinator.client.write_register(BOOST_MODE, 1)
            except Venus300ModbusError as err:
                raise HomeAssistantError(str(err)) from err
            self._active = True
            await self.coordinator.async_request_refresh()
        self._schedule_auto_off()

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
        """Turn boost back off and restore prior state once time's up."""
        self._cancel_timer = None
        self._active = False
        try:
            await self.coordinator.client.write_register(BOOST_MODE, 0)
        except Venus300ModbusError as err:
            _LOGGER.error("Failed to auto turn off boost: %s", err)
        else:
            await self._async_restore_pre_boost_state()
        await self.coordinator.async_request_refresh()

    async def _async_restore_pre_boost_state(self) -> None:
        """Write back power/fan speed as they were just before boost started."""
        if self._pre_boost_state is None:
            return
        snapshot, self._pre_boost_state = self._pre_boost_state, None
        try:
            for register, value in (
                (SWITCH_ON, snapshot.get(SWITCH_ON.key)),
                (FAN_POWER_SETPOINT, snapshot.get(FAN_POWER_SETPOINT.key)),
            ):
                if value is not None:
                    await self.coordinator.client.write_register(
                        register, encode_value(register, value)
                    )
        except Venus300ModbusError as err:
            _LOGGER.error("Failed to restore pre-boost state: %s", err)


class Venus300SyncClockButton(Venus300Entity, ButtonEntity):
    """Force-sync the unit's own real-time clock to Home Assistant's now.

    This also happens automatically (once at startup and every 24h — see
    __init__.py); this button is for an immediate on-demand sync, e.g.
    right after a power outage without waiting for the next periodic
    check. See time_sync.py: schedule-based features (Freecooling's
    season/hour window) are evaluated against the unit's own clock, not
    Home Assistant's, so keeping it accurate matters.
    """

    _attr_translation_key = "sync_unit_clock"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: Venus300Coordinator, entry: Venus300ConfigEntry) -> None:
        """Set up the sync button."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_sync_unit_clock"

    async def async_press(self) -> None:
        """Write Home Assistant's current time to the unit now."""
        try:
            await time_sync.async_force_sync(self.coordinator.client)
        except Venus300ModbusError as err:
            raise HomeAssistantError(str(err)) from err
        await self.coordinator.async_request_refresh()
