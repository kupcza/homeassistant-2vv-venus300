"""Switch entities for the Venus 300."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import Venus300ConfigEntry
from .coordinator import Venus300Coordinator
from .entity import Venus300Entity
from .modbus_client import Venus300ModbusError
from .registers import FREECOOLING_ENABLE, FREECOOLING_MODE, SWITCH_ON, Register


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
