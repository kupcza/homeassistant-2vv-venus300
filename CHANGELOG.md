# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [0.11.0] - 2026-09-10

### Added

- `button.force_freecooling`: manually triggers Freecooling on demand.
  Confirmed live that Freecooling's start condition is **edge-triggered**
  on the unit's own clock crossing `freecooling_on_hour:freecooling_on_min`
  — not a level check re-evaluated continuously — which explains a
  previously unresolved anomaly where every tracked condition read `True`
  simultaneously yet Freecooling never started. This button snapshots the
  configured start time, nudges it to just past the unit's current clock
  to fire that edge, then restores the original start time once it's had
  time to latch on. See README's "Manually triggering Freecooling" section
  and the new `freecooling_force.py`. **Confirmed working end-to-end on a
  real unit** shortly after release.

## [0.10.0] - 2026-09-10

### Added

- Automatic clock sync: the unit's own real-time clock (`TIME` sheet) was
  found sitting at its factory default (`2000-01-01 00:00:00`, confirmed
  live — never set) and drifting freely. Since every schedule-based
  feature (Freecooling's season/hour window) is evaluated against this
  clock, not Home Assistant's, this integration now corrects it
  automatically: once when it starts, and every 24h after that, whenever
  drift exceeds 60 seconds. Uses `TIME_DRIVER`'s `Set*` holding registers
  plus `SetFlag=1` to commit — confirmed live that the flag self-clears
  back to `0` once applied, unlike `FreecoolingMode`'s broken behavior.
- `sensor.unit_clock_drift` — current offset in seconds (positive = unit
  ahead, negative = behind).
- `button.sync_unit_clock` — forces an immediate sync on demand (e.g.
  right after a power outage).
- New `time_sync.py` module with the sync/drift logic, and
  `tests/test_time_sync.py` covering drift calculation and the
  threshold-gated auto-sync.

## [0.9.1] - 2026-09-10

### Added

- Three new diagnostic binary sensors breaking `freecooling_conditions_met`
  down into its individual parts, so it's obvious at a glance which
  precondition is failing instead of digging into attributes:
  `binary_sensor.freecooling_temperature_met`,
  `binary_sensor.freecooling_season_met`,
  `binary_sensor.freecooling_hour_window_met`.
- Translated to Czech, Turkish, and Romanian.

### Changed

- `binary_sensor.freecooling_conditions_met` no longer exposes
  `temperature_ok`/`season_ok`/`hour_window_ok` as attributes — that
  information moved to the three dedicated sensors above. The combined
  sensor itself (the overall AND of all three) is unchanged.

## [0.9.0] - 2026-09-09

### Removed (breaking)

- `switch.freecooling_mode`: repeated live testing confirmed writing to
  its underlying register (SHARE `FreecoolingMode`, 21010) does not
  reliably work — the unit's own firmware overwrites it before the next
  readback, every time. Converting it to a read-only sensor wasn't a
  better option either, since that register almost always reads `0`
  regardless of real Freecooling status, making it actively misleading
  either way. Removed rather than ship something that looks like a
  working control but isn't.

  Use `binary_sensor.freecooling_active` (real, confirmed status),
  `binary_sensor.freecooling_conditions_met` (would it run right now,
  added in 0.8.0), and `switch.freecooling_enable` (the master enable)
  instead — together they cover what this switch never reliably did.
  `FREECOOLING_MODE` remains defined in `registers.py` for reference.

If you had automations calling `switch.turn_on`/`turn_off` on
`switch.freecooling_mode`, remove them — they were never having a
confirmed effect anyway.

## [0.8.0] - 2026-09-09

### Added

- `binary_sensor.freecooling_conditions_met`: answers "would Freecooling
  run right now" by evaluating temperature, season, and hour-window
  conditions (deliberately excluding `freecooling_enable`, which has its
  own switch) — with a `temperature_ok`/`season_ok`/`hour_window_ok`
  attribute breakdown for troubleshooting. Confirmed live against the real
  unit: `all_met` correctly matched `freecooling_active` once combined
  with `freecooling_enable`.
- The unit's own real-time clock (TIME sheet, previously unused) is now
  polled every cycle and used for this evaluation — confirmed the
  scheduler evaluates its season/hour window against this clock, not
  Home Assistant's.
- New `freecooling_conditions.py` module with the evaluation logic
  (fixed a same-day-vs-wrap hour-window bug caught by its own test suite
  before shipping — the wrap formula is only valid when `on_hour >
  off_hour`) and `tests/test_freecooling_conditions.py` covering both
  same-day and wrap-past-midnight window shapes.

## [0.7.0] - 2026-09-09

### Added

- Translations: Czech (`cs`), Turkish (`tr`), and Romanian (`ro`), covering
  the config flow and all entity names/enum states. `strings.json` remains
  the source of truth; each language file mirrors its exact key structure.
- `tests/test_translations.py` now asserts every translation file's key
  structure exactly matches `strings.json`, for all four languages
  (`en`/`cs`/`tr`/`ro`), so a future change to `strings.json` that isn't
  mirrored everywhere fails CI instead of shipping silently broken.

## [0.6.1] - 2026-09-09

### Documentation

- Documented findings from live debugging a real unit's Freecooling
  behavior (see README):
  - **Confirmed** `switch.freecooling_mode` does not reliably work as a
    manual override — writes succeed at the protocol level but are
    overwritten by the unit's own scheduler before the next readback,
    every time. Noted directly in `registers.py` next to
    `FREECOOLING_MODE`.
  - **Confirmed** the daily allowed-hours window wraps past midnight
    (`now ≥ on_hour OR now < off_hour`) — an overnight window like
    22:00→06:00 is normal, not a misconfiguration.
  - **Confirmed** `bypass_type = none` is not necessarily a
    misconfiguration: on a plate-exchanger unit, Freecooling is achieved
    by stopping the exhaust fan (heat exchange needs flow on both sides)
    rather than a physical bypass damper, and the exhaust flap stays
    open (not sealed) even with its fan off.
- Added `scripts/debug_freecooling.py`, a standalone (no Home Assistant
  needed) diagnostic that dumps every Freecooling-relevant register plus
  the unit's own real-time clock, evaluates each precondition, and can
  optionally activate Freecooling and watch the result live. Read-only
  by default; `--activate` opts into the live write+watch.

No functional changes to the integration itself.

## [0.6.0] - 2026-09-08

### Changed (breaking)

- Replaced `switch.boost_active` with **`button.boost`**: a momentary
  action is a better fit than a persistent switch for a self-clearing,
  timed boost. Pressing it (re)starts a fresh countdown, matching a
  physical push-button, rather than toggling on/off — there's no "press
  to cancel early" now; use `switch.power` to stop everything immediately
  instead. The snapshot/restore-on-end safety net (added in 0.4.1) now
  only snapshots on the *first* press of a sequence, so repeated presses
  extending the boost don't lose track of the true pre-boost state.
- `number.boost_timer_minutes` renamed display name to "Boost duration
  (HA button only)" to match.

If you had automations or dashboards calling `switch.turn_on`/
`switch.turn_off` on `switch.boost_active`, change them to `button.press`
on `button.boost`.

## [0.5.1] - 2026-09-08

### Changed

- `number.fan_power_setpoint` constrained from a plain 0–100/step‑1 range to
  **20–100, step 10** (20, 30, ..., 100) — matching the unit's practical
  minimum airflow (`FACTORY_SET MinFlowManual`, default 20%) and giving a
  coarser, more practical dashboard slider. "Off" remains a separate
  concern via `switch.power`, unaffected by this change. Note: Home
  Assistant's `number.set_value` service doesn't reject non-multiples of
  `step` server-side — only the dashboard slider snaps to increments of 10.

## [0.5.0] - 2026-09-08

### Added

- `number.boost_timer`: exposes the unit's **own** `BoostTimer` register
  (SERVICE, doc 20012, 1–60 min, default 3) — previously undiscovered.
  Unlike `number.boost_timer_minutes` (which only times out
  `switch.boost_active`'s Home-Assistant-managed activation), this governs
  boost duration for *every* trigger source: the physical wired boost
  switch (`Status_DI_5_Boost`), the control panel, and Modbus. The two are
  intentionally independent — see the README for which one to adjust for
  what.
- Renamed the two boost-duration entities' display names to
  "Boost duration (HA switch only)" / "Boost duration (unit, all
  triggers)" to make the distinction unmistakable in the UI.

## [0.4.1] - 2026-09-08

### Added

- `switch.boost_active` now snapshots `switch.power` and
  `number.fan_power_setpoint` right before activating boost, and
  explicitly restores them when boost ends (by timer or manual
  turn-off) — a safety net in case the unit doesn't fully resume its
  prior state on its own once `BoostMode` returns to 0. Added
  `tests/test_boost_switch.py` covering the snapshot/write/restore logic.

## [0.4.0] - 2026-09-08

### Added

- `switch.boost_active`: activates the unit's real boost airflow (SHARE
  `BoostMode`, doc 21009 — previously only readable via
  `binary_sensor.boost_mode_active`, never writable) and automatically
  turns itself back off after a configurable duration — simulating a
  physical "boost button" without an external Home Assistant automation
  managing the timeout.
