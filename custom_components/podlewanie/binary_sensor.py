"""Binary sensor platform for Podlewanie."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
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
    """Set up Podlewanie binary sensors from YAML discovery."""
    coordinator: PodlewanieCoordinator = hass.data[DOMAIN]

    entities: list[BinarySensorEntity] = []

    # Per-zone active sensors
    for zone in coordinator.zones:
        entities.append(ZoneActiveBinarySensor(coordinator, zone.key))

    # Master running sensor
    entities.append(ControllerRunningBinarySensor(coordinator))

    async_add_entities(entities)


class ZoneActiveBinarySensor(
    CoordinatorEntity[PodlewanieCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if a zone is actively watering."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Active"
        self._attr_unique_id = f"podlewanie_{zone_key}_active"

    @property
    def is_on(self) -> bool:
        """Return true if zone is watering."""
        zone = self.coordinator.get_zone(self._zone_key)
        return zone.active if zone else False


class ControllerRunningBinarySensor(
    CoordinatorEntity[PodlewanieCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if the controller is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: PodlewanieCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._attr_name = "Podlewanie Running"
        self._attr_unique_id = "podlewanie_running"

    @property
    def is_on(self) -> bool:
        """Return true if sequencer is running."""
        return self.coordinator.sequencer.is_running
