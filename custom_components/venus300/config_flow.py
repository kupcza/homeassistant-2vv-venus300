"""Config flow for the 2VV Venus 300 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import CONF_SLAVE_ID, DEFAULT_PORT, DEFAULT_SLAVE_ID, DOMAIN
from .modbus_client import Venus300ModbusClient, Venus300ModbusError
from .registers import CONTROL_BLOCK

_LOGGER = logging.getLogger(__name__)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_SLAVE_ID, default=DEFAULT_SLAVE_ID): int,
    }
)


class Venus300ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the 2VV Venus 300."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for host/port/slave id and verify the unit answers."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._async_abort_entries_match(
                {CONF_HOST: user_input[CONF_HOST], CONF_PORT: user_input[CONF_PORT]}
            )
            client = Venus300ModbusClient(
                user_input[CONF_HOST], user_input[CONF_PORT], user_input[CONF_SLAVE_ID]
            )
            try:
                await client.connect()
                await client.read_block(CONTROL_BLOCK)
            except Venus300ModbusError:
                _LOGGER.debug("Connection test failed", exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=f"Venus 300 ({user_input[CONF_HOST]})", data=user_input
                )
            finally:
                client.close()

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )
