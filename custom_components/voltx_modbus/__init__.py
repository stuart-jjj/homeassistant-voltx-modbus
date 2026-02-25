"""Voltx Modbus integration for Home Assistant.

Each config entry represents one inverter (distinguished by host, port and
slave ID).  Multiple entries can coexist for multi-inverter set-ups.

Setup sequence per entry:
1. Build a VoltxModbusCoordinator with the connection parameters.
2. Perform the first Modbus poll (async_config_entry_first_refresh).
3. Forward entity setup to the sensor platform.
4. Listen for options updates so a changed scan-interval takes effect without
   a full reload.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import CONF_SCAN_INTERVAL, CONF_SLAVE_ID, DEFAULT_SCAN_INTERVAL, DOMAIN
from .coordinator import VoltxModbusCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NUMBER, Platform.SELECT]

# Type alias for typed runtime-data access
type VoltxModbusConfigEntry = ConfigEntry[VoltxModbusCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: VoltxModbusConfigEntry) -> bool:
    """Set up a Voltx Modbus device from a config entry."""
    host: str = entry.data[CONF_HOST]
    port: int = entry.data[CONF_PORT]
    slave_id: int = entry.data[CONF_SLAVE_ID]
    scan_interval: int = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    coordinator = VoltxModbusCoordinator(
        hass=hass,
        host=host,
        port=port,
        slave_id=slave_id,
        scan_interval=scan_interval,
    )

    # First refresh – raises ConfigEntryNotReady on failure (HA will retry).
    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator as the entry's runtime data for typed access from platforms.
    entry.runtime_data = coordinator

    # Forward entity registration to the sensor platform.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload the entry when the user changes options (e.g. scan interval).
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant,
    entry: VoltxModbusConfigEntry,
) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: VoltxModbusConfigEntry) -> bool:
    """Unload a Voltx Modbus config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
