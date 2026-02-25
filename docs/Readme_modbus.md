# Modbus TCP Implementation Guide

## Overview

Notes on the direct Modbus TCP register map for the **Solplanet/Voltx ASW010K-SH** inverter with battery storage,
discovered by scanning the device (slave ID 3) and cross-referenced against the official **AISWEI Modbus specification**
(MB001_ASW GEN-Modbus-en_V2.1.5).

**Address convention:**

- `doc_addr − 30001` = actual Modbus input register address (e.g. doc 31309 → frame addr 1308 ✓)
- `doc_addr − 40001` = actual Modbus holding register address (e.g. doc 41104 → frame addr 1103 ✓)

---

## Connection

| Parameter | Value       |
| --------- | ----------- |
| Protocol  | Modbus TCP  |
| Host      | xx.xx.xx.xx |
| Port      | 502         |
| Slave ID  | 3           |

---

## Verified Register Map — Solplanet/Voltx ASW010K-SH

**Input registers** (Modbus function code 0x04).
Verification method and cross-checks are noted for each entry.

### Inverter Sensors

| Register(s) | Key    | Description           | Type | Scale | Unit | Notes                                         |
| ----------- | ------ | --------------------- | ---- | ----- | ---- | --------------------------------------------- |
| 1307        | `hto`  | Total working hours   | u16  | 1     | h    | Stable counter                                |
| 1308        | `flg`  | Inverter status       | u16  | enum  | —    | 0=Waiting, 1=Normal, 2=Fault, 4=Checking      |
| 1310        | `tmp`  | Inverter temperature  | s16  | 0.1   | °C   | 0x8000 = sensor not fitted                    |
| 1316        | `vbus` | DC bus voltage        | u16  | 0.1   | V    |                                               |
| 1358        | `vac`  | Grid voltage          | u16  | 0.1   | V    |                                               |
| 1359        | `iac`  | AC phase current      | u16  | 0.1   | A    |                                               |
| 1367        | `fac`  | Grid frequency        | u16  | 0.01  | Hz   |                                               |
| 1368–1369   | `sac`  | Apparent power        | s32  | 1     | VA   | pac ÷ sac ≈ pf                                |
| 1370–1371   | `pac`  | Inverter active power | s32  | 1     | W    | Signed                                        |
| 1372–1373   | `qac`  | Reactive power        | s32  | 1     | VAr  | Signed; negative=capacitive                   |
| 1374        | `pf`   | Power factor          | u16  | 0.01  | —    |                                               |
| ----------- | ------ | --------------------- | ---- | ----- | ---- | --------------------------------------------- |

**Note on 32-bit registers:** 32-bit values span two consecutive 16-bit registers in big-endian word order —
the lower-numbered register holds the high word. Use signed int32 (`s32`) interpretation as values can be
negative (e.g. reactive power). Example:

```python
regs = client.read_input_registers(1370, 2)  # [high, low]
raw  = ((regs[0] & 0xFFFF) << 16) | (regs[1] & 0xFFFF)
pac  = struct.unpack('>i', struct.pack('>I', raw))[0]   # signed int32
```

### Holding Registers (Modbus function code 0x03)

#### Writable Control Registers

All writable via FC06 (write single register); inverter applies immediately, no commit step.

| Register | Key         | Description                    | Type    | Raw scale | Range         | Notes                                                                                                  |
| -------- | ----------- | ------------------------------ | ------- | --------- | ------------- | ------------------------------------------------------------------------------------------------------ |
| 1103     | `work_mode` | Work mode                      | u16     | enum      | —             | 2=Self-consumption, 3=Reserve Power, 4=Custom, 5=Time of Use                                           |
| 1152     | `chpwr`     | Charge/discharge power command | **s16** | 1         | −10000–+10000 | Active control in Custom mode. Negative = charge, positive = discharge. Write as two's-complement u16. |
| 1153     | `soc_max`   | Battery SOC max                | u16     | ÷100 = %  | 0–10000       |                                                                                                        |
| 1154     | `soc_min`   | Battery SOC min                | u16     | ÷100 = %  | 0–10000       |                                                                                                        |
| -------- | ----------- | ------------------------------ | ------- | --------- | ------------- | ------------------------------------------------------------------------------------------------------ |

**Charge/discharge status register (read-only):**

| Register | Key     | Description           | Type | Scale | Notes                                                                                                                                                          |
| -------- | ------- | --------------------- | ---- | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1151     | `chflg` | Charge/discharge flag | u16  | enum  | **Read-only status** — 1=Stop, 2=Charging, 3=Discharging. Reflects inverter state; writes have no effect. Updates automatically as `chpwr` drives the battery. |
| -------- | ------- | --------------------- | ---- | ----- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |

**Custom mode charge/discharge control:** Set `work_mode` to 4 (Custom), then write `chpwr` (1152) to command the battery.
The inverter enforces its own current limits and SOC thresholds regardless. Set `chpwr = 0` to idle the battery.
`chflg` updates to reflect the resulting state but is not a command target.

**Writing examples (pyModbusTCP):**

