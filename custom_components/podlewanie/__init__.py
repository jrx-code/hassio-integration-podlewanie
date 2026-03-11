"""The Podlewanie integration (v2 — UI-only config)."""

from __future__ import annotations

import copy
import logging
from datetime import time as dt_time
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_OPTIONS, DOMAIN
from .coordinator import PodlewanieCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

type PodlewanieConfigEntry = ConfigEntry[PodlewanieCoordinator]

# Minimal YAML schema — only for v1→v2 migration
CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): dict},
    extra=vol.ALLOW_EXTRA,
)


def _yaml_to_options(yaml_config: dict[str, Any]) -> dict[str, Any]:
    """Convert v1 YAML config dict to v2 options dict."""
    options = copy.deepcopy(DEFAULT_OPTIONS)

    # Zones
    zones = []
    for zc in yaml_config.get("zones", []):
        zone: dict[str, Any] = {
            "key": zc["key"],
            "name": zc["name"],
            "valve": zc["valve"],
            "area_m2": zc["area_m2"],
            "duration": zc.get("duration", 15),
            "max_duration": zc.get("max_duration", 60),
            "soil_moisture": zc.get("soil_moisture"),
            "soil_temperature": zc.get("soil_temperature"),
            "soil_battery": zc.get("soil_battery"),
            "flow_meter": zc.get("flow_meter"),
        }
        zones.append(zone)
    options["zones"] = zones

    # Schedules — convert time objects to strings
    schedules = []
    for sc in yaml_config.get("schedules", []):
        time_val = sc["time"]
        if isinstance(time_val, dt_time):
            time_str = time_val.strftime("%H:%M:%S")
        else:
            time_str = str(time_val)
        schedule: dict[str, Any] = {
            "key": sc["key"],
            "time": time_str,
            "months": list(sc["months"]),
            "weekdays": list(sc["weekdays"]),
            "retry_next_day": sc.get("retry_next_day", False),
        }
        schedules.append(schedule)
    options["schedules"] = schedules

    # Weather
    weather = yaml_config.get("weather", {})
    if weather:
        options["weather"] = {
            "rain_sensors": weather.get("rain_sensors", []),
            "rain_binary": weather.get("rain_binary"),
            "forecast_entity": weather.get("forecast_entity"),
            "forecast_hours": weather.get("forecast_hours", 48),
            "rain_threshold": weather.get("rain_threshold", 2.0),
            "forecast_rain_threshold": weather.get("forecast_rain_threshold", 5.0),
        }

    # Tank
    tank = yaml_config.get("tank")
    if tank:
        options["tank"] = {
            "level_sensor": tank["level_sensor"],
            "pump_switch": tank.get("pump_switch"),
            "pump_on_above": tank.get("pump_on_above", 30),
            "pump_off_below": tank.get("pump_off_below", 15),
        }

    # Antifreeze
    af = yaml_config.get("antifreeze")
    if af:
        options["antifreeze"] = {
            "flush_duration": af.get("flush_duration", 30),
            "tiers": af.get("tiers", []),
            "hibernation_below": af.get("hibernation_below", -5.0),
            "recovery_above": af.get("recovery_above", 5.0),
        }

    # ET
    et = yaml_config.get("et", {})
    options["et"] = {
        "enabled": et.get("enabled", True),
        "bucket_max": et.get("bucket_max", 25.0),
        "moisture_threshold": et.get("moisture_threshold", 40),
    }

    # Sequencer
    seq = yaml_config.get("sequencer", {})
    options["sequencer"] = {
        "inter_zone_delay": seq.get("inter_zone_delay", 30),
    }

    return options


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Podlewanie integration."""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        # Store YAML config for v1→v2 migration only
        hass.data[DOMAIN]["yaml_config"] = config[DOMAIN]
        _LOGGER.warning(
            "Podlewanie YAML configuration is deprecated. "
            "Configuration has been migrated to UI. "
            "Remove 'podlewanie:' section from configuration.yaml"
        )

        # Auto-import: create config entry if YAML is present but no entry exists
        if not hass.config_entries.async_entries(DOMAIN):
            hass.async_create_task(
                hass.config_entries.flow.async_init(
                    DOMAIN, context={"source": "import"}
                )
            )

    return True


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> bool:
    """Migrate config entry from v1 to v2."""
    if config_entry.version == 1:
        _LOGGER.info("Migrating podlewanie config entry from v1 to v2")

        yaml_config = hass.data.get(DOMAIN, {}).get("yaml_config")
        if yaml_config:
            options = _yaml_to_options(yaml_config)
        else:
            options = copy.deepcopy(DEFAULT_OPTIONS)

        hass.config_entries.async_update_entry(
            config_entry, version=2, options=options
        )
        _LOGGER.info("Migration to v2 complete")
        return True

    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: PodlewanieConfigEntry
) -> bool:
    """Set up Podlewanie from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = PodlewanieCoordinator(hass, entry)
    await coordinator.async_setup()
    await coordinator.async_refresh()

    entry.runtime_data = coordinator

    # Register controller device BEFORE platforms (so zone via_device works)
    dev_reg = dr.async_get(hass)
    dev_reg.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="Podlewanie",
        manufacturer="JI Engineering",
        model="Irrigation Controller",
        entry_type=dr.DeviceEntryType.SERVICE,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    from .services import async_register_services  # noqa: PLC0415

    await async_register_services(hass)

    # Reload on options change
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Handle options update — reload the entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: PodlewanieConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator: PodlewanieCoordinator = entry.runtime_data
        await coordinator.async_unload()

    return unload_ok
