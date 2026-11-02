# Changelog

All notable changes to this project will be documented in this file.

## [2.0.1] — 2026-11-02

### Changed
- Public release: English README for the UI configuration, MIT license, HACS metadata, hassfest and HACS validation workflow, issue tracker link in the manifest

## [2.0.0] — 2026-03-12

### Added
- **Full UI configuration** — no YAML needed, everything via Settings → Integrations → Configure
- Options flow with menu-driven interface:
  - Add/Edit/Remove zones dynamically
  - Add/Edit/Remove schedules
  - Weather settings (rain sensors, forecast, thresholds)
  - Rainwater tank (enable/disable + pump control)
  - Anti-freeze (enable/disable, tiers, hibernation)
  - Evapotranspiration (ET) settings
  - Sequencer settings (inter-zone delay)
- **Device-per-zone grouping** — each zone is a separate HA device (child of controller)
- Valve domain detection — supports both `switch.*` and `valve.*` entities
- Config entry migration (v1 → v2) — existing YAML config auto-imported

### Changed
- `config_flow.py` — complete rewrite with ConfigFlow v2 + OptionsFlow (~930 lines)
- `__init__.py` — removed YAML dependency, uses `entry.runtime_data` pattern
- `coordinator.py` — accepts ConfigEntry, parses time strings from options
- All entity platforms — device-per-zone + `entry.runtime_data`
- `services.py` — coordinator access via config entry runtime_data
- `schema.py` — removed (no longer needed)

### Removed
- YAML configuration support (deprecated, auto-migrated to UI)
- `schema.py` — voluptuous schema for YAML validation

## [1.1.0] — 2026-03-11

### Added
- UI config flow — integration can now be added from Settings → Integrations
- Auto-import from YAML — config entry created automatically when YAML config present
- DeviceInfo for all entities — grouped under "Podlewanie" device in UI
- `config_flow.py` with single-instance guard
- `strings.json` for config flow localization

### Changed
- Platforms use `async_setup_entry` instead of `async_setup_platform` (discovery)
- Coordinator stored in `hass.data[DOMAIN]["coordinator"]` (was `hass.data[DOMAIN]`)

## [1.0.1] — 2026-03-11

### Added
- Brand icon (sprinkler on green circle, `brand/icon.png` + `icon@2x.png`)

## [1.0.0] — 2026-03-11

### Added
- Initial release of custom Podlewanie integration
- 4-zone sequential irrigation with configurable schedules
- Hargreaves ET₀ evapotranspiration calculation (daily at 03:00)
- Per-zone moisture bucket tracking with soil sensor correction
- Anti-freeze flush with 3 temperature tiers and hibernation mode
- Rainwater tank pump controller with hysteresis (on/off thresholds)
- Weather-based skip logic (rain sensors, binary rain sensor, forecast)
- 47 entities: 5 binary_sensor, 22 sensor, 5 switch, 15 number
- 7 services: manual_run, run_sequence, cancel, adjust_time, enable, disable, reload
- Persistent state via hass.helpers.storage.Store (bucket levels, enabled states, adjustments)
- YAML-only configuration (no UI config flow)
- Sequencer state machine: IDLE → PRIMING_PUMP → WATERING → INTER_ZONE_DELAY → STOPPING → IDLE
- Valve open verification (5s delay + state check)
- Safety cutoff per zone (max_duration)
- Season multiplier and per-zone adjustment controls
- Crop coefficient (Kc) per zone for ET calculation

### Replaces
- `custom_components/irrigation_unlimited/`
- `custom_components/smart_irrigation/`
- 9 automation YAML files (`podlewanie_*.yaml`)
- 4 package YAML files (`podlewanie_*.yaml`)
