"""Config flow for Voltx Modbus integration.

Handles initial user setup and options (scan interval).  Multiple devices can
be added by running the flow again with a different host / slave ID.  The
unique-id is derived from ``{host}:{port}:{slave_id}`` so duplicate entries
are rejected automatically.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers import selector

from .const import (
    CONF_SCAN_INTERVAL,
    CONF_SLAVE_ID,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SLAVE_ID,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the config-flow form schema, pre-filled with *defaults*."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_HOST, default=d.get(CONF_HOST, "")): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            ),
            vol.Required(CONF_PORT, default=d.get(CONF_PORT, DEFAULT_PORT)): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=65535, mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Required(
                CONF_SLAVE_ID, default=d.get(CONF_SLAVE_ID, DEFAULT_SLAVE_ID)
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1, max=247, mode=selector.NumberSelectorMode.BOX
                )
            ),
        }
    )


def _options_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Return the options-flow form schema."""
    d = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_SCAN_INTERVAL,
                default=d.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5, max=3600, step=5, mode=selector.NumberSelectorMode.SLIDER
                )
            ),
        }
    )


async def _validate_connection(
    hass,
    host: str,
    port: int,
    slave_id: int,
) -> str | None:
    """Try one register read; return an error key string or None on success."""
    from pyModbusTCP.client import ModbusClient  # noqa: PLC0415

    def _try_connect() -> bool:
        client = ModbusClient(host=host, port=int(port), unit_id=int(slave_id), timeout=5)
        try:
            if not client.open():
                return False
            # Read the working-hours register (1307) as a quick sanity check.
            result = client.read_input_registers(1307, 1)
            return result is not None
        except Exception:  # noqa: BLE001
            return False
        finally:
            client.close()

    try:
        ok = await hass.async_add_executor_job(_try_connect)
    except Exception:  # noqa: BLE001
        return "cannot_connect"
    return None if ok else "cannot_connect"


class VoltxModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Voltx Modbus."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> VoltxModbusOptionsFlow:
        """Return the options flow."""
        return VoltxModbusOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            slave_id = int(user_input[CONF_SLAVE_ID])

            # Prevent duplicate entries for the same device.
            unique_id = f"{host}_{port}_{slave_id}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Validate we can actually talk to the inverter.
            error = await _validate_connection(self.hass, host, port, slave_id)
            if error:
                errors["base"] = error
            else:
                return self.async_create_entry(
                    title=f"Voltx {host} (slave {slave_id})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_SLAVE_ID: slave_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_user_schema(user_input),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Allow the user to update host/port/slave_id without re-adding."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = int(user_input[CONF_PORT])
            slave_id = int(user_input[CONF_SLAVE_ID])

            error = await _validate_connection(self.hass, host, port, slave_id)
            if error:
                errors["base"] = error
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=f"{host}_{port}_{slave_id}",
                    title=f"Voltx {host} (slave {slave_id})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_SLAVE_ID: slave_id,
                    },
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(entry.data),
            errors=errors,
        )


class VoltxModbusOptionsFlow(config_entries.OptionsFlow):
    """Handle options (scan interval)."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL])},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(self.config_entry.options),
        )
