"""DataUpdateCoordinator for the Podlewanie integration (v2)."""

from __future__ import annotations

import logging
from datetime import datetime, time as dt_time, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ANTIFREEZE,
    CONF_BUCKET_MAX,
    CONF_ET,
    CONF_ET_ENABLED,
    CONF_FLUSH_DURATION,
    CONF_FORECAST_ENTITY,
    CONF_FORECAST_HOURS,
    CONF_FORECAST_RAIN_THRESHOLD,
    CONF_HIBERNATION_BELOW,
    CONF_INTER_ZONE_DELAY,
    CONF_LEVEL_SENSOR,
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
    CONF_TANK,
    CONF_TEMP_MAX,
    CONF_TIERS,
    CONF_TIME,
    CONF_WEATHER,
    CONF_WEEKDAYS,
    CONF_ZONES,
    ControllerStatus,
    DEFAULT_BUCKET_MAX,
    DEFAULT_FLUSH_DURATION,
    DEFAULT_HIBERNATION_BELOW,
    DEFAULT_MOISTURE_THRESHOLD,
    DEFAULT_RECOVERY_ABOVE,
    DEFAULT_SEASON_MULTIPLIER,
    DEFAULT_ZONE_ADJUSTMENT,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VERSION,
    UPDATE_INTERVAL_SECONDS,
    WEEKDAY_MAP,
)
from .irrigation import (
    AntifreezeManager,
    BucketTracker,
    ETCalculator,
    PumpController,
    Sequencer,
    Zone,
)

_LOGGER = logging.getLogger(__name__)


def _parse_time_string(time_str: str) -> dt_time:
    """Parse 'HH:MM:SS' or 'HH:MM' string to datetime.time."""
    parts = time_str.split(":")
    return dt_time(
        int(parts[0]),
        int(parts[1]),
        int(parts[2]) if len(parts) > 2 else 0,
    )


class PodlewanieCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage irrigation state and scheduling."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator from config entry options."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL_SECONDS),
        )
        self._entry = entry
        self._store = Store[dict[str, Any]](hass, STORAGE_VERSION, STORAGE_KEY)
        self._unsub_listeners: list[CALLBACK_TYPE] = []

        opts = entry.options

        # Build zones from options
        self.zones: list[Zone] = [
            Zone.from_config(zc) for zc in opts.get(CONF_ZONES, [])
        ]
        self._zone_map: dict[str, Zone] = {z.key: z for z in self.zones}

        # Latitude for ET calculation
        self._latitude = hass.config.latitude

        # ET Calculator
        et_cfg = opts.get(CONF_ET, {})
        self._et_enabled = et_cfg.get(CONF_ET_ENABLED, True)
        self._et_calc = ETCalculator(self._latitude) if self._et_enabled else None

        # Bucket Tracker
        bucket_max = et_cfg.get(CONF_BUCKET_MAX, DEFAULT_BUCKET_MAX)
        self._moisture_threshold = et_cfg.get(
            CONF_MOISTURE_THRESHOLD, DEFAULT_MOISTURE_THRESHOLD
        )
        self._bucket_tracker = BucketTracker(bucket_max, self._moisture_threshold)

        # Pump controller
        tank_cfg = opts.get(CONF_TANK)
        self._pump: PumpController | None = None
        if tank_cfg is not None:
            self._pump = PumpController(
                hass,
                tank_cfg[CONF_LEVEL_SENSOR],
                tank_cfg.get(CONF_PUMP_SWITCH),
                tank_cfg.get(CONF_PUMP_ON_ABOVE, 30),
                tank_cfg.get(CONF_PUMP_OFF_BELOW, 15),
            )

        # Sequencer
        seq_cfg = opts.get(CONF_SEQUENCER, {})
        inter_delay = seq_cfg.get(CONF_INTER_ZONE_DELAY, 30)
        self.sequencer = Sequencer(hass, self.zones, inter_delay, self._pump)
        self.sequencer.set_coordinator(self)

        # Antifreeze
        af_cfg = opts.get(CONF_ANTIFREEZE)
        self._antifreeze: AntifreezeManager | None = None
        if af_cfg is not None:
            self._antifreeze = AntifreezeManager(
                tiers=af_cfg.get(CONF_TIERS, []),
                flush_duration=af_cfg.get(
                    CONF_FLUSH_DURATION, DEFAULT_FLUSH_DURATION
                ),
                hibernation_below=af_cfg.get(
                    CONF_HIBERNATION_BELOW, DEFAULT_HIBERNATION_BELOW
                ),
                recovery_above=af_cfg.get(
                    CONF_RECOVERY_ABOVE, DEFAULT_RECOVERY_ABOVE
                ),
            )

        # Weather config
        self._weather_cfg = opts.get(CONF_WEATHER, {})

        # Schedules — parse time strings to dt_time
        self._schedules: list[dict[str, Any]] = []
        for s in opts.get(CONF_SCHEDULES, []):
            schedule = dict(s)
            time_val = s[CONF_TIME]
            if isinstance(time_val, str):
                schedule[CONF_TIME] = _parse_time_string(time_val)
            self._schedules.append(schedule)

        # Master switch
        self.master_enabled: bool = True

        # Season multiplier
        self.season_multiplier: float = DEFAULT_SEASON_MULTIPLIER

        # Rain threshold overrides
        self.rain_threshold: float = self._weather_cfg.get(
            CONF_RAIN_THRESHOLD, 2.0
        )
        self.moisture_threshold_override: float = self._moisture_threshold

        # ET daily cache
        self.et_daily: float = 0.0

        # Status
        self.status: ControllerStatus = ControllerStatus.IDLE

    @property
    def entry(self) -> ConfigEntry:
        """Return the config entry."""
        return self._entry

    async def async_setup(self) -> None:
        """Set up scheduler listeners and restore state."""
        await self._restore_state()
        self._setup_schedule_listeners()
        self._setup_et_listener()

        # Cancel on HA stop
        self.hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, self._on_ha_stop
        )

    async def _on_ha_stop(self, event: Event) -> None:
        """Handle HA shutdown."""
        await self.sequencer.cancel()
        await self._save_state()

    def _setup_schedule_listeners(self) -> None:
        """Register time-based schedule triggers."""
        for schedule in self._schedules:
            sched_time: dt_time = schedule[CONF_TIME]
            unsub = async_track_time_change(
                self.hass,
                self._schedule_callback_factory(schedule),
                hour=sched_time.hour,
                minute=sched_time.minute,
                second=0,
            )
            self._unsub_listeners.append(unsub)

    def _schedule_callback_factory(
        self, schedule: dict
    ):
        """Create callback for a specific schedule."""

        @callback
        def _schedule_triggered(now: datetime) -> None:
            """Handle schedule trigger."""
            if not self.master_enabled:
                return

            # Check month
            if now.month not in schedule[CONF_MONTHS]:
                return

            # Check weekday
            weekday_names = schedule[CONF_WEEKDAYS]
            weekday_nums = [WEEKDAY_MAP[d] for d in weekday_names]
            if now.weekday() not in weekday_nums:
                # Check retry_next_day
                if schedule.get(CONF_RETRY_NEXT_DAY, False):
                    yesterday = now.weekday() - 1
                    if yesterday < 0:
                        yesterday = 6
                    if yesterday not in weekday_nums:
                        return
                    _LOGGER.info(
                        "Schedule %s: retry for yesterday",
                        schedule[CONF_SCHEDULE_KEY],
                    )
                else:
                    return

            # Check weather conditions
            if self._should_skip_rain():
                _LOGGER.info(
                    "Schedule %s: skipping due to rain",
                    schedule[CONF_SCHEDULE_KEY],
                )
                return

            _LOGGER.info(
                "Schedule %s triggered at %s",
                schedule[CONF_SCHEDULE_KEY],
                now.isoformat(),
            )
            self.hass.async_create_task(
                self.sequencer.run_sequence(
                    season_multiplier=self.season_multiplier
                )
            )

        return _schedule_triggered

    def _setup_et_listener(self) -> None:
        """Schedule daily ET calculation at 03:00."""
        if not self._et_enabled:
            return

        unsub = async_track_time_change(
            self.hass, self._et_daily_callback, hour=3, minute=0, second=0
        )
        self._unsub_listeners.append(unsub)

    @callback
    def _et_daily_callback(self, now: datetime) -> None:
        """Calculate daily ET and update buckets."""
        t_min, t_max = self._get_temp_range()
        if t_min is None or t_max is None:
            _LOGGER.warning("Cannot calculate ET: temperature data unavailable")
            return

        day_of_year = now.timetuple().tm_yday
        self.et_daily = self._et_calc.calculate(t_min, t_max, day_of_year)
        _LOGGER.info("Daily ET0: %.2f mm/day", self.et_daily)

        # Apply ET to all zone buckets
        for zone in self.zones:
            self._bucket_tracker.apply_et(zone, self.et_daily)

        # Apply rain from previous day
        rain = self._get_rain_today()
        if rain > 0:
            for zone in self.zones:
                self._bucket_tracker.apply_rain(zone, rain)
            _LOGGER.info("Applied %.1f mm rain to all buckets", rain)

        # Reset daily volume
        for zone in self.zones:
            zone.volume_today = 0.0

    async def _async_update_data(self) -> dict[str, Any]:
        """Periodic update — read sensors, check antifreeze, compute next runs."""
        # Update soil readings and correct buckets
        for zone in self.zones:
            moisture = self._get_entity_float(zone.soil_moisture_entity)
            if moisture is not None:
                self._bucket_tracker.correct_from_sensor(zone, moisture)

            # Update flow meter volumes
            volume = self._get_entity_float(zone.flow_meter_entity)
            if volume is not None:
                zone.volume_today = volume

        # Antifreeze check
        if self._antifreeze is not None and not self.sequencer.is_running:
            avg_temp = self._get_avg_soil_temp()
            if avg_temp is not None:
                self._antifreeze.check_hibernation(avg_temp)
                if self._antifreeze.should_flush(avg_temp):
                    _LOGGER.info(
                        "Antifreeze flush triggered at %.1f\u00b0C", avg_temp
                    )
                    self._antifreeze.last_flush_time = dt_util.utcnow()
                    await self.sequencer.run_antifreeze(
                        self.zones, self._antifreeze.flush_duration
                    )

        # Compute next run times
        self._compute_next_runs()

        # Update status
        self._update_status()

        # Periodically save state
        await self._save_state()

        return {
            "status": self.status,
            "et_daily": self.et_daily,
            "zones": {z.key: z for z in self.zones},
        }

    def _update_status(self) -> None:
        """Update controller status."""
        if self._antifreeze and self._antifreeze.is_hibernating:
            self.status = ControllerStatus.HIBERNATION
        elif self.sequencer.state.value == "watering" and self._antifreeze and self._get_avg_soil_temp() is not None and (self._get_avg_soil_temp() or 99) < 3:
            self.status = ControllerStatus.ANTIFREEZE
        elif self.sequencer.is_running:
            self.status = ControllerStatus.RUNNING
        elif not self.master_enabled:
            self.status = ControllerStatus.DEGRADED
        else:
            self.status = ControllerStatus.IDLE

    def _compute_next_runs(self) -> None:
        """Compute next scheduled run time for each zone."""
        now = dt_util.now()
        for zone in self.zones:
            if not zone.enabled or not self.master_enabled:
                zone.next_run = None
                continue

            next_time = self._find_next_schedule_time(now)
            zone.next_run = next_time

    def _find_next_schedule_time(self, now: datetime) -> datetime | None:
        """Find next matching schedule time from now."""
        candidates: list[datetime] = []

        for schedule in self._schedules:
            sched_time: dt_time = schedule[CONF_TIME]
            months = schedule[CONF_MONTHS]
            weekday_names = schedule[CONF_WEEKDAYS]
            weekday_nums = [WEEKDAY_MAP[d] for d in weekday_names]

            # Check next 30 days
            for day_offset in range(31):
                candidate = now + timedelta(days=day_offset)
                candidate = candidate.replace(
                    hour=sched_time.hour,
                    minute=sched_time.minute,
                    second=0,
                    microsecond=0,
                )
                if candidate <= now:
                    continue
                if candidate.month not in months:
                    continue
                if candidate.weekday() not in weekday_nums:
                    continue
                candidates.append(candidate)
                break

        return min(candidates) if candidates else None

    def _should_skip_rain(self) -> bool:
        """Check if irrigation should be skipped due to rain."""
        # Check binary rain sensor
        rain_binary = self._weather_cfg.get(CONF_RAIN_BINARY)
        if rain_binary:
            state = self.hass.states.get(rain_binary)
            if state and state.state == "on":
                return True

        # Check rain sensors
        rain_sensors = self._weather_cfg.get(CONF_RAIN_SENSORS, [])
        for sensor_id in rain_sensors:
            value = self._get_entity_float(sensor_id)
            if value is not None and value >= self.rain_threshold:
                return True

        # Check forecast
        forecast_entity = self._weather_cfg.get(CONF_FORECAST_ENTITY)
        if forecast_entity:
            forecast_rain = self._get_forecast_rain(forecast_entity)
            threshold = self._weather_cfg.get(CONF_FORECAST_RAIN_THRESHOLD, 5.0)
            if forecast_rain >= threshold:
                return True

        return False

    def _get_forecast_rain(self, entity_id: str) -> float:
        """Get total forecasted rain from weather entity."""
        state = self.hass.states.get(entity_id)
        if state is None:
            return 0.0

        forecast = state.attributes.get("forecast", [])
        if not forecast:
            return 0.0

        hours = self._weather_cfg.get(CONF_FORECAST_HOURS, 48)
        now = dt_util.utcnow()
        cutoff = now + timedelta(hours=hours)
        total_rain = 0.0

        for entry in forecast:
            fc_time = entry.get("datetime")
            if fc_time and isinstance(fc_time, str):
                try:
                    fc_dt = datetime.fromisoformat(fc_time)
                    if fc_dt > cutoff:
                        break
                except ValueError:
                    continue
            precipitation = entry.get("precipitation", 0) or 0
            total_rain += float(precipitation)

        return total_rain

    def _get_rain_today(self) -> float:
        """Get today's rain total from rain sensors."""
        max_rain = 0.0
        rain_sensors = self._weather_cfg.get(CONF_RAIN_SENSORS, [])
        for sensor_id in rain_sensors:
            value = self._get_entity_float(sensor_id)
            if value is not None:
                max_rain = max(max_rain, value)
        return max_rain

    def _get_temp_range(self) -> tuple[float | None, float | None]:
        """Get min/max temperature from weather forecast entity."""
        forecast_entity = self._weather_cfg.get(CONF_FORECAST_ENTITY)
        if not forecast_entity:
            return None, None

        state = self.hass.states.get(forecast_entity)
        if state is None:
            return None, None

        # Try current temperature as a fallback
        temp = state.attributes.get("temperature")
        forecast = state.attributes.get("forecast", [])

        if not forecast:
            if temp is not None:
                return float(temp) - 5, float(temp) + 5
            return None, None

        temps = []
        for entry in forecast[:24]:  # Last/next 24 hours
            t = entry.get("temperature")
            t_low = entry.get("templow")
            if t is not None:
                temps.append(float(t))
            if t_low is not None:
                temps.append(float(t_low))

        if not temps:
            return None, None

        return min(temps), max(temps)

    def _get_avg_soil_temp(self) -> float | None:
        """Get average soil temperature across all zones."""
        temps = []
        for zone in self.zones:
            value = self._get_entity_float(zone.soil_temperature_entity)
            if value is not None:
                temps.append(value)
        return sum(temps) / len(temps) if temps else None

    def _get_entity_float(self, entity_id: str | None) -> float | None:
        """Get float value from entity state."""
        if entity_id is None:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def get_zone(self, key: str) -> Zone | None:
        """Get zone by key."""
        return self._zone_map.get(key)

    async def _save_state(self) -> None:
        """Persist state to storage."""
        data: dict[str, Any] = {
            "master_enabled": self.master_enabled,
            "season_multiplier": self.season_multiplier,
            "rain_threshold": self.rain_threshold,
            "moisture_threshold": self.moisture_threshold_override,
            "zones": {},
        }
        for zone in self.zones:
            data["zones"][zone.key] = {
                "enabled": zone.enabled,
                "bucket": zone.bucket,
                "adjustment": zone.adjustment,
                "crop_kc": zone.crop_kc,
                "duration_override": zone.duration_override,
            }
        if self._antifreeze:
            data["last_antifreeze_time"] = (
                self._antifreeze.last_flush_time.isoformat()
                if self._antifreeze.last_flush_time
                else None
            )
        await self._store.async_save(data)

    async def _restore_state(self) -> None:
        """Restore state from storage."""
        data = await self._store.async_load()
        if data is None:
            return

        self.master_enabled = data.get("master_enabled", True)
        self.season_multiplier = data.get(
            "season_multiplier", DEFAULT_SEASON_MULTIPLIER
        )
        self.rain_threshold = data.get("rain_threshold", self.rain_threshold)
        self.moisture_threshold_override = data.get(
            "moisture_threshold", self._moisture_threshold
        )

        zones_data = data.get("zones", {})
        for zone in self.zones:
            zd = zones_data.get(zone.key, {})
            zone.enabled = zd.get("enabled", True)
            zone.bucket = zd.get("bucket", 0.0)
            zone.adjustment = zd.get("adjustment", DEFAULT_ZONE_ADJUSTMENT)
            zone.crop_kc = zd.get("crop_kc", zone.crop_kc)
            zone.duration_override = zd.get("duration_override")

        if self._antifreeze:
            af_time = data.get("last_antifreeze_time")
            if af_time:
                self._antifreeze.last_flush_time = datetime.fromisoformat(
                    af_time
                )

    async def async_unload(self) -> None:
        """Unload coordinator."""
        await self.sequencer.cancel()
        await self._save_state()
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
