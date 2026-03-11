"""Constants for the Podlewanie integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

DOMAIN = "podlewanie"
STORAGE_KEY = "podlewanie"
STORAGE_VERSION = 1

# Config keys
CONF_LATITUDE = "latitude"
CONF_ZONES = "zones"
CONF_SEQUENCER = "sequencer"
CONF_SCHEDULES = "schedules"
CONF_WEATHER = "weather"
CONF_TANK = "tank"
CONF_ANTIFREEZE = "antifreeze"
CONF_ET = "et"

# Zone config keys
CONF_ZONE_KEY = "key"
CONF_ZONE_NAME = "name"
CONF_VALVE = "valve"
CONF_AREA_M2 = "area_m2"
CONF_DURATION = "duration"
CONF_MAX_DURATION = "max_duration"
CONF_SOIL_MOISTURE = "soil_moisture"
CONF_SOIL_TEMPERATURE = "soil_temperature"
CONF_SOIL_BATTERY = "soil_battery"
CONF_FLOW_METER = "flow_meter"

# Sequencer config keys
CONF_INTER_ZONE_DELAY = "inter_zone_delay"

# Schedule config keys
CONF_SCHEDULE_KEY = "key"
CONF_TIME = "time"
CONF_MONTHS = "months"
CONF_WEEKDAYS = "weekdays"
CONF_RETRY_NEXT_DAY = "retry_next_day"

# Weather config keys
CONF_RAIN_SENSORS = "rain_sensors"
CONF_RAIN_BINARY = "rain_binary"
CONF_FORECAST_ENTITY = "forecast_entity"
CONF_FORECAST_HOURS = "forecast_hours"
CONF_RAIN_THRESHOLD = "rain_threshold"
CONF_FORECAST_RAIN_THRESHOLD = "forecast_rain_threshold"

# Tank config keys
CONF_LEVEL_SENSOR = "level_sensor"
CONF_PUMP_SWITCH = "pump_switch"
CONF_PUMP_ON_ABOVE = "pump_on_above"
CONF_PUMP_OFF_BELOW = "pump_off_below"

# Antifreeze config keys
CONF_FLUSH_DURATION = "flush_duration"
CONF_TIERS = "tiers"
CONF_TEMP_MAX = "temp_max"
CONF_INTERVAL = "interval"
CONF_HIBERNATION_BELOW = "hibernation_below"
CONF_RECOVERY_ABOVE = "recovery_above"

# ET config keys
CONF_ET_ENABLED = "enabled"
CONF_BUCKET_MAX = "bucket_max"
CONF_MOISTURE_THRESHOLD = "moisture_threshold"

# Defaults
DEFAULT_DURATION = 15
DEFAULT_MAX_DURATION = 60
DEFAULT_INTER_ZONE_DELAY = 30
DEFAULT_RAIN_THRESHOLD = 2.0
DEFAULT_FORECAST_RAIN_THRESHOLD = 5.0
DEFAULT_FORECAST_HOURS = 48
DEFAULT_PUMP_ON_ABOVE = 30
DEFAULT_PUMP_OFF_BELOW = 15
DEFAULT_FLUSH_DURATION = 30
DEFAULT_HIBERNATION_BELOW = -5.0
DEFAULT_RECOVERY_ABOVE = 5.0
DEFAULT_BUCKET_MAX = 25.0
DEFAULT_MOISTURE_THRESHOLD = 40
DEFAULT_CROP_KC = 0.85
DEFAULT_SEASON_MULTIPLIER = 100
DEFAULT_ZONE_ADJUSTMENT = 100

# Update interval
UPDATE_INTERVAL_SECONDS = 60

# Valve verification delay
VALVE_VERIFY_DELAY = 5

# Weekday mapping
WEEKDAY_MAP = {
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
    "sat": 5,
    "sun": 6,
}


class ControllerStatus(StrEnum):
    """Controller status."""

    IDLE = "idle"
    RUNNING = "running"
    ANTIFREEZE = "antifreeze"
    DEGRADED = "degraded"
    HIBERNATION = "hibernation"


class SequencerState(StrEnum):
    """Sequencer state machine."""

    IDLE = "idle"
    PRIMING_PUMP = "priming_pump"
    WATERING = "watering"
    INTER_ZONE_DELAY = "inter_zone_delay"
    STOPPING = "stopping"


# --- v2: Default options for new config entries ---

DEFAULT_OPTIONS: dict[str, Any] = {
    "zones": [],
    "schedules": [],
    "weather": {
        "rain_sensors": [],
        "rain_binary": None,
        "forecast_entity": None,
        "forecast_hours": DEFAULT_FORECAST_HOURS,
        "rain_threshold": DEFAULT_RAIN_THRESHOLD,
        "forecast_rain_threshold": DEFAULT_FORECAST_RAIN_THRESHOLD,
    },
    "tank": None,
    "antifreeze": None,
    "et": {
        "enabled": True,
        "bucket_max": DEFAULT_BUCKET_MAX,
        "moisture_threshold": DEFAULT_MOISTURE_THRESHOLD,
    },
    "sequencer": {
        "inter_zone_delay": DEFAULT_INTER_ZONE_DELAY,
    },
}

# Month names for UI selectors
MONTH_NAMES: dict[int, str] = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}

# Weekday names for UI selectors
WEEKDAY_NAMES: dict[str, str] = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


# --- v2: Device info helpers ---


def controller_device_info(entry_id: str) -> DeviceInfo:
    """Device info for the main irrigation controller."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry_id)},
        name="Podlewanie",
        manufacturer="JI Engineering",
        model="Irrigation Controller",
        entry_type=DeviceEntryType.SERVICE,
    )


def zone_device_info(
    entry_id: str, zone_key: str, zone_name: str
) -> DeviceInfo:
    """Device info for an irrigation zone (child of controller)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry_id}_{zone_key}")},
        name=f"Podlewanie {zone_name}",
        manufacturer="JI Engineering",
        model="Irrigation Zone",
        via_device=(DOMAIN, entry_id),
    )
