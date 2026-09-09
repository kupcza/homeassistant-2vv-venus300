#!/usr/bin/env python3
"""Standalone Freecooling diagnostic for the 2VV Venus 300 (AirGenio).

Connects directly over Modbus TCP (no Home Assistant needed) and:

  1. Dumps every Freecooling-relevant register plus the unit's OWN
     real-time clock (TIME sheet, doc 17000-17006) -- easy to miss, but
     the season/allowed-hours window is evaluated against the unit's own
     clock, not your wall clock. If it's wrong or was never set, the
     whole schedule check silently fails no matter what you configure.
  2. Evaluates each Freecooling precondition (enable, temperature,
     season, daily hour window) against the values actually read back,
     and prints a pass/fail verdict for each -- both a wrap-past-midnight
     and a same-day interpretation of the hour window, since the
     datasheet doesn't document which one the firmware actually uses.
  3. Writes FreecoolingMode=1 (the request register) and polls every
     second for ~30s, printing the request register plus the real-time
     status bits (freecooling_active, prefreecooling_active) -- so you
     can see exactly when/whether it reverts, correlated with everything
     above.

Usage:
    pip install pymodbus
    python3 debug_freecooling.py [host] [port] [slave_id] [--activate]

Defaults: host=192.168.0.176, port=502, slave_id=1

By default this is READ-ONLY: it only reads and reports. Pass --activate
to also write FreecoolingMode=1 and watch the result for ~30s (a live
write to the real unit -- same action as pressing it manually).
"""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime

from pymodbus.client import AsyncModbusTcpClient

# ---- Register map (wire addresses = doc "PLC Addresses BASE1" minus 1) ----
# Holding (function 0x03/0x06)
BOOST_TIMER = 20011  # doc 20012, minutes, unit's own boost auto-off
FREECOOLING_ENABLE = 20013  # doc 20014
FREECOOLING_AIRFLOW = 20014  # doc 20015, %
FREECOOLING_TEMP_THRESHOLD = 20015  # doc 20016, °C
FREECOOLING_ON_MONTH = 20016  # doc 20017
FREECOOLING_ON_DAY = 20017  # doc 20018
FREECOOLING_ON_HOUR = 20018  # doc 20019
FREECOOLING_ON_MIN = 20019  # doc 20020
FREECOOLING_OFF_MONTH = 20020  # doc 20021
FREECOOLING_OFF_DAY = 20021  # doc 20022
FREECOOLING_OFF_HOUR = 20022  # doc 20023
FREECOOLING_OFF_MIN = 20023  # doc 20024
BYPASS_TEMP_THRESHOLD = 20036  # doc 20037, °C
SWITCH_ON = 21000  # doc 21001
FAN_POWER_SETPOINT = 21001  # doc 21002, ‰ (x0.1 -> %)
TEMPERATURE_SETPOINT = 21002  # doc 21003, °C
FREECOOLING_MODE = 21010  # doc 21011, the request register

# Input (function 0x04)
GLOBAL_STATUS_RAW = 14999  # doc 15000, bit8 = Freecooling active
GLOBAL_STATUS2_RAW = 15000  # doc 15001, bit6 = Prefreecooling
TEMP_OUTSIDE_TO_UNIT = 15016  # doc 15017, signed, x0.1 °C
ACTUAL_YEAR = 16999  # doc 17000 -- the unit's OWN real-time clock
ACTUAL_MONTH = 17000  # doc 17001
ACTUAL_DAY = 17001  # doc 17002
ACTUAL_DAY_OF_WEEK = 17002  # doc 17003
ACTUAL_HOUR = 17003  # doc 17004
ACTUAL_MIN = 17004  # doc 17005
ACTUAL_SEC = 17005  # doc 17006


def _signed(raw: int) -> int:
    return raw - 0x10000 if raw >= 0x8000 else raw


async def _read_holding(client: AsyncModbusTcpClient, address: int, slave_id: int) -> int:
    result = await client.read_holding_registers(address, count=1, device_id=slave_id)
    return result.registers[0]


async def _read_input(client: AsyncModbusTcpClient, address: int, slave_id: int) -> int:
    result = await client.read_input_registers(address, count=1, device_id=slave_id)
    return result.registers[0]


