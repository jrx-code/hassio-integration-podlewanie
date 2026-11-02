# Podlewanie

A garden irrigation controller for Home Assistant, configured entirely from the UI.
It replaces the usual stack of Irrigation Unlimited, Smart Irrigation and a pile of
automations with one integration: schedules, a sequential zone runner, an
evapotranspiration (ET₀) water budget per zone, rain skipping, anti-freeze flushing
and an optional rainwater tank pump.

It drives valves you already have (any `switch.*` or `valve.*` entity), so it works
with LinkTap, Rainbird, Zigbee valves, relays and so on.

## Features

- Zones, each with its own valve, area, default and maximum run time
- Schedules (time, months, weekdays) that start a sequential run of all enabled zones
- Hargreaves ET₀ calculated daily at 03:00 from your Home Assistant latitude and the
  daily temperature range
- Per-zone moisture bucket that tracks water lost and applied, with optional
  soil moisture correction
- Skips a run after rain (rain sensors, a rain binary sensor, forecast entity)
- Anti-freeze flush with temperature tiers
- Optional rainwater tank pump controller with level hysteresis
- State survives restarts (bucket levels, enabled flags, adjustments)
- One Home Assistant device per zone, grouped under the controller

## Installation

### HACS

1. HACS → Integrations → three dots → Custom repositories.
2. Add `https://github.com/jrx-code/hassio-integration-podlewanie`, category Integration.
3. Install **Podlewanie** and restart Home Assistant.

### Manual

Copy `custom_components/podlewanie` into your `config/custom_components/` directory and
restart Home Assistant.

## Setup

1. Settings → Devices & services → Add integration → **Podlewanie** (one instance).
2. Open **Configure** on the integration. The menu has:

| Menu | What it sets |
|---|---|
| Add / Edit / Remove zone | Valve entity, area, default and maximum duration, optional soil moisture, soil temperature, sensor battery and flow meter |
| Schedules | Start time, months and weekdays, add / edit / remove |
| Weather | Rain sensors, rain binary sensor, forecast entity, thresholds |
| Rainwater tank | Level sensor and pump switch, on/off |
| Anti-freeze | Temperature tiers, flush duration, hibernation |
| Evapotranspiration (ET) | ET switch, bucket size, moisture threshold |
| Sequencer | Delay between zones |

An older YAML configuration (v1) is imported into a config entry automatically.

## Entities

Per zone: an *enabled* switch, *duration* / *adjustment* / crop coefficient numbers,
and sensors for remaining time, next run, volume today, bucket level and soil
moisture. Controller-wide: *enabled* switch, a *running* binary sensor, daily ET₀,
overall status and the threshold numbers (moisture, rain, season multiplier).

## Services

| Service | Description |
|---|---|
| `podlewanie.manual_run` | Run one zone, optional duration |
| `podlewanie.run_sequence` | Run all enabled zones one after another |
| `podlewanie.cancel` | Stop all irrigation immediately |
| `podlewanie.adjust_time` | Set a zone's duration multiplier in percent |
| `podlewanie.enable` | Enable a zone for scheduling |
| `podlewanie.disable` | Disable a zone |

## How it works

Sequencer state machine:

```
IDLE → PRIMING_PUMP → WATERING → INTER_ZONE_DELAY → (next zone) → STOPPING → IDLE
```

Hargreaves reference evapotranspiration:

```
ET₀ = 0.0023 × (T_mean + 17.8) × √(T_max − T_min) × Ra
```

`Ra` is computed from the latitude of your Home Assistant installation and the day of
the year. The daily minimum and maximum temperature come from the forecast of the
weather entity you pick in the Weather menu; without it ET₀ is not calculated.

## Status

Version 2.0.0. Written for and used on one garden with four zones; other setups may
hit gaps. Issues and pull requests are welcome.

## License

MIT, see [LICENSE](LICENSE).
