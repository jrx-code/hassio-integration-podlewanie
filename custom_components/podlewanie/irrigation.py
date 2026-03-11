"""Core irrigation logic: Zone, ETCalc, Bucket, Sequencer, Antifreeze, Pump."""

from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AREA_M2,
    CONF_DURATION,
    CONF_FLOW_METER,
    CONF_MAX_DURATION,
    CONF_SOIL_BATTERY,
    CONF_SOIL_MOISTURE,
    CONF_SOIL_TEMPERATURE,
    CONF_VALVE,
    CONF_ZONE_KEY,
    CONF_ZONE_NAME,
    ControllerStatus,
    DEFAULT_CROP_KC,
    DEFAULT_SEASON_MULTIPLIER,
    DEFAULT_ZONE_ADJUSTMENT,
    SequencerState,
    VALVE_VERIFY_DELAY,
)

if TYPE_CHECKING:
    from .coordinator import PodlewanieCoordinator

_LOGGER = logging.getLogger(__name__)


# --- Extraterrestrial radiation table (MJ/m2/day) by latitude and month ---
# Simplified Hargreaves Ra lookup. Index = month (1-12).
# Values for ~53°N latitude (Szczecin).
_RA_TABLE_53N: dict[int, float] = {
    1: 9.4,
    2: 15.0,
    3: 23.5,
    4: 33.0,
    5: 39.5,
    6: 42.0,
    7: 40.5,
    8: 34.5,
    9: 25.5,
    10: 16.5,
    11: 10.0,
    12: 7.5,
}


def _get_ra(latitude: float, day_of_year: int) -> float:
    """Calculate extraterrestrial radiation Ra (MJ/m2/day) using solar geometry."""
    lat_rad = math.radians(latitude)
    # Solar declination
    decl = 0.409 * math.sin(2 * math.pi / 365 * day_of_year - 1.39)
    # Sunset hour angle
    ws_arg = -math.tan(lat_rad) * math.tan(decl)
    ws_arg = max(-1.0, min(1.0, ws_arg))
    ws = math.acos(ws_arg)
    # Inverse relative distance Earth-Sun
    dr = 1 + 0.033 * math.cos(2 * math.pi / 365 * day_of_year)
    # Ra in MJ/m2/day
    ra = (
        24
        * 60
        / math.pi
        * 0.0820
        * dr
        * (ws * math.sin(lat_rad) * math.sin(decl)
           + math.cos(lat_rad) * math.cos(decl) * math.sin(ws))
    )
    return max(ra, 0.0)


@dataclass
class Zone:
    """Irrigation zone runtime state."""

    key: str
    name: str
    valve_entity: str
    area_m2: float
    base_duration: int  # minutes
    max_duration: int
    soil_moisture_entity: str | None = None
    soil_temperature_entity: str | None = None
    soil_battery_entity: str | None = None
    flow_meter_entity: str | None = None

    # Runtime state
    enabled: bool = True
    active: bool = False
    remaining_seconds: int = 0
    adjustment: float = DEFAULT_ZONE_ADJUSTMENT  # %
    crop_kc: float = DEFAULT_CROP_KC
    bucket: float = 0.0  # mm, negative = needs water
    volume_today: float = 0.0  # liters
    next_run: datetime | None = None
    duration_override: int | None = None  # minutes

    @property
    def effective_duration(self) -> int:
        """Calculate effective watering duration in minutes."""
        base = self.duration_override if self.duration_override is not None else self.base_duration
        adjusted = base * (self.adjustment / 100.0)
        return max(1, min(int(adjusted), self.max_duration))

    @classmethod
    def from_config(cls, zone_cfg: dict[str, Any]) -> Zone:
        """Create zone from YAML config dict."""
        return cls(
            key=zone_cfg[CONF_ZONE_KEY],
            name=zone_cfg[CONF_ZONE_NAME],
            valve_entity=zone_cfg[CONF_VALVE],
            area_m2=zone_cfg[CONF_AREA_M2],
            base_duration=zone_cfg[CONF_DURATION],
            max_duration=zone_cfg[CONF_MAX_DURATION],
            soil_moisture_entity=zone_cfg.get(CONF_SOIL_MOISTURE),
            soil_temperature_entity=zone_cfg.get(CONF_SOIL_TEMPERATURE),
            soil_battery_entity=zone_cfg.get(CONF_SOIL_BATTERY),
            flow_meter_entity=zone_cfg.get(CONF_FLOW_METER),
        )


