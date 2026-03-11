"""Number platform for Podlewanie."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .binary_sensor import DEVICE_INFO
from .const import (
    DEFAULT_CROP_KC,
    DEFAULT_ZONE_ADJUSTMENT,
    DOMAIN,
)
from .coordinator import PodlewanieCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Podlewanie numbers from config entry."""
    coordinator: PodlewanieCoordinator = hass.data[DOMAIN]["coordinator"]

    entities: list[NumberEntity] = []

    for zone in coordinator.zones:
        entities.extend([
            ZoneDurationNumber(coordinator, zone.key),
            ZoneAdjustmentNumber(coordinator, zone.key),
            ZoneCropKcNumber(coordinator, zone.key),
        ])

    entities.extend([
        MoistureThresholdNumber(coordinator),
        RainThresholdNumber(coordinator),
        SeasonMultiplierNumber(coordinator),
    ])

    async_add_entities(entities)


class ZoneDurationNumber(
    CoordinatorEntity[PodlewanieCoordinator], NumberEntity
):
    """Override watering duration for a zone."""

    _attr_native_min_value = 1
    _attr_native_max_value = 120
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "min"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:timer-outline"
    _attr_device_info = DEVICE_INFO

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Duration"
        self._attr_unique_id = f"podlewanie_{zone_key}_duration"

    @property
    def native_value(self) -> float | None:
        zone = self.coordinator.get_zone(self._zone_key)
        if zone is None:
            return None
        return float(
            zone.duration_override
            if zone.duration_override is not None
            else zone.base_duration
        )

    async def async_set_native_value(self, value: float) -> None:
        zone = self.coordinator.get_zone(self._zone_key)
        if zone:
            zone.duration_override = int(value)
            self.coordinator.async_set_updated_data(
                self.coordinator.data or {}
            )


class ZoneAdjustmentNumber(
    CoordinatorEntity[PodlewanieCoordinator], NumberEntity
):
    """Zone duration adjustment multiplier."""

    _attr_native_min_value = 0
    _attr_native_max_value = 200
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:tune-variant"
    _attr_device_info = DEVICE_INFO

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Adjustment"
        self._attr_unique_id = f"podlewanie_{zone_key}_adjustment"

    @property
    def native_value(self) -> float | None:
        zone = self.coordinator.get_zone(self._zone_key)
        return zone.adjustment if zone else DEFAULT_ZONE_ADJUSTMENT

    async def async_set_native_value(self, value: float) -> None:
        zone = self.coordinator.get_zone(self._zone_key)
        if zone:
            zone.adjustment = value
            self.coordinator.async_set_updated_data(
                self.coordinator.data or {}
            )


class ZoneCropKcNumber(
    CoordinatorEntity[PodlewanieCoordinator], NumberEntity
):
    """Crop coefficient (Kc) for ET calculation per zone."""

    _attr_native_min_value = 0.1
    _attr_native_max_value = 2.0
    _attr_native_step = 0.05
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:grass"
    _attr_device_info = DEVICE_INFO

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Crop Kc"
        self._attr_unique_id = f"podlewanie_{zone_key}_crop_kc"

    @property
    def native_value(self) -> float | None:
        zone = self.coordinator.get_zone(self._zone_key)
        return zone.crop_kc if zone else DEFAULT_CROP_KC

    async def async_set_native_value(self, value: float) -> None:
        zone = self.coordinator.get_zone(self._zone_key)
        if zone:
            zone.crop_kc = value
            self.coordinator.async_set_updated_data(
                self.coordinator.data or {}
            )


class MoistureThresholdNumber(
    CoordinatorEntity[PodlewanieCoordinator], NumberEntity
):
    """Global moisture threshold for skip decision."""

    _attr_native_min_value = 10
    _attr_native_max_value = 90
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:water-percent"
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: PodlewanieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Podlewanie Moisture Threshold"
        self._attr_unique_id = "podlewanie_moisture_threshold"

    @property
    def native_value(self) -> float:
        return self.coordinator.moisture_threshold_override

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.moisture_threshold_override = value
        self.coordinator._bucket_tracker._moisture_threshold = value
        self.coordinator.async_set_updated_data(
            self.coordinator.data or {}
        )


class RainThresholdNumber(
    CoordinatorEntity[PodlewanieCoordinator], NumberEntity
):
    """Rain threshold for skip decision."""

    _attr_native_min_value = 0.1
    _attr_native_max_value = 20.0
    _attr_native_step = 0.1
    _attr_native_unit_of_measurement = "mm/h"
    _attr_mode = NumberMode.BOX
    _attr_icon = "mdi:weather-rainy"
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: PodlewanieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Podlewanie Rain Threshold"
        self._attr_unique_id = "podlewanie_rain_threshold"

    @property
    def native_value(self) -> float:
        return self.coordinator.rain_threshold

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.rain_threshold = value
        self.coordinator.async_set_updated_data(
            self.coordinator.data or {}
        )


class SeasonMultiplierNumber(
    CoordinatorEntity[PodlewanieCoordinator], NumberEntity
):
    """Seasonal multiplier applied to all zone durations."""

    _attr_native_min_value = 0
    _attr_native_max_value = 200
    _attr_native_step = 5
    _attr_native_unit_of_measurement = "%"
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:calendar-range"
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: PodlewanieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Podlewanie Season Multiplier"
        self._attr_unique_id = "podlewanie_season_multiplier"

    @property
    def native_value(self) -> float:
        return self.coordinator.season_multiplier

    async def async_set_native_value(self, value: float) -> None:
        self.coordinator.season_multiplier = value
        self.coordinator.async_set_updated_data(
            self.coordinator.data or {}
        )
