# Voltx Modbus — Home Assistant Integration

## What it does

This integration supports a modbusTCP connection to a Solplanet/Voltx inverter and battery. It does not expose all the entities of other integrations, just enough to control the inverter and battery for automated charge/discharge with power setpoint. You would still need another integration to see information such as grid and PV meter values.

## Features
- Supports single-phase inverters
- Supports min 5s refresh times
- Sensors for inverter and battery
- Battery mode control
- Inverter power setpoint control
- Inverter SOC min/max control
- Modbus RTU-over-TCP (requires TCP gateway)


**Config flow** — go to _Settings → Devices & Services → Add Integration → Voltx Modbus_ and enter **host IP**, **port** (default 502) and **slave ID** (default 3). The flow validates the connection before saving. It support multiple inverters at different slave IDs — each gets its own HA device but that's not been tested.


## Installation

#### With HACS

[![Open in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=stuart-jjj&repository=homeassistant-voltx-modbus&category=integration)

#### Manual installation

1. Place `voltx_modbus` directory inside `config/custom_components` directory
2. Restart Home Assistant.

## Setting Up

1. Add Voltx Modbus from the Integration page.
2. Enter the IP address or hostname of your Solplanet/Voltx TCP gateway device, the modbus port and slaveID value.

## Structure

```
custom_components/voltx_modbus/
├── __init__.py          – entry setup, platform forwarding, options listener
├── config_flow.py       – UI config flow + options flow
├── const.py             – constants (domain, defaults)
├── coordinator.py       – DataUpdateCoordinator (Modbus polling via executor)
├── device_info.py       – DeviceInfo helpers; splits entities across Inverter and Battery devices
├── manifest.json        – HACS/HA metadata, requires pyModbusTCP==0.3.0
├── number.py            – writable number entities (e.g. SOC max/min)
├── select.py            – writable select entities (e.g. work mode)
├── sensor.py            – read-only sensor entities
├── strings.json         – config flow UI strings
└── translations/
    └── en.json          – English translations for UI
hacs.json                – HACS metadata
```

**Two devices per config entry:**

Each config entry creates two linked HA devices:

- **Voltx Inverter** — AC/grid sensors and work-mode control
- **Voltx Battery** — battery sensors and charge/discharge controls (shown as a sub-device of the inverter)

**Options flow** — click _Configure_ on the integration card to change the polling interval (5–3600 s slider, default 30 s).
