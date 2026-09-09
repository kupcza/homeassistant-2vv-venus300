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
| button | Boost | holding 21008 | press for a self-clearing timed boost — see below |
| button | Reset filter usage hours | holding 21015 | press after replacing a filter — see below |
| number | Fan power setpoint | holding 21001 | 20–100 %, step 10, raw is ‰ — "off" is `switch.power` |
| number | Boost duration (HA button only) | *(computed in HA)* | 1–60 min, default 5, config category — see below |
| number | Boost duration (unit, all triggers) | holding 20011 | 1–60 min, default 3, config category — see below |
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
| sensor | Filter usage (estimated) | *(computed in HA)* | hours since last reset — see below |
| sensor | Filter usage % (estimated) | *(computed in HA)* | % of `filter_max_hours` — see below |
| sensor | Filter usage last reset | *(computed in HA)* | timestamp, diagnostic |
| sensor | Bypass position | input 15040 | % |
| sensor | Bypass type | holding 10128 | enum, diagnostic |
| sensor | Temperature sensor selection | holding 25008 | enum, diagnostic |
| sensor | Ventilation mode | holding 24999 | enum, diagnostic |
| sensor | Modbus port (readback) | input 16020 | diagnostic |
| sensor | Global status / status 2 / error 1 / error 2 (raw) | input 14999–15002 | diagnostic, raw 16-bit words (see below) |
| binary_sensor | 40 decoded status/error bits | input 14999–15002 | diagnostic; see `bitfields.py` |
| binary_sensor | Freecooling conditions met | *(computed in HA)* | diagnostic; excludes `freecooling_enable` — see below |

Register addresses are wire (0-based) addresses, one less than the
"PLC Addresses - BASE1" numbers in `MODBUS_V1_FW166_167.xlsx`; this mirrors
the original `modbus.yaml` this project was migrated from.

### Freecooling: what actually controls it (confirmed by live testing)

**`switch.freecooling_mode` (SHARE `FreecoolingMode`, register 21010) does
not reliably work as a manual on-demand override.** Confirmed by repeated
live testing against a real unit: writing `1` succeeds at the protocol
level (no Modbus error; the device even echoes the value back in the write
response) — but an immediate readback already shows `0` again, every time,
even with every other condition below satisfied. The unit's own firmware
appears to recompute and overwrite this register on its own control loop,
faster than any external write can stick. Don't rely on this switch for
on-demand control; the automatic scheduler below is what's actually
confirmed to work.

**What the automatic scheduler evaluates** (four conditions, all exposed
as entities):

1. **`Freecooling enabled`** (switch, holding 20013) — a master enable at
   the SERVICE level.
2. **`Freecooling temperature threshold`** (number, holding 20015) —
   outdoor temperature must be below this. Confirmed hysteresis: it can
   stay active briefly even after outdoor temp ticks slightly *above* the
   threshold, rather than dropping out the instant it's crossed.
3. **The allowed-hours/season window** (8 number entities, holding
   20016–20023). **Confirmed empirically**: the daily hour window wraps
   past midnight — evaluated as `now ≥ on_hour OR now < off_hour`, not a
   same-day range. So `freecooling_on_hour = 22`, `freecooling_off_hour = 6`
   (an overnight window) is normal and correct — `on_hour` being
   numerically larger than `off_hour` is expected for that shape, not a
   misconfiguration.
4. A hardware/mechanism precondition — see below.

Check `binary_sensor.freecooling_active` (the unit's real, confirmed status)
and `binary_sensor.prefreecooling_active` (a transitional state before it
fully engages) — these reflect ground truth from direct register reads,
independent of whatever `switch.freecooling_mode` shows.

**`binary_sensor.freecooling_conditions_met`** answers "would Freecooling
run right now, ignoring whether it's enabled" — conditions 2–4 above,
deliberately excluding `freecooling_enable` (check that separately). Its
attributes (`temperature_ok`, `season_ok`, `hour_window_ok`) break down
which specific condition is or isn't currently satisfied, for at-a-glance
troubleshooting instead of comparing several entities by hand. Computed in
`freecooling_conditions.py` using the unit's own real-time clock (also
newly exposed, read every poll — see `registers.py`'s `TIME_BLOCK`), not
Home Assistant's, since that's what the scheduler itself is confirmed to
use.

### The actual cooling mechanism: fan control, not a bypass damper

`sensor.bypass_type` reading "none" on units like this one is **not
necessarily a misconfiguration** — confirmed by directly observing a real
active Freecooling cycle:

```
freecooling_active = True,  bypass_position = 100% (static/non-functional)
inlet_fan_power  = 60%   (supply fan running)
outlet_fan_power =  0%   (exhaust fan OFF)

TempEXT1 (raw outside air)        = 18.6°C
TempEXT2 (supply air TO house)    = 19.8°C   (+1.2°C — barely tempered)
TempINT1 (extract air FROM house) = 25.1°C
TempINT2 (exhaust, stagnant)      = 19.3°C   (not actively flowing)
```

This unit's recuperator is a **plate exchanger** (FACTORY_SET `RecupType`
= 1 — a fixed core with no moving parts, unlike a rotary wheel which could
just stop spinning to achieve the same effect). Instead, when Freecooling
engages, the unit **stops the exhaust fan entirely** while keeping the
supply fan running. Heat exchangers need continuous flow on *both* sides
to keep transferring heat — the same reason a car radiator stops cooling
anything if the coolant flow stops, even with air still blowing through
it. With the exhaust side stalled, incoming outside air passes through the
core nearly untempered (confirmed: only ~1°C rise, consistent with duct/
casing thermal mass rather than active exchange) — achieving the same
practical result as a bypass damper, without needing one.

