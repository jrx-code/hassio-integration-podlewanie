"""Sensor platform for Podlewanie."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfTime, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PodlewanieCoordinator


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up Podlewanie sensors from YAML discovery."""
    coordinator: PodlewanieCoordinator = hass.data[DOMAIN]

    entities: list[SensorEntity] = []

    for zone in coordinator.zones:
        entities.extend([
            ZoneRemainingSensor(coordinator, zone.key),
            ZoneNextRunSensor(coordinator, zone.key),
            ZoneVolumeTodaySensor(coordinator, zone.key),
            ZoneBucketSensor(coordinator, zone.key),
            ZoneSoilSensor(coordinator, zone.key),
        ])

    entities.append(ETDailySensor(coordinator))
    entities.append(StatusSensor(coordinator))

    async_add_entities(entities)


class ZoneRemainingSensor(
    CoordinatorEntity[PodlewanieCoordinator], SensorEntity
):
    """Remaining watering time for a zone."""

    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Remaining"
        self._attr_unique_id = f"podlewanie_{zone_key}_remaining"

    @property
    def native_value(self) -> float | None:
        zone = self.coordinator.get_zone(self._zone_key)
        if zone is None:
            return None
        return round(zone.remaining_seconds / 60, 1) if zone.remaining_seconds > 0 else 0


class ZoneNextRunSensor(
    CoordinatorEntity[PodlewanieCoordinator], SensorEntity
):
    """Next scheduled run time for a zone."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Next Run"
        self._attr_unique_id = f"podlewanie_{zone_key}_next_run"

    @property
    def native_value(self) -> datetime | None:
        zone = self.coordinator.get_zone(self._zone_key)
        return zone.next_run if zone else None


class ZoneVolumeTodaySensor(
    CoordinatorEntity[PodlewanieCoordinator], SensorEntity
):
    """Today's water volume for a zone."""

    _attr_device_class = SensorDeviceClass.VOLUME
    _attr_native_unit_of_measurement = UnitOfVolume.LITERS
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Volume Today"
        self._attr_unique_id = f"podlewanie_{zone_key}_volume_today"

    @property
    def native_value(self) -> float | None:
        zone = self.coordinator.get_zone(self._zone_key)
        return round(zone.volume_today, 1) if zone else None


class ZoneBucketSensor(
    CoordinatorEntity[PodlewanieCoordinator], SensorEntity
):
    """ET moisture bucket balance for a zone."""

    _attr_native_unit_of_measurement = "mm"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:water-opacity"

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Bucket"
        self._attr_unique_id = f"podlewanie_{zone_key}_bucket"

    @property
    def native_value(self) -> float | None:
        zone = self.coordinator.get_zone(self._zone_key)
        return round(zone.bucket, 1) if zone else None


class ZoneSoilSensor(
    CoordinatorEntity[PodlewanieCoordinator], SensorEntity
):
    """Mirror of soil moisture sensor for a zone."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_class = SensorDeviceClass.MOISTURE
    _attr_icon = "mdi:water-percent"

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Soil"
        self._attr_unique_id = f"podlewanie_{zone_key}_soil"
        self._soil_entity = zone.soil_moisture_entity

    @property
    def native_value(self) -> float | None:
        if self._soil_entity is None:
            return None
        state = self.coordinator.hass.states.get(self._soil_entity)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        try:
            return round(float(state.state), 1)
        except (ValueError, TypeError):
            return None


class ETDailySensor(
    CoordinatorEntity[PodlewanieCoordinator], SensorEntity
):
    """Daily evapotranspiration rate."""

    _attr_native_unit_of_measurement = "mm/day"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:weather-sunny-alert"

    def __init__(self, coordinator: PodlewanieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Podlewanie ET Daily"
        self._attr_unique_id = "podlewanie_et_daily"

    @property
    def native_value(self) -> float | None:
        return round(self.coordinator.et_daily, 2)


class StatusSensor(
    CoordinatorEntity[PodlewanieCoordinator], SensorEntity
):
    """Controller status sensor."""

    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, coordinator: PodlewanieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Podlewanie Status"
        self._attr_unique_id = "podlewanie_status"

    @property
    def native_value(self) -> str:
        # Derive status directly from live state, not cached coordinator.status
        if self.coordinator._antifreeze and self.coordinator._antifreeze.is_hibernating:
            return "hibernation"
        if self.coordinator.sequencer.is_running:
            return "running"
        if not self.coordinator.master_enabled:
            return "degraded"
        return "idle"

    @property
    def extra_state_attributes(self) -> dict:
        attrs = {
            "sequencer_state": self.coordinator.sequencer.state.value,
            "master_enabled": self.coordinator.master_enabled,
            "season_multiplier": self.coordinator.season_multiplier,
        }
        # Add active zone info
        for zone in self.coordinator.zones:
            if zone.active:
                attrs["active_zone"] = zone.name
                attrs["active_zone_remaining"] = zone.remaining_seconds
                break
        return attrs
