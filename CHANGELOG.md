# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
