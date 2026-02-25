"""Number platform for Voltx Modbus integration.

Exposes writable holding registers as Home Assistant number entities.
Each entity reads its current value from coordinator data and writes
back via FC06 (write single holding register) through the coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VoltxModbusCoordinator
from .device_info import get_device_info


@dataclass(frozen=True, kw_only=True)
class VoltxNumberEntityDescription(NumberEntityDescription):
    """Extends NumberEntityDescription with Voltx-specific fields."""

    # FC03 holding register address to write
    register: int
    # Multiply the HA native value by this to get the raw register integer.
    # e.g. raw_scale=100 means 40% → raw 4000 written to the register.
    raw_scale: int = 1


# ── Number entity catalogue ───────────────────────────────────────────────────

NUMBER_DESCRIPTIONS: tuple[VoltxNumberEntityDescription, ...] = (
    VoltxNumberEntityDescription(
        key="chpwr",
        name="Battery Charge/Discharge Power",
        # Positive = discharge, negative = charge (inverter convention).
        # s16 register — _write_register masks to u16 for two's-complement.
        native_min_value=-10000,
        native_max_value=10000,
        native_step=50,
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=NumberDeviceClass.POWER,
        mode=NumberMode.BOX,
        icon="mdi:battery-arrow-up-outline",
        register=1152,
        raw_scale=1,
    ),
    VoltxNumberEntityDescription(
        key="soc_max",
        name="Battery SOC Max",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.BATTERY,
        mode=NumberMode.BOX,
        icon="mdi:battery-arrow-up",
        register=1153,
        raw_scale=100,
    ),
    VoltxNumberEntityDescription(
        key="soc_min",
        name="Battery SOC Min",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        device_class=NumberDeviceClass.BATTERY,
        mode=NumberMode.BOX,
        icon="mdi:battery-arrow-down",
        register=1154,
        raw_scale=100,
    ),
)


# ── Platform setup ────────────────────────────────────────────────────────────


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Voltx Modbus number entities from a config entry."""
    coordinator: VoltxModbusCoordinator = entry.runtime_data

    async_add_entities(
        VoltxNumberEntity(coordinator, entry, description)
        for description in NUMBER_DESCRIPTIONS
        if description.key in (coordinator.data or {})
    )


# ── Entity class ──────────────────────────────────────────────────────────────


class VoltxNumberEntity(
    CoordinatorEntity[VoltxModbusCoordinator],
    NumberEntity,
):
    """A writable Voltx Modbus number entity."""

    entity_description: VoltxNumberEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VoltxModbusCoordinator,
        entry: ConfigEntry,
        description: VoltxNumberEntityDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_device_info = get_device_info(entry, description.key)

    @property
    def native_value(self) -> float | None:
        """Return the current value from coordinator data."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def available(self) -> bool:
        """Return True when the coordinator has data and the key is present."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value to the inverter via FC06."""
        raw = int(round(value * self.entity_description.raw_scale))
        await self.coordinator.async_write_register(
            self.entity_description.register, raw
        )
