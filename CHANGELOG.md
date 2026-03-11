# Changelog

All notable changes to this project will be documented in this file.

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