class ETCalculator:
    """Hargreaves ET0 calculator."""

    def __init__(self, latitude: float) -> None:
        self._latitude = latitude
        self.et_daily: float = 0.0  # mm/day

    def calculate(self, t_min: float, t_max: float, day_of_year: int) -> float:
        """Calculate daily ET0 using Hargreaves equation.

        ET0 = 0.0023 * (T_mean + 17.8) * (T_max - T_min)^0.5 * Ra
        Ra in mm/day (divide MJ by 2.45 latent heat).
        """
        if t_max <= t_min:
            return 0.0

        t_mean = (t_min + t_max) / 2.0
        ra_mj = _get_ra(self._latitude, day_of_year)
        ra_mm = ra_mj / 2.45  # MJ to mm equivalent

        et0 = 0.0023 * (t_mean + 17.8) * math.sqrt(t_max - t_min) * ra_mm
        self.et_daily = max(et0, 0.0)
        return self.et_daily


class BucketTracker:
    """Per-zone moisture balance tracker."""

    def __init__(self, bucket_max: float, moisture_threshold: float) -> None:
        self._bucket_max = bucket_max
        self._moisture_threshold = moisture_threshold

    def apply_et(self, zone: Zone, et_daily: float) -> None:
        """Apply daily ET loss to zone bucket (call once per day)."""
        zone.bucket -= et_daily * zone.crop_kc

    def apply_rain(self, zone: Zone, rain_mm: float) -> None:
        """Apply rain gain to zone bucket."""
        zone.bucket = min(zone.bucket + rain_mm, self._bucket_max)

    def apply_irrigation(self, zone: Zone, duration_minutes: int) -> None:
        """Apply irrigation to bucket (approximate 2mm per minute as default)."""
        mm_applied = duration_minutes * 2.0
        zone.bucket = min(zone.bucket + mm_applied, self._bucket_max)

    def correct_from_sensor(self, zone: Zone, soil_moisture: float) -> None:
        """Correct bucket using actual soil moisture reading."""
        if soil_moisture > 60.0:
            zone.bucket = max(zone.bucket, 0.0)
        elif soil_moisture < 20.0:
            zone.bucket = min(zone.bucket * 1.5, -self._bucket_max)

    def should_skip(self, zone: Zone, soil_moisture: float | None) -> bool:
        """Determine if zone should skip watering."""
        if zone.bucket >= 0:
            return True
        if soil_moisture is not None and soil_moisture > self._moisture_threshold:
            return True
        return False

    def get_adjustment(self, zone: Zone) -> float:
        """Get duration adjustment based on bucket deficit (0-200%)."""
        if zone.bucket >= 0:
            return 0.0
        deficit_ratio = abs(zone.bucket) / self._bucket_max
        return min(deficit_ratio * 100.0, 200.0)


