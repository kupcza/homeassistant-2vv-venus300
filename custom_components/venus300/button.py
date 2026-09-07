"""Button entities for the Venus 300."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Venus300ConfigEntry
from .coordinator import Venus300Coordinator
from .entity import Venus300Entity
from .modbus_client import Venus300ModbusError
from .registers import FILTER_CLOGGED_TIMER_RESET


async def async_setup_entry(
    hass: HomeAssistant,
    entry: Venus300ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Venus 300 buttons."""
    coordinator = entry.runtime_data
    async_add_entities([Venus300FilterTimerResetButton(coordinator, entry)])


class Venus300FilterTimerResetButton(Venus300Entity, ButtonEntity):
    """Reset the filter clog timer/counter after replacing a filter.

    Writes SHARE's FilterClogedTimerReset (doc 21016): this is a one-shot
    action, not a persistent state, so it isn't tracked by the coordinator.
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
        await self.coordinator.async_request_refresh()
