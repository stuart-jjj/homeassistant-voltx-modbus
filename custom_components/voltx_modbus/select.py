"""Select platform for Voltx Modbus integration.

Exposes enum holding registers as Home Assistant select entities.
Each entity reads its current option from coordinator data and writes
back the corresponding raw integer via FC06 through the coordinator.
"""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VoltxModbusCoordinator
from .device_info import get_device_info


@dataclass(frozen=True, kw_only=True)
class VoltxSelectEntityDescription(SelectEntityDescription):
    """Extends SelectEntityDescription with Voltx-specific fields."""

    # FC03 holding register address to write
    register: int
    # Mapping from raw register integer to HA option label string.
    # The reverse map (label → raw) is built automatically at entity init.
    options_map: dict[int, str]


# ── Select entity catalogue ───────────────────────────────────────────────────
#
# Work mode confirmed values (Solplanet/Voltx ASW010K-SH):
#   2 = Self-consumption  (observed while mode was "Self-consumption mode")
#   3 = Reserve Power     (observed while mode was "Reserve Power Mode")
#   4 = Custom            (observed while mode was "Custom Mode")
#   5 = Time of Use       (observed while mode was "Time of use")
#
# Note: Off Grid mode is not included — switching to it disconnects from the
# grid and drops non-essential circuits.  Value TBC (not yet tested).

# Note: register 1151 (chflg) is read-only status — the inverter updates it to
# reflect current charge/discharge state.  It is exposed as a text sensor (chflg)
# but has no writable select entity because writes have no observable effect.
# Register 1152 (chpwr) is the actual control register in Custom mode.
SELECT_DESCRIPTIONS: tuple[VoltxSelectEntityDescription, ...] = (
    VoltxSelectEntityDescription(
        key="work_mode",
        name="Work Mode",
        icon="mdi:solar-power-variant",
        register=1103,
        options_map={
            2: "Self-consumption",
            3: "Reserve Power",
            4: "Custom",
            5: "Time of Use",
        },
        options=["Self-consumption", "Reserve Power", "Custom", "Time of Use"],
    ),
)


# ── Platform setup ────────────────────────────────────────────────────────────


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Voltx Modbus select entities from a config entry."""
    coordinator: VoltxModbusCoordinator = entry.runtime_data

    async_add_entities(
        VoltxSelectEntity(coordinator, entry, description)
        for description in SELECT_DESCRIPTIONS
        if description.key in (coordinator.data or {})
    )


# ── Entity class ──────────────────────────────────────────────────────────────


class VoltxSelectEntity(
    CoordinatorEntity[VoltxModbusCoordinator],
    SelectEntity,
):
    """A writable Voltx Modbus select entity."""

    entity_description: VoltxSelectEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VoltxModbusCoordinator,
        entry: ConfigEntry,
        description: VoltxSelectEntityDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"
        self._attr_options = list(description.options)
        self._reverse_map: dict[str, int] = {
            label: raw for raw, label in description.options_map.items()
        }
        self._attr_device_info = get_device_info(entry, description.key)

    @property
    def current_option(self) -> str | None:
        """Return the currently active option label."""
        if self.coordinator.data is None:
            return None
        raw = self.coordinator.data.get(self.entity_description.key)
        if raw is None:
            return None
        return self.entity_description.options_map.get(raw)

    @property
    def available(self) -> bool:
        """Return True when the coordinator has data and the key is present."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.key in self.coordinator.data
        )

    async def async_select_option(self, option: str) -> None:
        """Write the selected option's raw value to the inverter via FC06."""
        raw = self._reverse_map.get(option)
        if raw is None:
            return
        await self.coordinator.async_write_register(
            self.entity_description.register, raw
        )
