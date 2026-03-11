"""YAML configuration schema for the Podlewanie integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_ANTIFREEZE,
    CONF_AREA_M2,
    CONF_BUCKET_MAX,
    CONF_DURATION,
    CONF_ET,
    CONF_ET_ENABLED,
    CONF_FLOW_METER,
    CONF_FLUSH_DURATION,
    CONF_FORECAST_ENTITY,
    CONF_FORECAST_HOURS,
    CONF_FORECAST_RAIN_THRESHOLD,
    CONF_HIBERNATION_BELOW,
    CONF_INTER_ZONE_DELAY,
    CONF_INTERVAL,
    CONF_LATITUDE,
    CONF_LEVEL_SENSOR,
    CONF_MAX_DURATION,
    CONF_MOISTURE_THRESHOLD,
    CONF_MONTHS,
    CONF_PUMP_OFF_BELOW,
    CONF_PUMP_ON_ABOVE,
    CONF_PUMP_SWITCH,
    CONF_RAIN_BINARY,
    CONF_RAIN_SENSORS,
    CONF_RAIN_THRESHOLD,
    CONF_RECOVERY_ABOVE,
    CONF_RETRY_NEXT_DAY,
    CONF_SCHEDULE_KEY,
    CONF_SCHEDULES,
    CONF_SEQUENCER,
    CONF_SOIL_BATTERY,
    CONF_SOIL_MOISTURE,
    CONF_SOIL_TEMPERATURE,
    CONF_TANK,
    CONF_TEMP_MAX,
    CONF_TIERS,
    CONF_TIME,
    CONF_VALVE,
    CONF_WEATHER,
    CONF_WEEKDAYS,
    CONF_ZONE_KEY,
    CONF_ZONE_NAME,
    CONF_ZONES,
    DEFAULT_BUCKET_MAX,
    DEFAULT_DURATION,
    DEFAULT_FLUSH_DURATION,
    DEFAULT_FORECAST_HOURS,
    DEFAULT_FORECAST_RAIN_THRESHOLD,
    DEFAULT_HIBERNATION_BELOW,
    DEFAULT_INTER_ZONE_DELAY,
    DEFAULT_MAX_DURATION,
    DEFAULT_MOISTURE_THRESHOLD,
    DEFAULT_PUMP_OFF_BELOW,
    DEFAULT_PUMP_ON_ABOVE,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_RECOVERY_ABOVE,
)

ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_KEY): cv.string,
        vol.Required(CONF_ZONE_NAME): cv.string,
        vol.Required(CONF_VALVE): cv.entity_id,
        vol.Required(CONF_AREA_M2): vol.Coerce(float),
        vol.Optional(CONF_DURATION, default=DEFAULT_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=120)
        ),
        vol.Optional(CONF_MAX_DURATION, default=DEFAULT_MAX_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=180)
        ),
        vol.Optional(CONF_SOIL_MOISTURE): cv.entity_id,
        vol.Optional(CONF_SOIL_TEMPERATURE): cv.entity_id,
        vol.Optional(CONF_SOIL_BATTERY): cv.entity_id,
        vol.Optional(CONF_FLOW_METER): cv.entity_id,
    }
)

SCHEDULE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SCHEDULE_KEY): cv.string,
        vol.Required(CONF_TIME): cv.time,
        vol.Required(CONF_MONTHS): vol.All(
            cv.ensure_list, [vol.All(vol.Coerce(int), vol.Range(min=1, max=12))]
        ),
        vol.Required(CONF_WEEKDAYS): vol.All(
            cv.ensure_list,
            [vol.In(["mon", "tue", "wed", "thu", "fri", "sat", "sun"])],
        ),
        vol.Optional(CONF_RETRY_NEXT_DAY, default=False): cv.boolean,
    }
)

TIER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_TEMP_MAX): vol.Coerce(float),
        vol.Required(CONF_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=360)
        ),
    }
)

WEATHER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_RAIN_SENSORS, default=[]): vol.All(
            cv.ensure_list, [cv.entity_id]
        ),
        vol.Optional(CONF_RAIN_BINARY): cv.entity_id,
        vol.Optional(CONF_FORECAST_ENTITY): cv.entity_id,
        vol.Optional(
            CONF_FORECAST_HOURS, default=DEFAULT_FORECAST_HOURS
        ): vol.Coerce(int),
        vol.Optional(
            CONF_RAIN_THRESHOLD, default=DEFAULT_RAIN_THRESHOLD
        ): vol.Coerce(float),
        vol.Optional(
            CONF_FORECAST_RAIN_THRESHOLD, default=DEFAULT_FORECAST_RAIN_THRESHOLD
        ): vol.Coerce(float),
    }
)

TANK_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_LEVEL_SENSOR): cv.entity_id,
        vol.Optional(CONF_PUMP_SWITCH): cv.entity_id,
        vol.Optional(
            CONF_PUMP_ON_ABOVE, default=DEFAULT_PUMP_ON_ABOVE
        ): vol.Coerce(float),
        vol.Optional(
            CONF_PUMP_OFF_BELOW, default=DEFAULT_PUMP_OFF_BELOW
        ): vol.Coerce(float),
    }
)

ANTIFREEZE_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_FLUSH_DURATION, default=DEFAULT_FLUSH_DURATION
        ): vol.All(vol.Coerce(int), vol.Range(min=5, max=120)),
        vol.Required(CONF_TIERS): vol.All(cv.ensure_list, [TIER_SCHEMA]),
        vol.Optional(
            CONF_HIBERNATION_BELOW, default=DEFAULT_HIBERNATION_BELOW
        ): vol.Coerce(float),
        vol.Optional(
            CONF_RECOVERY_ABOVE, default=DEFAULT_RECOVERY_ABOVE
        ): vol.Coerce(float),
    }
)

ET_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ET_ENABLED, default=True): cv.boolean,
        vol.Optional(
            CONF_BUCKET_MAX, default=DEFAULT_BUCKET_MAX
        ): vol.Coerce(float),
        vol.Optional(
            CONF_MOISTURE_THRESHOLD, default=DEFAULT_MOISTURE_THRESHOLD
        ): vol.Coerce(float),
    }
)

SEQUENCER_SCHEMA = vol.Schema(
    {
        vol.Optional(
            CONF_INTER_ZONE_DELAY, default=DEFAULT_INTER_ZONE_DELAY
        ): vol.All(vol.Coerce(int), vol.Range(min=0, max=300)),
    }
)

CONFIG_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_LATITUDE): vol.Coerce(float),
        vol.Required(CONF_ZONES): vol.All(cv.ensure_list, [ZONE_SCHEMA]),
        vol.Optional(CONF_SEQUENCER, default={}): SEQUENCER_SCHEMA,
        vol.Optional(CONF_SCHEDULES, default=[]): vol.All(
            cv.ensure_list, [SCHEDULE_SCHEMA]
        ),
        vol.Optional(CONF_WEATHER, default={}): WEATHER_SCHEMA,
        vol.Optional(CONF_TANK): TANK_SCHEMA,
        vol.Optional(CONF_ANTIFREEZE): ANTIFREEZE_SCHEMA,
        vol.Optional(CONF_ET, default={}): ET_SCHEMA,
    }
)
