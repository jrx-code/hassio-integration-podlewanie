"""Constants for the Podlewanie integration."""

from __future__ import annotations

from enum import StrEnum

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
