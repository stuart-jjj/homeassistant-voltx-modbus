# Development To-Do

Priorities identified after scanning session on 25 February 2026.

---

## P1 — High value, low risk

### 1. Identify input 1632–1633 (doc 31633–31634)

~~The active-power scan found an unidentified s32 ≈ 2448 W immediately after the battery
block.~~

**INVESTIGATED — 2026-02-25. Not a power register.**

Three-condition cross-check (grid import / solar export / oven on + high battery discharge):

| Condition                                         | pac     | pb      | reg 1633 u16 | ×0.1    |
| ------------------------------------------------- | ------- | ------- | ------------ | ------- |
| pac=−2622 W, pb=−2451 W (grid charging battery)   | −2622 W | −2451 W | **2432**     | 243.2 V |
| pac=−1131 W, pb=−1081 W (solar exporting)         | −1131 W | −1081 W | **2434**     | 243.4 V |
| pac=+2871 W, pb=+3005 W (oven on, batt discharge) | +2871 W | +3005 W | **2454**     | 245.4 V |

Reg 1633 tracks **grid voltage** (drifts ~1 V as load rises/falls) — conclusively not a
power register.

**Exhaustive scan completed 2026-02-25:** individual-register sweep of input 1290–1310,
1380–1410, 1400–1559, 1560–1605, 1629–1659 — all returned zero/0xFFFF outside known blocks.

**Why grid/load power is missing from the Modbus TCP map:** Grid import/export and
per-circuit readings in the Solplanet app come from CT clamps reporting via the proprietary cloud protocol
(`getdefine.cgi`). These are not surfaced as Modbus registers.

**This item is closed.** No grid or load power sensor can be added via Modbus TCP.

---

### 2. 'Off Grid work mode register value and EPS mode sensors

When ready (daytime, non-essential circuits acceptable): switch to Off Grid Mode in the
Solplanet app while `scan_registers.py` polls register 1103. Expected value is somewhere
not yet in the enum (current known values: 2=Self-consumption, 3=Reserve Power,
4=Custom, 5=Time of Use).

> Off Grid / EPS mode disconnects from the grid and drops non-essential house
> circuits. Only attempt during daylight hours with battery well charged.

Once confirmed, add to the `work_mode` select entity in
[select.py](custom_components/voltx_modbus/select.py).

---

## P2 — Useful, moderate effort

### 4. Grid power ratio entity (register 1155)

Currently reads 0xFFFF (not configured on this installation). Used to cap grid export
as a percentage — relevant if subject to a DNO export limit.

**Action:** Add as a `number` entity (0–100%, disabled by default) so it's available
without requiring another release later.

---

### 5. Energy dashboard integration (state class)

The kWh sensors (`e_chg_today` 1625–1626, `e_dis_today` 1627–1628) are working but
not declared with `state_class: total_increasing`, so they do not appear in the HA
Energy dashboard.

**Action:** Update sensor descriptions in [sensor.py](custom_components/voltx_modbus/sensor.py)
to add `state_class=SensorStateClass.TOTAL_INCREASING` and
`device_class=SensorDeviceClass.ENERGY` where missing. No new register reads required.

---

### 6. Faster battery-only polling loop

The holding register mirror block at frames 1111–1122 (doc 41112–41123) shadows the
battery input registers (vb, cb, soc, cli, clo) in real time. Could allow a separate,
faster-interval coordinator update for battery state without re-querying the full
register set.

---

## P3 — Background / when opportunity arises

### 7. doc 44003–44012 — grid protection function flags

The scan found 10 consecutive registers containing `1` in this range, suggesting
individual grid protection functions (volt-var, volt-watt, frequency response, etc.)
are enabled at their defaults. Mostly read-only diagnostic interest.

---

### 8. RS485 access

The MB001 spec documents many registers that do not respond over Modbus TCP — comms
settings (40201+), grid protection thresholds (40501+), full firmware version block
(41210+). These are possibly accessible via another RS485 port on the inverter, e.g.
the meter port. Could try to re-run the scans there. Currently the Modbus access is
over ModbusTCP via a USR-304 TCP gateway to the inverter Monitor port CN-707.

---

### 9. Consolidate scan scripts

Three scan scripts have grown organically:

- `scan_registers.py` — targeted input + holding scan with known annotations
- `scan_holding_extended.py` — bulk sweep of doc 40201–45201
- `scan_active_power.py` — power-candidate hunt across input + holding

Merge into a single `scan.py --input --holding --range 1300:1640` style tool for
cleaner future discovery work.

---

## Completed

| Date       | Item                                                                                                                                                                                                                                                                         |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 2026-02-25 | Verified cb (1617) as S16; corrected SOC/SOH scale to ×1.0; added e_chg_today / e_dis_today (1625–1628); added chflg (1151) / chpwr (1152) read                                                                                                                              |
| 2026-02-25 | Confirmed Custom Mode = register value 4; added to work_mode select entity                                                                                                                                                                                                   |
| 2026-02-25 | Scanned 40201–45201 holding registers; found firmware version strings at frame 1700 block; confirmed grid protection flags at doc 44003–44012; confirmed no external CT/meter or EV charger registers responding                                                             |
| 2026-02-25 | Input 1632–1633 CLOSED: two-condition cross-check showed reg 1633 = frozen ~2432 (secondary voltage ×0.1, not power). Full scan of input 1400–1559 during solar export: empty. Grid/load power comes from CT clamp via cloud protocol only — not accessible over Modbus TCP. |
