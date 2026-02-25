"""Device info helpers for Voltx Modbus integration.

Defines two HA devices per config entry:
  • Inverter  – grid/AC/DC inverter metrics and controls
  • Battery   – battery storage metrics and controls (linked to inverter via via_device)
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo

from .const import CONF_SLAVE_ID, DOMAIN

# Keys produced by the coordinator that belong to the Battery device.
# Everything else goes to the Inverter device.
BATTERY_KEYS: frozenset[str] = frozenset({
    # Live battery measurements
    "pb", "vb", "cb", "tb",
    "soc", "soh",
    "cli", "clo",
    "bst", "bcomm",
    "e_chg_today", "e_dis_today",
    # Charge/discharge command & status (Custom mode control)
    "chflg", "chpwr",
    # Battery limit settings
    "soc_max", "soc_min",
})


def inverter_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return DeviceInfo for the inverter device."""
    uid = entry.unique_id or entry.entry_id
    host = entry.data[CONF_HOST]
    slave = entry.data[CONF_SLAVE_ID]
    return DeviceInfo(
        identifiers={(DOMAIN, uid)},
        name=f"Voltx Inverter ({host} slave {slave})",
        manufacturer="Voltx",
        model="Hybrid Inverter",
    )


def battery_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Return DeviceInfo for the battery device, linked to the inverter."""
    uid = entry.unique_id or entry.entry_id
    host = entry.data[CONF_HOST]
    slave = entry.data[CONF_SLAVE_ID]
    return DeviceInfo(
        identifiers={(DOMAIN, f"{uid}_battery")},
        name=f"Voltx Battery ({host} slave {slave})",
        manufacturer="Voltx",
        model="Battery Storage",
        via_device=(DOMAIN, uid),
    )


def get_device_info(entry: ConfigEntry, key: str) -> DeviceInfo:
    """Return the correct DeviceInfo for a given coordinator data key."""
    if key in BATTERY_KEYS:
        return battery_device_info(entry)
    return inverter_device_info(entry)