```python
# Set work mode to Custom (4)
client.write_single_register(1103, 4)

# Command battery to charge at 3000 W (s16 −3000 → two's-complement u16 = 0xF448)
client.write_single_register(1152, (-3000) & 0xFFFF)

# Command battery to discharge at 5000 W
client.write_single_register(1152, 5000)

# Idle the battery (power = 0)
client.write_single_register(1152, 0)

# Set SOC min to 20 % (raw value = 2000)
client.write_single_register(1154, 2000)
```

#### Read-only Holding Registers

| Register | Key            | Description       | Type | Notes                               |
| -------- | -------------- | ----------------- | ---- | ----------------------------------- |
| 1150     | `cloud_status` | Cloud comm status | u16  |                                     |
| -------- | -------------- | ----------------- | ---- | ----------------------------------- |

## Device Info Strings (packet ASCII, not polled by integration)

Device info strings are stored as packed ASCII (2 chars per 16-bit register, big-endian).
These are not exposed as HA entities.

| Registers | Content          | Decoded example               |
| --------- | ---------------- | ----------------------------- |
| 1182–1189 | Serial number    | `AL010K1234567890`            |
| 1198–1202 | Model name       | `ASW010K-SH`                  |
| 1209+     | Firmware version | `V610-…`                      |
| --------- | ---------------- | ----------------------------- |

---

## Schedule Input/Output Power (Pin/Pout)

These values (scheduled charge/discharge targets visible in the Solplanet app) are **not** Modbus TCP
registers. They are managed by the cloud dongle via the HTTP API (`getdefine.cgi` → JSON `Pin`/`Pout`,
written via `setting.cgi` POST).

For real-time battery charge/discharge control via Modbus TCP, set `work_mode` to 4 (Custom) and write
`chpwr` (register **1152**) directly. Register 1151 (`chflg`) is a **read-only** status register that
reflects the inverter's current commanded state — it is not a control register and writes have no
observable effect.

### Battery Sensors

| Register(s) | Key           | Description                     | Type    | Scale | Unit | Notes                                                   |
| ----------- | ------------- | ------------------------------- | ------- | ----- | ---- | ------------------------------------------------------- |
| 1606        | `bcomm`       | Battery comm status             | u16     | enum  | —    | 0x000A (10) = OK, 0x0005 = Error                        |
| 1607        | `bst`         | Battery operating status        | u16     | enum  | —    | 0=N/A, 1=Idle, 2=Charging, 3=Discharging, 4=Error       |
| 1616        | `vb`          | Battery voltage                 | u16     | 0.01  | V    | Verified; vb × cb = pb ✓                                |
| 1617        | `cb`          | Battery current                 | **s16** | 0.1   | A    | **Signed**: positive = discharging, negative = charging |
| 1618–1619   | `pb`          | Battery power                   | s32     | 1     | W    | Positive = discharging, negative = charging             |
| 1620        | `tb`          | Battery temperature             | s16     | 0.1   | °C   | Verified                                                |
| 1621        | `soc`         | Battery state of charge         | u16     | 1     | %    | Verified;                                               |
| 1622        | `soh`         | Battery state of health         | u16     | 1     | %    | Verified;                                               |
| 1623        | `cli`         | Charge current limit            | u16     | 0.1   | A    | Verified;                                               |
| 1624        | `clo`         | Discharge current limit         | u16     | 0.1   | A    | Verified;                                               |
| 1625–1626   | `e_chg_today` | Battery energy charged today    | u32     | 0.1   | kWh  | Verified;                                               |
| 1627–1628   | `e_dis_today` | Battery energy discharged today | u32     | 0.1   | kWh  | Verified;                                               |
| ----------- | ------------- | ------------------------------- | ------- | ----- | ---- | ------------------------------------------------------- |

**cb is S16:** When charging, `cb` is negative. Always decode with signed int16:

```python
cb = struct.unpack('>h', struct.pack('>H', raw & 0xFFFF))[0]
```

Registers 1608–1615 return 0xFFFF (individual cell voltages, not populated on this unit).

---

## Discovery Methodology

Registers were found using a scan utility script, which read blocks of input registers
in 125-register chunks (the Modbus protocol maximum per request) and printed each value in multiple
interpretations (u16, s16, ×0.1, ×0.01, s32 pair). A `scan_range_individual()` fallback reads one
register at a time when block reads fail due to holes in the register map (e.g. 1290–1299).

Control registers were identified by setting sentinel values in the Solplanet app and running before/after
snapshots of the entire holding register map, then diffing the results.

Key cross-checks used to confirm sensor candidates:

1. **Battery power:** `vb (1616) × cb (1617) = pb — matched to the watt.
2. **Inverter power:** `pac (1370–1371) ÷ sac  = pf` — matched to two decimal places.
3. **Battery SOC:** with `×1.0` → confirmed against app display.
4. **Battery SOH:** with `×1.0` → confirmed against app display.
5. **Charge power cmd:** s16(1152) → charging, consistent with chflg=2=Charging.
6. **ASCII decoding:** holding regs 1182–1202 decode as packed ASCII matching serial/model/firmware.

---
