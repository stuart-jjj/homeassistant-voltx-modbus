"""Sensor platform for Voltx Modbus integration.

Exposes all verified registers as HA sensor entities via the coordinator.
Each sensor maps a key in coordinator.data to a single HA sensor entity.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfApparentPower,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import VoltxModbusCoordinator
from .device_info import get_device_info


@dataclass(frozen=True, kw_only=True)
class VoltxModbusSensorEntityDescription(SensorEntityDescription):
    """Extends SensorEntityDescription with Voltx-specific metadata."""

    # Key must match the dict key produced by the coordinator's _fetch_data().
    # e.g. "pac", "soc", "vb" …
    # (inherited *key* field from SensorEntityDescription is used directly)


# ── Sensor catalogue ──────────────────────────────────────────────────────────
#
# All registers verified on Solplanet/Voltx ASW010K-SH; see MODBUS_README.md.

SENSOR_DESCRIPTIONS: tuple[VoltxModbusSensorEntityDescription, ...] = (
    # ── Inverter / grid sensors ───────────────────────────────────────────────
    VoltxModbusSensorEntityDescription(
        key="pac",
        name="Inverter Active Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        icon="mdi:solar-power",
    ),
    VoltxModbusSensorEntityDescription(
        key="sac",
        name="Inverter Apparent Power",
        device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfApparentPower.VOLT_AMPERE,
        suggested_display_precision=0,
        entity_registry_enabled_default=True,
    ),
    VoltxModbusSensorEntityDescription(
        key="qac",
        name="Inverter Reactive Power",
        # SensorDeviceClass.REACTIVE_POWER is available in HA 2023.2+
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="var",
        suggested_display_precision=0,
        entity_registry_enabled_default=True,
    ),
    VoltxModbusSensorEntityDescription(
        key="iac",
        name="AC Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        icon="mdi:current-ac",
    ),
    VoltxModbusSensorEntityDescription(
        key="tmp",
        name="Inverter Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
        icon="mdi:thermometer",
    ),
    VoltxModbusSensorEntityDescription(
        key="flg",
        name="Inverter Status",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        icon="mdi:information-outline",
    ),
    VoltxModbusSensorEntityDescription(
        key="vac",
        name="Grid Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=1,
    ),
    VoltxModbusSensorEntityDescription(
        key="fac",
        name="Grid Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfFrequency.HERTZ,
        suggested_display_precision=2,
    ),
    VoltxModbusSensorEntityDescription(
        key="pf",
        name="Power Factor",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=None,
        suggested_display_precision=2,
    ),
    VoltxModbusSensorEntityDescription(
        key="hto",
        name="Total Working Hours",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfTime.HOURS,
        suggested_display_precision=0,
        icon="mdi:clock-outline",
    ),
    # ── Battery sensors ───────────────────────────────────────────────────────
    VoltxModbusSensorEntityDescription(
        key="pb",
        name="Battery Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        icon="mdi:battery-charging",
    ),
    VoltxModbusSensorEntityDescription(
        key="soc",
        name="Battery State of Charge",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
    ),
    VoltxModbusSensorEntityDescription(
        key="vb",
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=2,
        entity_registry_enabled_default=True,
    ),
    VoltxModbusSensorEntityDescription(
        key="cb",
        name="Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        entity_registry_enabled_default=True,
    ),
    VoltxModbusSensorEntityDescription(
        key="tb",
        name="Battery Temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        suggested_display_precision=1,
    ),
    VoltxModbusSensorEntityDescription(
        key="soh",
        name="Battery State of Health",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        icon="mdi:battery-heart",
        entity_registry_enabled_default=True,
    ),
    VoltxModbusSensorEntityDescription(
        key="cli",
        name="Battery Charge Current Limit",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        icon="mdi:current-dc",
    ),
    VoltxModbusSensorEntityDescription(
        key="clo",
        name="Battery Discharge Current Limit",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
        icon="mdi:current-dc",
    ),
    VoltxModbusSensorEntityDescription(
        key="bst",
        name="Battery Status",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        icon="mdi:battery-heart-variant",
    ),
    VoltxModbusSensorEntityDescription(
        key="bcomm",
        name="Battery Comm Status",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        icon="mdi:battery-check",
        entity_registry_enabled_default=True,
    ),
    VoltxModbusSensorEntityDescription(
        key="e_chg_today",
        name="Battery Energy Charged Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        icon="mdi:battery-plus",
    ),
    VoltxModbusSensorEntityDescription(
        key="e_dis_today",
        name="Battery Energy Discharged Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=1,
        icon="mdi:battery-minus",
    ),
    # ── Charge/discharge control sensors ────────────────────────────────────────────
    VoltxModbusSensorEntityDescription(
        key="chflg",
        name="Charge/Discharge Flag",
        device_class=None,
        state_class=None,
        native_unit_of_measurement=None,
        icon="mdi:battery-sync",
    ),
    VoltxModbusSensorEntityDescription(
        key="chpwr",
        name="Charge/Discharge Power Command",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        suggested_display_precision=0,
        icon="mdi:battery-arrow-up-outline",
        entity_registry_enabled_default=True,
    ),
)


# ── Platform setup ────────────────────────────────────────────────────────────


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Voltx Modbus sensors from a config entry."""
    coordinator: VoltxModbusCoordinator = entry.runtime_data

    async_add_entities(
        VoltxModbusSensorEntity(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
        # Only create sensors whose key is present in the first data snapshot.
        # This gracefully handles missing block reads at startup.
        if description.key in (coordinator.data or {})
    )


# ── Entity class ──────────────────────────────────────────────────────────────


class VoltxModbusSensorEntity(
    CoordinatorEntity[VoltxModbusCoordinator],
    SensorEntity,
):
    """A single Voltx Modbus sensor entity."""

    entity_description: VoltxModbusSensorEntityDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: VoltxModbusCoordinator,
        entry: ConfigEntry,
        description: VoltxModbusSensorEntityDescription,
    ) -> None:
        """Initialise the entity."""
        super().__init__(coordinator)
        self.entity_description = description

        # Unique ID: derives from the config-entry unique ID so it is stable
        # across restarts even if the host address changes (via reconfigure).
        self._attr_unique_id = f"{entry.unique_id}_{description.key}"

        # Device info: assings to Inverter or Battery device based on key.
        self._attr_device_info = get_device_info(entry, description.key)

    @property
    def native_value(self) -> Any:
        """Return the current sensor value from coordinator data."""
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