class PumpController:
    """Rainwater tank pump controller."""

    def __init__(
        self,
        hass: HomeAssistant,
        level_sensor: str,
        pump_switch: str | None,
        on_above: float,
        off_below: float,
    ) -> None:
        self._hass = hass
        self._level_sensor = level_sensor
        self._pump_switch = pump_switch
        self._on_above = on_above
        self._off_below = off_below

    @property
    def tank_level(self) -> float | None:
        """Get current tank level %."""
        state = self._hass.states.get(self._level_sensor)
        if state is None or state.state in (STATE_UNAVAILABLE, STATE_UNKNOWN):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    async def start_pump(self) -> bool:
        """Start pump if tank level sufficient. Returns True if pump started."""
        if self._pump_switch is None:
            return True  # No pump configured, assume mains water

        level = self.tank_level
        if level is None or level < self._on_above:
            _LOGGER.info(
                "Tank level %.1f%% below threshold %.1f%%, using mains water",
                level or 0, self._on_above,
            )
            return False

        await self._hass.services.async_call(
            "switch", "turn_on", {"entity_id": self._pump_switch}
        )
        _LOGGER.info("Pump started, tank level: %.1f%%", level)
        return True

    async def stop_pump(self) -> None:
        """Stop pump."""
        if self._pump_switch is None:
            return

        await self._hass.services.async_call(
            "switch", "turn_off", {"entity_id": self._pump_switch}
        )
        _LOGGER.info("Pump stopped")

    def should_stop_pump(self) -> bool:
        """Check if pump should be stopped due to low tank."""
        level = self.tank_level
        return level is not None and level < self._off_below


class AntifreezeManager:
    """Anti-freeze flush manager."""

    def __init__(
        self,
        tiers: list[dict],
        flush_duration: int,
        hibernation_below: float,
        recovery_above: float,
    ) -> None:
        self._tiers = sorted(tiers, key=lambda t: t["temp_max"])
        self._flush_duration = flush_duration
        self._hibernation_below = hibernation_below
        self._recovery_above = recovery_above
        self.last_flush_time: datetime | None = None
        self.is_hibernating: bool = False
        self._hibernation_start: datetime | None = None
        self._recovery_start: datetime | None = None

    def check_hibernation(self, avg_temp: float) -> bool:
        """Update hibernation state based on average soil temperature."""
        now = dt_util.utcnow()

        if self.is_hibernating:
            if avg_temp >= self._recovery_above:
                if self._recovery_start is None:
                    self._recovery_start = now
                elif (now - self._recovery_start).total_seconds() >= 48 * 3600:
                    self.is_hibernating = False
                    self._recovery_start = None
                    _LOGGER.info("Exiting hibernation, temp recovered to %.1f°C", avg_temp)
            else:
                self._recovery_start = None
        else:
            if avg_temp < self._hibernation_below:
                if self._hibernation_start is None:
                    self._hibernation_start = now
                elif (now - self._hibernation_start).total_seconds() >= 24 * 3600:
                    self.is_hibernating = True
                    self._hibernation_start = None
                    _LOGGER.info("Entering hibernation, temp %.1f°C for 24h", avg_temp)
            else:
                self._hibernation_start = None

        return self.is_hibernating

    def should_flush(self, avg_temp: float) -> bool:
        """Check if anti-freeze flush is needed based on temperature."""
        if self.is_hibernating:
            return False

        tier = self._get_tier(avg_temp)
        if tier is None:
            return False

        if self.last_flush_time is None:
            return True

        elapsed = (dt_util.utcnow() - self.last_flush_time).total_seconds()
        return elapsed >= tier["interval"] * 60

    def _get_tier(self, avg_temp: float) -> dict | None:
        """Find matching anti-freeze tier for temperature."""
        for tier in self._tiers:
            if avg_temp <= tier["temp_max"]:
                return tier
        return None

    @property
    def flush_duration(self) -> int:
        """Return flush duration in seconds."""
        return self._flush_duration


