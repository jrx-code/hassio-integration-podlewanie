# Podlewanie — Custom Home Assistant Integration

Autorska integracja HA do zarządzania nawadnianiem ogrodu. YAML-only config, bez UI config flow.

Zastępuje: Irrigation Unlimited + Smart Irrigation + 9 plików automatyk + 4 packages.

## Features

- **4-zone sequential irrigation** with configurable schedules (morning/evening/winter)
- **Hargreaves ET₀** evapotranspiration calculation (daily at 03:00)
- **Per-zone moisture bucket tracking** with soil sensor correction
- **Anti-freeze flush** with temperature tiers and hibernation mode
- **Rainwater tank pump controller** with hysteresis
- **Weather-based skip logic** (rain sensors + forecast)
- **Persistent state** survives HA restarts (bucket levels, enabled states, adjustments)

## Entities (47)

| Platform | Count | Examples |
|---|---|---|
| `binary_sensor` | 5 | `podlewanie_{zone}_active`, `podlewanie_running` |
| `sensor` | 22 | `{zone}_remaining`, `{zone}_next_run`, `{zone}_volume_today`, `{zone}_bucket`, `{zone}_soil`, `et_daily`, `status` |
| `switch` | 5 | `podlewanie_{zone}_enabled`, `podlewanie_enabled` |
| `number` | 15 | `{zone}_duration`, `{zone}_adjustment`, `{zone}_crop_kc`, `moisture_threshold`, `rain_threshold`, `season_multiplier` |

## Services (7)

| Service | Description |
|---|---|
| `podlewanie.manual_run` | Run single zone (zone, duration?) |
| `podlewanie.run_sequence` | Full sequential cycle for all enabled zones |
| `podlewanie.cancel` | Stop all irrigation immediately |
| `podlewanie.adjust_time` | Set zone duration multiplier (zone, percentage) |
| `podlewanie.enable` | Enable zone for scheduling |
| `podlewanie.disable` | Disable zone from scheduling |
| `podlewanie.reload` | Reload configuration |

## Installation

Copy `custom_components/podlewanie/` to your HA `config/custom_components/` directory.

Add to `configuration.yaml`:

```yaml
podlewanie:
  latitude: 53.4289

  zones:
    - key: brzeg_domu
      name: "Brzeg Domu"
      valve: switch.linktap_obwod_brzeg_domu
      area_m2: 40
      duration: 15
      max_duration: 60
      soil_moisture: sensor.ts0601_1_obwod_brzeg_domu_wilgotnosc_gleby
      soil_temperature: sensor.ts0601_1_obwod_brzeg_domu_temperatura
      flow_meter: sensor.linktap_obwod_brzeg_domu_volume

  sequencer:
    inter_zone_delay: 30

  schedules:
    - key: morning
      time: "05:30"
      months: [4,5,6,7,8,9,10]
      weekdays: [mon,wed,fri,sun]

  weather:
    rain_sensors:
      - sensor.openweathermap_rain
    rain_binary: binary_sensor.czujnik_deszczu_multisensor_rain_0
    forecast_entity: weather.openweathermap

  tank:
    level_sensor: sensor.deszczowka_zapelnienie
    pump_switch: switch.sterownik_pompy_wody_deszczowej

  antifreeze:
    flush_duration: 30
    tiers:
      - temp_max: -2
        interval: 30
      - temp_max: 0
        interval: 60
      - temp_max: 3
        interval: 180

  et:
    enabled: true
    bucket_max: 25.0
    moisture_threshold: 40
```

## Architecture

```
irrigation.py    — Zone, ETCalculator, BucketTracker, Sequencer (FSM), AntifreezeManager, PumpController
coordinator.py   — DataUpdateCoordinator, scheduler, persistence, weather/rain skip
__init__.py      — async_setup (YAML), platform discovery
binary_sensor.py — 5 entities
sensor.py        — 22 entities
switch.py        — 5 entities
number.py        — 15 entities
services.py      — 7 service handlers
```

### Sequencer State Machine

```
IDLE → PRIMING_PUMP → WATERING → INTER_ZONE_DELAY → (next zone) → STOPPING → IDLE
```

### ET₀ Hargreaves

```
ET₀ = 0.0023 × (T_mean + 17.8) × (T_max - T_min)^0.5 × Ra
```

## Hardware

- 4× LinkTap water valves (G2S)
- 4× Tuya soil moisture/temperature sensors (TS0601)
- 1× rain gauge + binary rain sensor
- 1× rainwater tank level sensor + pump switch

## License

Private — JI ENGINEERING