async def dump_state(client: AsyncModbusTcpClient, slave_id: int) -> dict:
    """Read every relevant register and return the decoded values."""
    r = lambda addr: _read_holding(client, addr, slave_id)  # noqa: E731
    ri = lambda addr: _read_input(client, addr, slave_id)  # noqa: E731

    values = {}
    values["freecooling_enable"] = await r(FREECOOLING_ENABLE)
    values["freecooling_airflow"] = await r(FREECOOLING_AIRFLOW)
    values["freecooling_temp_threshold"] = await r(FREECOOLING_TEMP_THRESHOLD)
    values["freecooling_on_month"] = await r(FREECOOLING_ON_MONTH)
    values["freecooling_on_day"] = await r(FREECOOLING_ON_DAY)
    values["freecooling_on_hour"] = await r(FREECOOLING_ON_HOUR)
    values["freecooling_on_min"] = await r(FREECOOLING_ON_MIN)
    values["freecooling_off_month"] = await r(FREECOOLING_OFF_MONTH)
    values["freecooling_off_day"] = await r(FREECOOLING_OFF_DAY)
    values["freecooling_off_hour"] = await r(FREECOOLING_OFF_HOUR)
    values["freecooling_off_min"] = await r(FREECOOLING_OFF_MIN)
    values["bypass_temp_threshold"] = await r(BYPASS_TEMP_THRESHOLD)
    values["boost_timer"] = await r(BOOST_TIMER)
    values["switch_on"] = await r(SWITCH_ON)
    values["fan_power_setpoint"] = round(await r(FAN_POWER_SETPOINT) * 0.1, 1)
    values["temperature_setpoint"] = await r(TEMPERATURE_SETPOINT)
    values["freecooling_mode"] = await r(FREECOOLING_MODE)

    values["temp_outside"] = round(_signed(await ri(TEMP_OUTSIDE_TO_UNIT)) * 0.1, 1)
    global_status_raw = await ri(GLOBAL_STATUS_RAW)
    global_status2_raw = await ri(GLOBAL_STATUS2_RAW)
    values["global_status_raw"] = global_status_raw
    values["global_status2_raw"] = global_status2_raw
    values["freecooling_active"] = bool(global_status_raw >> 8 & 1)
    values["prefreecooling_active"] = bool(global_status2_raw >> 6 & 1)

    values["unit_year"] = await ri(ACTUAL_YEAR)
    values["unit_month"] = await ri(ACTUAL_MONTH)
    values["unit_day"] = await ri(ACTUAL_DAY)
    values["unit_day_of_week"] = await ri(ACTUAL_DAY_OF_WEEK)
    values["unit_hour"] = await ri(ACTUAL_HOUR)
    values["unit_min"] = await ri(ACTUAL_MIN)
    values["unit_sec"] = await ri(ACTUAL_SEC)

    return values


def _in_season(v: dict) -> bool:
    start = (v["freecooling_on_month"], v["freecooling_on_day"])
    end = (v["freecooling_off_month"], v["freecooling_off_day"])
    now = (v["unit_month"], v["unit_day"])
    if start <= end:
        return start <= now <= end
    return now >= start or now <= end  # wraps across the new year


def _in_hour_window(v: dict, wrap: bool) -> bool:
    start = (v["freecooling_on_hour"], v["freecooling_on_min"])
    end = (v["freecooling_off_hour"], v["freecooling_off_min"])
    now = (v["unit_hour"], v["unit_min"])
    if wrap:
        return now >= start or now < end
    return start <= now < end