class Sequencer:
    """Zone sequencer state machine."""

    def __init__(
        self,
        hass: HomeAssistant,
        zones: list[Zone],
        inter_zone_delay: int,
        pump: PumpController | None,
    ) -> None:
        self._hass = hass
        self._zones = zones
        self._inter_zone_delay = inter_zone_delay
        self._pump = pump
        self.state: SequencerState = SequencerState.IDLE
        self._task: asyncio.Task | None = None
        self._cancel_event = asyncio.Event()
        self._coordinator: PodlewanieCoordinator | None = None

    def set_coordinator(self, coordinator: PodlewanieCoordinator) -> None:
        """Set coordinator reference for state updates."""
        self._coordinator = coordinator

    @property
    def is_running(self) -> bool:
        """Return True if sequencer is active."""
        return self.state not in (SequencerState.IDLE, SequencerState.STOPPING)

    async def run_sequence(
        self,
        zones: list[Zone] | None = None,
        season_multiplier: float = 100.0,
    ) -> None:
        """Run full irrigation sequence."""
        if self.is_running:
            _LOGGER.warning("Sequencer already running, ignoring request")
            return

        target_zones = zones or [z for z in self._zones if z.enabled]
        if not target_zones:
            _LOGGER.info("No enabled zones to run")
            return

        self._cancel_event.clear()
        self._task = self._hass.async_create_task(
            self._run_sequence_task(target_zones, season_multiplier)
        )

    async def run_single(self, zone: Zone, duration: int | None = None) -> None:
        """Run single zone manually."""
        if self.is_running:
            _LOGGER.warning("Sequencer already running, ignoring manual request")
            return

        self._cancel_event.clear()
        self._task = self._hass.async_create_task(
            self._run_single_task(zone, duration)
        )

    async def run_antifreeze(self, zones: list[Zone], flush_seconds: int) -> None:
        """Run anti-freeze flush on all zones."""
        if self.is_running:
            _LOGGER.warning("Sequencer already running, ignoring antifreeze request")
            return

        self._cancel_event.clear()
        self._task = self._hass.async_create_task(
            self._run_antifreeze_task(zones, flush_seconds)
        )

    async def cancel(self) -> None:
        """Cancel current sequence."""
        if self._task is not None and not self._task.done():
            self._cancel_event.set()
            try:
                await asyncio.wait_for(self._task, timeout=30)
            except asyncio.TimeoutError:
                self._task.cancel()
                _LOGGER.warning("Sequencer task force-cancelled after timeout")

    async def _run_sequence_task(
        self, zones: list[Zone], season_multiplier: float
    ) -> None:
        """Internal sequence task."""
        try:
            # Prime pump
            if self._pump is not None:
                self.state = SequencerState.PRIMING_PUMP
                self._notify_update()
                pump_ok = await self._pump.start_pump()
                if not pump_ok:
                    _LOGGER.info("Pump failed, proceeding with mains water")

            for i, zone in enumerate(zones):
                if self._cancel_event.is_set():
                    break

                duration = int(
                    zone.effective_duration * (season_multiplier / 100.0)
                )
                duration = max(1, min(duration, zone.max_duration))

                await self._water_zone(zone, duration)

                # Inter-zone delay (except after last zone)
                if i < len(zones) - 1 and not self._cancel_event.is_set():
                    self.state = SequencerState.INTER_ZONE_DELAY
                    self._notify_update()
                    await self._interruptible_sleep(self._inter_zone_delay)

        except asyncio.CancelledError:
            _LOGGER.info("Sequence cancelled")
        finally:
            await self._stop_all(zones)

    async def _run_single_task(self, zone: Zone, duration: int | None) -> None:
        """Internal single zone task."""
        try:
            if self._pump is not None:
                self.state = SequencerState.PRIMING_PUMP
                self._notify_update()
                await self._pump.start_pump()

            dur = duration or zone.effective_duration
            dur = max(1, min(dur, zone.max_duration))
            await self._water_zone(zone, dur)

        except asyncio.CancelledError:
            _LOGGER.info("Manual run cancelled")
        finally:
            await self._stop_all([zone])

    async def _run_antifreeze_task(
        self, zones: list[Zone], flush_seconds: int
    ) -> None:
        """Internal antifreeze flush task."""
        try:
            for i, zone in enumerate(zones):
                if self._cancel_event.is_set():
                    break

                _LOGGER.info("Antifreeze flush: %s (%ds)", zone.name, flush_seconds)
                await self._open_valve(zone)

                # Flush duration in seconds
                self.state = SequencerState.WATERING
                self._notify_update()
                await self._interruptible_sleep(flush_seconds)

                await self._close_valve(zone)

                if i < len(zones) - 1 and not self._cancel_event.is_set():
                    self.state = SequencerState.INTER_ZONE_DELAY
                    self._notify_update()
                    await self._interruptible_sleep(60)

        except asyncio.CancelledError:
            _LOGGER.info("Antifreeze cancelled")
        finally:
            await self._stop_all(zones)

    async def _water_zone(self, zone: Zone, duration_minutes: int) -> None:
        """Water a single zone for given duration."""
        _LOGGER.info(
            "Starting zone %s for %d minutes", zone.name, duration_minutes
        )
        await self._open_valve(zone)

        self.state = SequencerState.WATERING
        zone.active = True
        zone.remaining_seconds = duration_minutes * 60
        self._notify_update()

        # Count down in 1-second intervals
        while zone.remaining_seconds > 0 and not self._cancel_event.is_set():
            await self._interruptible_sleep(1)
            zone.remaining_seconds -= 1

            # Check pump level periodically
            if (
                self._pump is not None
                and zone.remaining_seconds % 60 == 0
                and self._pump.should_stop_pump()
            ):
                _LOGGER.warning("Tank level low, stopping zone %s", zone.name)
                break

            # Update remaining every 10 seconds
            if zone.remaining_seconds % 10 == 0:
                self._notify_update()

        await self._close_valve(zone)
        zone.active = False
        zone.remaining_seconds = 0
        self._notify_update()

    async def _open_valve(self, zone: Zone) -> None:
        """Open zone valve with verification (supports switch.* and valve.*)."""
        entity_id = zone.valve_entity
        if entity_id.startswith("valve."):
            await self._hass.services.async_call(
                "valve", "open_valve", {"entity_id": entity_id}
            )
            expected_state = "open"
        else:
            await self._hass.services.async_call(
                "switch", "turn_on", {"entity_id": entity_id}
            )
            expected_state = STATE_ON
        await asyncio.sleep(VALVE_VERIFY_DELAY)

        state = self._hass.states.get(entity_id)
        if state is None or state.state != expected_state:
            _LOGGER.warning(
                "Valve %s did not open (state: %s, expected: %s)",
                entity_id,
                state.state if state else "unknown",
                expected_state,
            )

    async def _close_valve(self, zone: Zone) -> None:
        """Close zone valve (supports switch.* and valve.*)."""
        entity_id = zone.valve_entity
        if entity_id.startswith("valve."):
            await self._hass.services.async_call(
                "valve", "close_valve", {"entity_id": entity_id}
            )
        else:
            await self._hass.services.async_call(
                "switch", "turn_off", {"entity_id": entity_id}
            )

    async def _stop_all(self, zones: list[Zone]) -> None:
        """Stop all zones and pump."""
        self.state = SequencerState.STOPPING
        self._notify_update()

        for zone in zones:
            if zone.active:
                await self._close_valve(zone)
                zone.active = False
                zone.remaining_seconds = 0

        if self._pump is not None:
            await self._pump.stop_pump()

        self.state = SequencerState.IDLE
        self._notify_update()

    async def _interruptible_sleep(self, seconds: int) -> None:
        """Sleep that can be interrupted by cancel event."""
        try:
            await asyncio.wait_for(
                self._cancel_event.wait(), timeout=seconds
            )
        except asyncio.TimeoutError:
            pass  # Normal timeout = sleep completed

    def _notify_update(self) -> None:
        """Notify coordinator of state change."""
        if self._coordinator is not None:
            self._coordinator.async_set_updated_data(
                self._coordinator.data or {}
            )