- `number.boost_timer_minutes`: the boost duration (1–60 minutes, default
  5). Purely a Home Assistant-side setting, no Modbus register — restores
  across restarts.

## [0.3.0] - 2026-09-08

### Added

- Home-Assistant-side filter usage tracking (`filter_usage.py`),
  independent of the unit's own (sometimes non-functional — see the 0.2.4
  caveat) `%` registers:
  - `sensor.filter_usage_hours` — hours accumulated since the last reset,
    counted only while the unit is powered on, persisted across Home
    Assistant restarts.
  - `sensor.filter_usage_percent` — `filter_usage_hours` against the live
    `filter_max_hours` value read from the unit.
  - `sensor.filter_usage_reset_at` — diagnostic timestamp of the last
    reset.
  - `button.filter_timer_reset` now resets both the unit's own register
    and this tracker. Resetting via the unit's own control panel instead
    does not reset the Home Assistant side.

## [0.2.4] - 2026-09-08

### Documentation

- README: documented an observed real-world caveat — on a unit with no
  physical filter differential-pressure sensor fitted,
  `inlet_filter_life`/`outlet_filter_life` stay at 0% indefinitely even
  with `filter_working_hours_enabled` on and `filter_max_hours` set,
  regardless of elapsed time. The hour-based comparison appears to still
  correctly drive `filter_inlet_warning`/`filter_outlet_warning`/
  `filter_change_due`, so those are the reliable "time to change" signal
  on such units. Unconfirmed against firmware source — observed behavior
  only.

