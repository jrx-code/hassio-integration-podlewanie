"""Binary sensor platform for Podlewanie (v2 — device-per-zone)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .__init__ import PodlewanieConfigEntry
from .const import controller_device_info, zone_device_info
from .coordinator import PodlewanieCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: PodlewanieConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Podlewanie binary sensors from config entry."""
    coordinator: PodlewanieCoordinator = entry.runtime_data

    entities: list[BinarySensorEntity] = []

    for zone in coordinator.zones:
        entities.append(ZoneActiveBinarySensor(coordinator, zone.key))

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
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        entry_id = coordinator.entry.entry_id
        self._attr_device_info = zone_device_info(entry_id, zone_key, zone.name)
        self._attr_name = f"Podlewanie {zone.name} Active"
        self._attr_unique_id = f"podlewanie_{zone_key}_active"

    @property
    def is_on(self) -> bool:
        zone = self.coordinator.get_zone(self._zone_key)
        return zone.active if zone else False


class ControllerRunningBinarySensor(
    CoordinatorEntity[PodlewanieCoordinator], BinarySensorEntity
):
    """Binary sensor indicating if the controller is running."""

    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, coordinator: PodlewanieCoordinator) -> None:
        super().__init__(coordinator)
        entry_id = coordinator.entry.entry_id
        self._attr_device_info = controller_device_info(entry_id)
        self._attr_name = "Podlewanie Running"
        self._attr_unique_id = "podlewanie_running"

    @property
    def is_on(self) -> bool:
        return self.coordinator.sequencer.is_running
