"""Data coordinator for Voltx Modbus integration.

Polls the inverter via Modbus TCP and provides data to all sensor entities.
All register reads run in a thread-pool executor to avoid blocking the
Home Assistant event loop (pyModbusTCP is synchronous).

Register map (verified on Solplanet/Voltx ASW010K-SH, firmware v2, slave ID 3).
Doc source: MB001_ASW GEN-Modbus-en_V2.1.5 (AISWEI).
Address convention: doc_addr − 30001 = input frame addr; doc_addr − 40001 = holding frame addr.

  Input registers (function code 0x04):
    1307        hto         Total working hours           u16  ×1      h
    1308        flg         Inverter status               u16  enum    0=Waiting,1=Normal,2=Fault,4=Checking
    1310        tmp         Inverter temperature          s16  ×0.1    °C  (0x8000 = not fitted)
    1316        vbus        DC bus voltage                u16  ×0.1    V
    1358        vac         Grid voltage                  u16  ×0.1    V
    1359        iac         AC phase current              u16  ×0.1    A
    1367        fac         Grid frequency                u16  ×0.01   Hz
    1368–1369   sac         Apparent power                s32  ×1      VA
    1370–1371   pac         Inverter active power         s32  ×1      W
    1372–1373   qac         Reactive power                s32  ×1      VAr
    1374        pf          Power factor                  u16  ×0.01   —
    1606        bcomm       Battery comm status           u16  ×1      enum (0x000A=OK, 0x0005=Err)
    1607        bst         Battery operating status      u16  enum    0=N/A,1=Idle,2=Charging,3=Discharging,4=Error
    1616        vb          Battery voltage               u16  ×0.01   V
    1617        cb          Battery current               s16  ×0.1    A   (positive=discharge, negative=charge)
    1618–1619   pb          Battery power                 s32  ×1      W   (positive=discharge, negative=charge)
    1620        tb          Battery temperature           s16  ×0.1    °C
    1621        soc         Battery state of charge       u16  ×1      %
    1622        soh         Battery state of health       u16  ×1      %
    1623        cli         Charge current limit          u16  ×0.1    A
    1624        clo         Discharge current limit       u16  ×0.1    A
    1625–1626   e_chg_today Battery energy charged today  u32  ×0.1    kWh
    1627–1628   e_dis_today Battery energy discharged today u32 ×0.1   kWh

  Holding registers (function code 0x03):
    1103        work_mode    Work mode                    u16  enum    2=Self-consumption,3=Reserve Power,4=Custom,5=Time of Use
    1150        cloud_status Commbox cloud comm status    u16  ×1      enum (0x000A=10=Online) — READ ONLY, do not write
    1151        chflg        Charge/discharge flag        u16  enum    1=Stop,2=Charging,3=Discharging — READ ONLY status, writes have no effect
    1152        chpwr        Charge/discharge power cmd   s16  ×1      W   (negative=charge, positive=discharge) — active control in Custom mode
    1153        soc_max      Battery SOC max              u16  ÷100    %
    1154        soc_min      Battery SOC min              u16  ÷100    %
"""

from __future__ import annotations

import logging
import struct
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# ── Modbus decoding helpers ───────────────────────────────────────────────────


def _s16(raw: int) -> int:
    """Interpret a raw u16 register value as signed int16."""
    return struct.unpack(">h", struct.pack(">H", raw & 0xFFFF))[0]


def _s32(hi: int, lo: int) -> int:
    """Combine two raw u16 registers into a signed int32 (big-endian word order)."""
    raw = ((hi & 0xFFFF) << 16) | (lo & 0xFFFF)
    return struct.unpack(">i", struct.pack(">I", raw))[0]


# ── Inverter status code map ─────────────────────────────────────────────────
_INV_STATUS: dict[int, str] = {
    0: "Waiting",
    1: "Normal",
    2: "Fault",
    4: "Checking",
}

# ── Battery status code map ──────────────────────────────────────────────────
_BATT_STATUS: dict[int, str] = {
    0: "N/A",
    1: "Idle",
    2: "Charging",
    3: "Discharging",
    4: "Error",
}

# ── Charge/discharge flag map ────────────────────────────────────────────────
_CHFLG: dict[int, str] = {
    1: "Stop",
    2: "Charging",
    3: "Discharging",
}

# ── Coordinator ───────────────────────────────────────────────────────────────


class VoltxModbusCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Manage polling of a single Voltx inverter via Modbus TCP.

    One coordinator per config entry (= per host/port/slave-ID combination).
    Multiple entries can therefore coexist for inverters at different slave IDs
    or on different hosts.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        slave_id: int,
        scan_interval: int,
    ) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{host}_{port}_{slave_id}",
            update_interval=timedelta(seconds=scan_interval),
        )
        self.host = host
        self.port = port
        self.slave_id = slave_id

    # ------------------------------------------------------------------
    # Internal – runs in a thread-pool executor (blocking I/O allowed)
    # ------------------------------------------------------------------

    def _fetch_data(self) -> dict[str, Any]:
        """Synchronous Modbus read – called via async_add_executor_job."""
        # Import here so pyModbusTCP is only loaded in the executor thread.
        from pyModbusTCP.client import ModbusClient  # noqa: PLC0415

        client = ModbusClient(
            host=self.host,
            port=self.port,
            unit_id=self.slave_id,
            timeout=5,
        )

        try:
            if not client.open():
                raise UpdateFailed(
                    f"Cannot open Modbus TCP connection to {self.host}:{self.port} "
                    f"(slave {self.slave_id})"
                )

            data: dict[str, Any] = {}

            # ── Input register block 1: inverter data ─────────────────
            # Read 1300–1379 (80 registers) in a single request.
            regs = client.read_input_registers(1300, 80)
            if regs is not None and len(regs) >= 75:
                # offsets relative to base address 1300
                data["hto"] = regs[1307 - 1300]                          # working hours
                flg_raw = regs[1308 - 1300]
                data["flg"] = _INV_STATUS.get(flg_raw, f"Unknown({flg_raw})")  # inverter status
                tmp_raw = _s16(regs[1310 - 1300])
                data["tmp"] = (                                           # inverter temp °C
                    None if tmp_raw == -32768                             # 0x8000 = not fitted
                    else round(tmp_raw * 0.1, 1)
                )
                data["vbus"] = round(regs[1316 - 1300] * 0.1, 1)        # DC bus voltage V
                data["vac"] = round(regs[1358 - 1300] * 0.1, 1)         # grid voltage V
                data["iac"] = round(regs[1359 - 1300] * 0.1, 1)         # AC phase current A
                data["fac"] = round(regs[1367 - 1300] * 0.01, 2)        # grid frequency Hz
                data["sac"] = _s32(regs[1368 - 1300], regs[1369 - 1300])  # apparent power VA
                data["pac"] = _s32(regs[1370 - 1300], regs[1371 - 1300])  # active power W
                data["qac"] = _s32(regs[1372 - 1300], regs[1373 - 1300])  # reactive power VAr
                data["pf"] = round(regs[1374 - 1300] * 0.01, 2)         # power factor
            else:
                _LOGGER.debug(
                    "Failed to read inverter input registers from %s:%d slave %d",
                    self.host, self.port, self.slave_id,
                )

            # ── Input register block 2a: battery status ────────────────
            # Read 1606–1607 (2 registers): comm status and operating status.
            bsregs = client.read_input_registers(1606, 2)
            if bsregs is not None and len(bsregs) >= 2:
                bcomm_raw = bsregs[0]
                data["bcomm"] = bcomm_raw                          # battery comm status raw
                bst_raw = bsregs[1]
                data["bst"] = _BATT_STATUS.get(bst_raw, f"Unknown({bst_raw})")  # battery op status
            else:
                _LOGGER.debug(
                    "Failed to read battery status registers from %s:%d slave %d",
                    self.host, self.port, self.slave_id,
                )

            # ── Input register block 2b: battery data ────────────────────
            # Read 1616–1628 (13 registers): voltage, current, power, temps,
            # SOC/SOH, current limits, and energy-today counters.
            bregs = client.read_input_registers(1616, 13)
            if bregs is not None and len(bregs) >= 13:
                data["vb"] = round(bregs[0] * 0.01, 2)            # battery voltage V
                data["cb"] = round(_s16(bregs[1]) * 0.1, 1)       # battery current A (S16: neg=charging)
                data["pb"] = _s32(bregs[2], bregs[3])              # battery power W
                data["tb"] = round(_s16(bregs[4]) * 0.1, 1)       # battery temperature °C
                data["soc"] = bregs[5]                             # state of charge %
                data["soh"] = bregs[6]                             # state of health %
                data["cli"] = round(bregs[7] * 0.1, 1)            # charge current limit A
                data["clo"] = round(bregs[8] * 0.1, 1)            # discharge current limit A
                # 1625–1626: battery energy charged today (u32 × 0.1 kWh)
                e_chg_raw = ((bregs[9] & 0xFFFF) << 16) | (bregs[10] & 0xFFFF)
                data["e_chg_today"] = round(e_chg_raw * 0.1, 1)   # kWh
                # 1627–1628: battery energy discharged today (u32 × 0.1 kWh)
                e_dis_raw = ((bregs[11] & 0xFFFF) << 16) | (bregs[12] & 0xFFFF)
                data["e_dis_today"] = round(e_dis_raw * 0.1, 1)   # kWh
            else:
                _LOGGER.debug(
                    "Failed to read battery input registers from %s:%d slave %d",
                    self.host, self.port, self.slave_id,
                )

            # ── Holding register block: inverter settings ─────────────
            # Read 1100–1154 (55 registers) in a single request.
            sregs = client.read_holding_registers(1100, 55)
            if sregs is not None and len(sregs) >= 55:
                data["work_mode"] = sregs[1103 - 1100]            # work mode enum
                data["cloud_status"] = sregs[1150 - 1100]         # cloud comm status (0x000A=10=Online)
                chflg_raw = sregs[1151 - 1100]
                data["chflg"] = _CHFLG.get(chflg_raw, f"Unknown({chflg_raw})")  # charge/discharge flag (read-only status)
                data["chpwr"] = _s16(sregs[1152 - 1100])          # charge/discharge power cmd W (neg=charge)
                data["soc_max"] = sregs[1153 - 1100] // 100       # SOC max % (raw ÷100)
                data["soc_min"] = sregs[1154 - 1100] // 100       # SOC min % (raw ÷100)
            else:
                _LOGGER.debug(
                    "Failed to read settings holding registers from %s:%d slave %d",
                    self.host, self.port, self.slave_id,
                )

            return data

        finally:
            client.close()

    def _write_register(self, address: int, value: int) -> None:
        """Synchronous FC06 write – called via async_add_executor_job."""
        from pyModbusTCP.client import ModbusClient  # noqa: PLC0415

        client = ModbusClient(
            host=self.host,
            port=self.port,
            unit_id=self.slave_id,
            timeout=5,
        )
        try:
            if not client.open():
                raise UpdateFailed(
                    f"Cannot open Modbus TCP connection to {self.host}:{self.port} "
                    f"(slave {self.slave_id})"
                )
            # Mask to u16 so s16 negative values (e.g. chpwr charging) are
            # correctly encoded as two's-complement before transmission.
            if not client.write_single_register(address, value & 0xFFFF):
                raise UpdateFailed(
                    f"Write to register {address} failed on "
                    f"{self.host}:{self.port} slave {self.slave_id}"
                )
        finally:
            client.close()

    async def async_write_register(self, address: int, value: int) -> None:
        """Write a single holding register then schedule a coordinator refresh.

        The refresh is fired as a background task so the UI call returns
        immediately without waiting for the next full Modbus poll round-trip.
        """
        await self.hass.async_add_executor_job(self._write_register, address, value)
        self.hass.async_create_task(self.async_request_refresh())

    # ------------------------------------------------------------------
    # DataUpdateCoordinator interface
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data – delegates blocking I/O to the executor."""
        try:
            return await self.hass.async_add_executor_job(self._fetch_data)
        except UpdateFailed:
            raise
        except Exception as exc:
            raise UpdateFailed(
                f"Unexpected error communicating with {self.host}:{self.port} "
                f"slave {self.slave_id}: {exc}"
            ) from exc

    async def async_validate_connection(self) -> None:
        """Try a single register read to validate connection parameters.

        Raises ConfigEntryNotReady on failure so the config-flow validator
        can surface the error to the user.
        """
        try:
            data = await self.hass.async_add_executor_job(self._fetch_data)
        except Exception as exc:
            raise ConfigEntryNotReady(
                f"Cannot connect to inverter at {self.host}:{self.port} "
                f"slave {self.slave_id}: {exc}"
            ) from exc
        if not data:
            raise ConfigEntryNotReady(
                f"Inverter at {self.host}:{self.port} slave {self.slave_id} "
                "returned no data – check slave ID."
            )