## [0.2.3] - 2026-09-08

### Fixed

- `number.filter_max_hours` range widened from the datasheet's "typical"
  200–3000 to the register's actual limits (0–65535): a real unit was
  observed configured to 5000, outside the old bound.

### Documentation

- README: added troubleshooting guidance for `inlet_filter_life`/
  `outlet_filter_life` reading stuck at 0% shortly after a filter change —
  check `filter_working_hours_enabled` and `filter_pressure_inlet`/
  `filter_pressure_outlet` to tell hour-based tracking apart from an
  unfitted/idle pressure sensor. Also flagged that the direction of the
  life/usage percentage (counts up vs. down) isn't confirmed by the
  datasheet.

## [0.2.2] - 2026-09-08

### Changed

- Renamed the filter-reset button's display name from "Reset filter timer"
  to "Reset filter usage hours" for clarity. Entity ID/unique ID unchanged
  (`button.filter_timer_reset`), so nothing breaks for existing installs.

## [0.2.1] - 2026-09-07

### Fixed

- HACS repository validation (`hacs/action`): repository made public, given a
  description and topics, Issues enabled, and added a bundled brand icon
  (`custom_components/venus300/brand/icon.png` + `icon@2x.png`) so the
  `brands` check passes without waiting on a PR to the central
  `home-assistant/brands` repository. No functional/runtime changes.

## [0.2.0] - 2026-09-07

### Added

- Filter lifetime tracking, exposed from the SERVICE_HARD sheet's
  `FilterMaxHours`/`FilterWoringHours` registers, previously not surfaced:
  - `number.filter_max_hours` — the configurable filter lifetime (200–3000
    hours, factory default 1440).
  - `switch.filter_working_hours_enabled` — whether the unit tracks filter
    life by elapsed hours (vs. differential-pressure reading).
  - `button.filter_timer_reset` — press after physically replacing a
    filter to reset `inlet_filter_life`/`outlet_filter_life` back to 100%.
- `sensor.filter_pressure_inlet` / `filter_pressure_outlet` (Pa) — filter
  differential-pressure readings, decoded from words already fetched by
  the existing status read block (no extra Modbus transaction). Only
  meaningful if the unit has physical dP sensors fitted.
- `sensor.hepa_filter_life` / `hepa_filter_pressure` — HEPA stage
  equivalents, only meaningful if a HEPA stage is fitted.
- `sensor.filter_disable_status` — factory setting for which filter(s) are
  actively monitored (`FACTORY_SET: FilterDisableStatus`), useful context
  for interpreting the life/pressure readings above.
- New `button` platform.

## [0.1.0] - 2026-09-07

### Added

- Initial release: config-flow-based Modbus TCP integration for the 2VV
  Venus 300 (AirGenio), migrated from a hand-written `modbus.yaml`.
- `switch`: Power, Freecooling mode (request), Freecooling enabled (master
  gate).
- `number`: fan power setpoint, temperature setpoint, bypass temperature
  threshold, freecooling airflow/temperature threshold, and the 8
  freecooling season/allowed-hours fields.
- `sensor`: 4 temperatures, inlet/outlet fan power, inlet/outlet filter
  life, bypass position, 3 read-only enums (bypass type, temperature
  sensor selection, ventilation mode), and 4 raw diagnostic status/error
  words.
- `binary_sensor`: 40 individually decoded bits of the status/error words
  (modes, faults, warnings), sourced from `MODBUS_V1_FW166_167.xlsx`.
- CI: `hassfest` + `hacs/action` validation, plus a `pytest` suite covering
  the register map, bitfield decoding, and translation-key coverage.