**To verify real cooling is happening** (not just the status bit), compare
`sensor.temperature_unit_to_house` to `sensor.temperature_outside_to_unit`
during an active cycle — they should be close (within a couple °C). A
large gap would mean the exchanger is still actively tempering the air
despite the status bit, i.e. not real freecooling.

### Overpressure consideration (supply-only operation)

Since only the supply fan runs during Freecooling, positive pressure
builds up in the house relative to outside. Confirmed **not** fully
sealed off, though: `Status_DO_2_Flap_outlet` (the exhaust duct's own
motorized flap, a separate register from the fan) reads **OPEN** even
while `outlet_fan_power = 0%`. So the exhaust path stays physically open —
positive pressure has a passive relief route directly back through the
idle exhaust fan/duct, in addition to normal building leakage.

Generally not a concern for typical homes, but worth being aware of if:
- Your house is very airtight (e.g. Passive House level) — less natural
  leakage means more noticeable pressure (doors harder to close,
  whistling at gaps).
- You have an **open-flue** (non-room-sealed) combustion appliance —
  positive pressure can push exhaust gases back down a flue. Room-sealed/
  balanced-flue appliances aren't affected.

None of this is configurable via Modbus — it's how the firmware
implements Freecooling on this hardware variant.

### Debugging Freecooling yourself

`scripts/debug_freecooling.py` — standalone, no Home Assistant needed.
Dumps every Freecooling-relevant register plus the unit's own real-time
clock (the schedule is evaluated against the unit's clock, not your wall
clock — worth checking they actually agree), evaluates each precondition
against live values, and can optionally activate Freecooling and watch
the result for ~30s:

```
pip install pymodbus
python3 scripts/debug_freecooling.py [host] [port] [slave_id]              # read-only
python3 scripts/debug_freecooling.py [host] [port] [slave_id] --activate   # also writes + watches
```

### Self-clearing Boost button — two different timers, on purpose

`button.boost` writes SHARE's `BoostMode` (doc 21009) directly to activate
the unit's own boost airflow, then schedules its own automatic turn-off
after `number.boost_timer_minutes` (default 5, adjustable 1–60, purely a
Home Assistant-side setting with no Modbus register of its own). This
simulates a physical boost push-button without needing an external Home
Assistant automation to manage the countdown — trigger it from a dashboard
button, a voice command, or any automation.

Like a physical push-button, it's momentary: there's no "off" state to
toggle. Pressing it again while a boost is already running **restarts the
countdown** for a fresh full duration rather than cancelling it — there's
no "press to cancel early" here; use `switch.power` if you want to stop
everything immediately, or just let the countdown finish.

**This is deliberately separate from `number.boost_timer`**, which writes
the unit's *own* `BoostTimer` register (SERVICE, doc 20012, default **3
minutes**). The unit has a physical wired input for boost (`Status_DI_5_Boost`
in its status word — e.g. a wall switch, wired independently of Home
Assistant) and presumably a control-panel trigger too; both use the unit's
own `BoostTimer` to decide how long boost runs, entirely outside Home
Assistant's knowledge or control.

So: **`number.boost_timer_minutes` only affects `button.boost`** (the
HA-managed one). **`number.boost_timer` affects every other way of
triggering boost** — the physical switch, the control panel — since it's
the unit's own setting. Changing one does not change the other. If you want
a physical boost button in the house to run for a different duration,
adjust `number.boost_timer`, not `number.boost_timer_minutes`.

Note: the countdown itself isn't restored across a Home Assistant restart
— if one happens mid-boost, Home Assistant has no memory of it, though the
unit itself keeps running boost until told otherwise (its own `BoostTimer`
will still end it, just not necessarily on the schedule Home Assistant had
in mind). `binary_sensor.boost_mode_active` (from the unit's own status
word) always reflects the unit's real state regardless of any of this.

**Restoring state after boost ends:** the datasheet documents a separate
`BoostFlow` airflow setting distinct from `fan_power_setpoint`, which
suggests the unit resumes its prior fan speed/power on its own once
`BoostMode` returns to 0 — but this isn't explicitly confirmed. As a safety
net, `switch.power` and `number.fan_power_setpoint` are snapshotted on the
*first* press of a sequence (repeated presses don't re-snapshot, so the
true pre-boost state survives a restarted countdown) and explicitly
written back once the countdown finally elapses.

### Filter lifetime — when to change filters

The unit tracks filter life two ways, both surfaced here:

1. **Hour-based** (`switch.filter_working_hours_enabled` on): `inlet_filter_life`
   / `outlet_filter_life` move against **`number.filter_max_hours`**
   (SERVICE_HARD `FilterMaxHours`, factory default 1440 hours ≈ 60 days —
   the datasheet lists 200–3000 as "typical", but it's a plain register and
   real units have been seen configured well outside that, so the number
   entity's range isn't clamped to it).
2. **Pressure-based** (if the unit has physical filter dP sensors fitted):
   `sensor.filter_pressure_inlet` / `filter_pressure_outlet` (Pa) reflect
   actual clogging directly, independent of elapsed time.

Either way, watch `binary_sensor.filter_change_due`,
`filter_inlet_warning`/`filter_outlet_warning` (early warning) and
`filter_inlet_error`/`filter_outlet_error` (overdue) for when to actually
change them. **After physically replacing a filter, press
`button.filter_timer_reset`** — this writes SHARE's `FilterClogedTimerReset`
and resets the countdown; skipping it means the life sensors keep counting
from wherever they were.

`sensor.filter_disable_status` tells you whether inlet, outlet, or both
filters are actively monitored (a factory setting) — useful if one side's
life/pressure reading looks stuck, and `hepa_filter_life` /
`hepa_filter_pressure` are the HEPA-stage equivalents, if fitted.

**Known caveat — `%` life stuck at 0% with no physical dP sensor fitted:**
observed on a real unit with `filter_working_hours_enabled` on continuously
since a filter change, `filter_max_hours` set, and both
`filter_pressure_inlet`/`filter_pressure_outlet` reading 0 (no physical
differential-pressure sensor fitted) — `inlet_filter_life`/
`outlet_filter_life` stayed at 0% for weeks regardless. This suggests the
`%` registers are sourced from the (unfitted) pressure sensor on this
firmware, independent of the hour-based tracking enable/threshold, which
instead appears to drive `binary_sensor.filter_inlet_warning`/
`filter_outlet_warning`/`filter_change_due` directly.

**If your unit has no physical filter dP sensor** (check
`filter_pressure_inlet`/`filter_pressure_outlet` — near-zero and never
moving means no sensor), don't rely on the `%` sensors for "when to
change"; watch the warning/error binary sensors instead — they appear to
reflect the hour-based comparison correctly even when the percentage
doesn't. This hasn't been confirmed against 2VV's firmware source, only
observed behavior — if you find out more (or your unit does have working
`%`), a PR/issue updating this note is welcome.

### Filter usage tracked independently in Home Assistant

Because the unit's own `%` can be permanently stuck at 0% (above), this
integration also tracks estimated filter usage **itself**, independent of
the unit's internal logic:

- `sensor.filter_usage_hours` — hours accumulated since the last reset,
  counted only while `switch.power` is on (matching what "filter **working**
  hours" means) — polled and accumulated every update, persisted across
  Home Assistant restarts.
- `sensor.filter_usage_percent` — `filter_usage_hours` ÷ the live
  `number.filter_max_hours` value read from the unit, as a percentage.
- `sensor.filter_usage_reset_at` — when the tracker was last reset
  (diagnostic).

**Pressing `button.filter_timer_reset` resets both**: the unit's own
`FilterClogedTimerReset` register *and* this Home-Assistant-side tracker.
This is why it matters to use the HA button rather than the unit's own
control-panel reset from now on — **if you reset a filter via the unit's
physical display instead, this tracker has no way to know and will keep
counting past the real reset point.**

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

### Known limitation: no icon in the HACS repository list

This integration ships a brand icon the modern way (`custom_components/venus300/brand/icon.png`,
served by Home Assistant's own [Brands Proxy API](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api)
since HA 2026.3), which is why `hacs/action` validation passes. HACS's own
dashboard, however, still only fetches icons from the older central
`brands.home-assistant.io` CDN and doesn't yet know about that mechanism —
a currently open upstream bug
([hacs/integration#5223](https://github.com/hacs/integration/issues/5223),
fix in progress at [hacs/frontend#937](https://github.com/hacs/frontend/pull/937)).
Nothing to fix here; it'll start showing once HACS ships that update.

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

### Translations

`strings.json` is the source of truth; `translations/<lang>.json` are
verbatim copies with only the `name`/`description`/`state` values
translated — same keys, same structure. Currently English (`en`), Czech
(`cs`), Turkish (`tr`), and Romanian (`ro`). To add a language, copy
`strings.json` to `translations/<code>.json`, translate the values, and
add the language code to `TRANSLATED_LANGUAGES` in
`tests/test_translations.py`, which enforces that every translation file's
key structure exactly matches `strings.json`.

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
release bumps `custom_components/venus300/manifest.json`'s `version`, gets
a matching entry in [CHANGELOG.md](CHANGELOG.md), and is tagged `vX.Y.Z`.
Pushing that tag triggers `.github/workflows/release.yml`, which publishes
a **GitHub Release** for it (extracting that version's CHANGELOG section as
the release notes) — HACS checks for **Releases**, not just tags, to offer
updates, so this step is required, not cosmetic.
