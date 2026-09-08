# 2VV Venus 300 (AirGenio) for Home Assistant

[![Validate](https://github.com/kupcza/homeassistant-2vv-venus300/actions/workflows/validate.yml/badge.svg)](https://github.com/kupcza/homeassistant-2vv-venus300/actions/workflows/validate.yml)
[![Tests](https://github.com/kupcza/homeassistant-2vv-venus300/actions/workflows/test.yml/badge.svg)](https://github.com/kupcza/homeassistant-2vv-venus300/actions/workflows/test.yml)
[![GitHub tag](https://img.shields.io/github/v/tag/kupcza/homeassistant-2vv-venus300)](https://github.com/kupcza/homeassistant-2vv-venus300/tags)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kupcza&repository=homeassistant-2vv-venus300&category=integration)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=venus300)

A HACS-installable Home Assistant integration for the **2VV Venus 300** heat
recovery ventilation unit (AirGenio control), talking **Modbus TCP** directly
— no YAML `modbus:` platform required.

This is an independent, community project. It is not affiliated with or
endorsed by 2VV s.r.o.

## Why not the built-in `modbus:` integration?

Home Assistant's core `modbus` component is a generic, YAML-configured
platform: every register is polled on its own timer, values are decoded
individually, and there's no config flow, no shared device, and no place to
add device-specific logic (enum decoding, a real `Power`/`Freecooling`
switch with verify-on-write, etc.). This integration is a dedicated,
config-flow-based replacement for a `modbus.yaml` register list, built with
a `DataUpdateCoordinator` and one shared `pymodbus` TCP connection per unit.

## Entities

| Platform | Entity | Register | Notes |
|---|---|---|---|
| switch | Power | holding 21000 | on/off |
| switch | Freecooling mode | holding 21010 | on/off, *requests* freecooling — see below |
| switch | Freecooling enabled | holding 20013 | on/off, config category, master enable — see below |
| switch | Filter hour-based tracking | holding 25018 | on/off, config category — see below |
| button | Reset filter usage hours | holding 21015 | press after replacing a filter — see below |
| number | Fan power setpoint | holding 21001 | 0–100 %, raw is ‰ |
| number | Temperature setpoint | holding 21002 | °C |
| number | Bypass temperature threshold | holding 20036 | °C, config category |
| number | Freecooling airflow | holding 20014 | 50–100 %, config category |
| number | Freecooling temperature threshold | holding 20015 | °C, config category |
| number | Freecooling season/allowed-hours (×8) | holding 20016–20023 | on/off month, day, hour, minute — config category |
| number | Filter lifetime | holding 25019 | 200–3000 hours, config category — see below |
| sensor | Outside → unit temperature | input 15016 | °C |
| sensor | Unit → house temperature | input 15017 | °C |
| sensor | House → unit temperature | input 15021 | °C |
| sensor | Unit → outside temperature | input 15022 | °C |
| sensor | Inlet fan power | input 15012 | % |
| sensor | Outlet fan power | input 15013 | % |
| sensor | Inlet filter life | input 15043 | % |
| sensor | Outlet filter life | input 15044 | % |
| sensor | Inlet/outlet filter pressure drop | input 15026/15027 | Pa, diagnostic — see below |
| sensor | HEPA filter life / pressure drop | input 15046/15047 | %, Pa, diagnostic — see below |
| sensor | Filter monitoring | holding 10162 | enum, diagnostic — which filter(s) are monitored |
| sensor | Bypass position | input 15040 | % |
| sensor | Bypass type | holding 10128 | enum, diagnostic |
| sensor | Temperature sensor selection | holding 25008 | enum, diagnostic |
| sensor | Ventilation mode | holding 24999 | enum, diagnostic |
| sensor | Modbus port (readback) | input 16020 | diagnostic |
| sensor | Global status / status 2 / error 1 / error 2 (raw) | input 14999–15002 | diagnostic, raw 16-bit words (see below) |
| binary_sensor | 40 decoded status/error bits | input 14999–15002 | diagnostic; see `bitfields.py` |

Register addresses are wire (0-based) addresses, one less than the
"PLC Addresses - BASE1" numbers in `MODBUS_V1_FW166_167.xlsx`; this mirrors
the original `modbus.yaml` this project was migrated from.

### Why "Freecooling mode" alone might not do anything

The `Freecooling mode` switch only writes SHARE's `FreecoolingMode` request
register (21010) — it asks the unit to freecool. Whether the unit actually
does depends on three more things, all now exposed as separate entities:

1. **`Freecooling enabled`** (switch, holding 20013) — a master enable at
   the SERVICE level. If this is off, the request switch above does nothing.
2. **`Freecooling temperature threshold`** (number, holding 20015, default
   20 °C) — outdoor temperature must be below this.
3. **The allowed-hours/season window** (8 number entities, holding
   20016–20023) — by factory default, freecooling is only permitted
   **June 1 – September 1, 20:00–06:00**. Outside that window the unit
   ignores freecooling requests entirely, regardless of the two settings
   above.

Check `binary_sensor.freecooling_active` (the unit's actual status, distinct
from the request) and `binary_sensor.prefreecooling_active` (a transitional
state before freecooling fully engages) to see what the unit is really
doing.

### Filter lifetime — when to change filters

The unit tracks filter life two ways, both surfaced here:

1. **Hour-based** (`switch.filter_working_hours_enabled` on): `inlet_filter_life`
   / `outlet_filter_life` count down from 100% to 0% against
   **`number.filter_max_hours`** (SERVICE_HARD `FilterMaxHours`, factory
   default **1440 hours ≈ 60 days**, adjustable 200–3000 hours).
2. **Pressure-based** (if the unit has physical filter dP sensors fitted):
   `sensor.filter_pressure_inlet` / `filter_pressure_outlet` (Pa) reflect
   actual clogging directly, independent of elapsed time.

Either way, watch `binary_sensor.filter_change_due`,
`filter_inlet_warning`/`filter_outlet_warning` (early warning) and
`filter_inlet_error`/`filter_outlet_error` (overdue) for when to actually
change them. **After physically replacing a filter, press
`button.filter_timer_reset`** — this writes SHARE's `FilterClogedTimerReset`
and resets the 100%/hour countdown; skipping it means the life sensors keep
counting down from wherever they were.

`sensor.filter_disable_status` tells you whether inlet, outlet, or both
filters are actively monitored (a factory setting) — useful if one side's
life/pressure reading looks stuck, and `hepa_filter_life` /
`hepa_filter_pressure` are the HEPA-stage equivalents, if fitted.

### Status/error bitfields

`Global status`, `Global status 2`, `Software error 1` and `Software error 2`
are 16-bit words; every documented bit (per `MODBUS_V1_FW166_167.xlsx`,
sheet `STATUS_AHU`) is decoded into its own diagnostic `binary_sensor` in
`bitfields.py`, plus the four raw words are kept as diagnostic `sensor`
entities for troubleshooting. A handful of bits are intentionally omitted:

- `ON/OFF` (global status bit 0) — already covered by the `power` switch.
  (`Freecooling`, bit 8, is *not* omitted — see above, it's the real status,
  distinct from the `freecooling_mode` request switch.)
- `CAV` / `VAV` (global status bits 2/3) — documented `Min == Max == 0` on
  this firmware, i.e. never set.
- Water-heater and AQS-sensor bits — this unit has neither fitted (per the
  note at the top of `modbus.yaml`).

If your unit's configuration differs (e.g. it does have a water heater),
add the relevant `BitSensorSpec` entries in `bitfields.py`.

## Installation

### One click, if your browser is paired with `my.home-assistant.io`

1. [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=kupcza&repository=homeassistant-2vv-venus300&category=integration) — adds this as a HACS custom repository. Click **Download** on the page it opens, then restart Home Assistant.
2. [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=venus300) — starts the config flow (see [Configuration](#configuration) below for what it asks).

### Via HACS (custom repository), manually

1. HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://github.com/kupcza/homeassistant-2vv-venus300`, category **Integration**.
3. Install "2VV Venus 300", restart Home Assistant.

### Manual, without HACS

Copy `custom_components/venus300` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

Settings → Devices & Services → Add Integration → **2VV Venus 300**
(or use the config-flow badge above). You'll be asked for:

- **Host** — the AirGenio unit's IP address.
- **Port** — Modbus TCP port (default `502`).
- **Modbus slave/unit ID** — default `1`.

## Migrating from `modbus.yaml`

If you were previously using a YAML `modbus:` platform config for this unit
(as this project originally was), remove that `modbus:` block — and any
template sensors decoding `bypass_type_raw`/`temp_sensor_selection_raw`/etc.
— after setting up this integration, to avoid duplicate entities.

## Development

```
custom_components/venus300/
  registers.py      # declarative register map (single source of truth)
  bitfields.py       # per-bit decoding of the status/error words
  modbus_client.py  # pymodbus TCP wrapper (locking, read/write)
  coordinator.py     # DataUpdateCoordinator, polls all registers
  entity.py           # shared device info
  config_flow.py, __init__.py, sensor.py, switch.py, number.py, binary_sensor.py
```

To add a register: add a `Register` (and, if it's a config/read-only enum,
an options dict) in `registers.py`, then reference it from the relevant
platform file's spec tuple. To decode another status/error bit, add a
`BitSensorSpec` in `bitfields.py`.

`_doc/MODBUS_V1_FW166_167.xlsx` and `_doc/2VV_AirGENIO_Modbus_RTU_TCP.pdf`
are the vendor documentation this register map and bitfield decoding were
built from — keep them for future reference (e.g. adding heater/AQS
entities for other Venus 300 configurations).

### Tests

```
tests/
  test_registers.py     # block/offset math, encode/decode roundtrips, key uniqueness
  test_bitfields.py      # bit-index validity, no duplicate (register, bit) pairs
  test_translations.py   # every translation_key used in code has a strings.json entry, and vice versa
  test_manifest.py        # manifest.json is well-formed and semver-valid
```

Run with `pip install -r requirements_test.txt && pytest`. These test the
pure data/logic layer (no live Modbus connection, no running Home Assistant
instance); CI runs them on every push/PR via `.github/workflows/test.yml`.

## Versioning

This project follows [Semantic Versioning](https://semver.org/). Every
release bumps `custom_components/venus300/manifest.json`'s `version` and
gets a matching, changelog-entry in [CHANGELOG.md](CHANGELOG.md) and a
`vX.Y.Z` git tag — this is what HACS uses to offer updates.