def print_report(v: dict) -> None:
    wall_now = datetime.now()
    unit_now = datetime(
        2000 + v["unit_year"] if v["unit_year"] < 100 else v["unit_year"],
        v["unit_month"],
        v["unit_day"],
        v["unit_hour"],
        v["unit_min"],
        v["unit_sec"],
    )

    print("=" * 70)
    print("UNIT'S OWN CLOCK  vs  THIS COMPUTER'S CLOCK")
    print("=" * 70)
    print(f"  Unit reports:     {unit_now.isoformat()}")
    print(f"  This machine:     {wall_now.isoformat()}")
    drift = abs((unit_now - wall_now).total_seconds())
    if drift > 300:
        print(f"  !!! CLOCK MISMATCH: {drift/60:.1f} minutes apart. If this is")
        print("      wrong/unset, the season and allowed-hours window below")
        print("      are being evaluated against the WRONG time entirely.")
    else:
        print(f"  OK, within {drift:.0f} seconds of each other.")

    print()
    print("=" * 70)
    print("FREECOOLING CONFIG (as currently read from the unit)")
    print("=" * 70)
    print(f"  freecooling_enable          = {v['freecooling_enable']} (1=enabled)")
    print(f"  freecooling_temp_threshold  = {v['freecooling_temp_threshold']} C")
    print(f"  bypass_temp_threshold       = {v['bypass_temp_threshold']} C")
    print(f"  temp_outside (unit sensor)  = {v['temp_outside']} C")
    print(
        f"  season window               = "
        f"{v['freecooling_on_month']:02d}-{v['freecooling_on_day']:02d} "
        f"to {v['freecooling_off_month']:02d}-{v['freecooling_off_day']:02d}"
    )
    print(
        f"  daily hour window           = "
        f"{v['freecooling_on_hour']:02d}:{v['freecooling_on_min']:02d} "
        f"to {v['freecooling_off_hour']:02d}:{v['freecooling_off_min']:02d}"
    )
    print(f"  freecooling_mode (request)  = {v['freecooling_mode']}")
    print(f"  switch_on (power)           = {v['switch_on']}")

    print()
    print("=" * 70)
    print("EVALUATED AGAINST THE UNIT'S OWN CLOCK/SENSOR RIGHT NOW")
    print("=" * 70)

    def verdict(label: str, ok: bool) -> None:
        print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

    verdict("freecooling_enable is on", v["freecooling_enable"] == 1)
    verdict(
        f"outdoor temp ({v['temp_outside']}C) < threshold ({v['freecooling_temp_threshold']}C)",
        v["temp_outside"] < v["freecooling_temp_threshold"],
    )
    verdict(
        f"outdoor temp ({v['temp_outside']}C) > bypass floor ({v['bypass_temp_threshold']}C)",
        v["temp_outside"] > v["bypass_temp_threshold"],
    )
    verdict("current date is within the season window", _in_season(v))
    verdict(
        "current time is within the daily hour window (wrap-past-midnight interpretation)",
        _in_hour_window(v, wrap=True),
    )
    verdict(
        "current time is within the daily hour window (same-day interpretation)",
        _in_hour_window(v, wrap=False),
    )
    print("  (Both hour-window interpretations are shown because the datasheet")
    print("   doesn't document which one the firmware actually uses -- if only")
    print("   one of them ever passes while Freecooling still fails to engage,")
    print("   that tells us which interpretation is correct.)")

    print()
    print("=" * 70)
    print("REAL-TIME STATUS BITS")
    print("=" * 70)
    print(f"  freecooling_active (status1 bit8)    = {v['freecooling_active']}")
    print(f"  prefreecooling_active (status2 bit6)  = {v['prefreecooling_active']}")


async def watch_after_activation(
    client: AsyncModbusTcpClient, slave_id: int, seconds: int = 30
) -> None:
    print()
    print("=" * 70)
    print(f"WRITING freecooling_mode=1, THEN POLLING FOR {seconds}s")
    print("=" * 70)
    await client.write_register(FREECOOLING_MODE, 1, device_id=slave_id)

    for i in range(seconds):
        mode = await _read_holding(client, FREECOOLING_MODE, slave_id)
        status1 = await _read_input(client, GLOBAL_STATUS_RAW, slave_id)
        status2 = await _read_input(client, GLOBAL_STATUS2_RAW, slave_id)
        active = bool(status1 >> 8 & 1)
        prefreecool = bool(status2 >> 6 & 1)
        print(
            f"  t+{i:>2}s  freecooling_mode={mode}  "
            f"freecooling_active={active}  prefreecooling_active={prefreecool}"
        )
        await asyncio.sleep(1)


async def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    activate = "--activate" in sys.argv[1:]
    host = args[0] if len(args) > 0 else "192.168.0.176"
    port = int(args[1]) if len(args) > 1 else 502
    slave_id = int(args[2]) if len(args) > 2 else 1

    print(f"Connecting to {host}:{port} (slave {slave_id})...")
    client = AsyncModbusTcpClient(host=host, port=port, timeout=5)
    if not await client.connect():
        print("FAILED TO CONNECT -- check host/port/network.")
        return

    try:
        values = await dump_state(client, slave_id)
        print_report(values)
        if activate:
            await watch_after_activation(client, slave_id)
            print()
            final = await dump_state(client, slave_id)
            print("Final freecooling_mode value:", final["freecooling_mode"])
            print("Final freecooling_active:", final["freecooling_active"])
        else:
            print()
            print("(Read-only mode -- pass --activate to also write")
            print(" FreecoolingMode=1 and watch the result for ~30s.)")
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
