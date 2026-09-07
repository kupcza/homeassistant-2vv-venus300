# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

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
