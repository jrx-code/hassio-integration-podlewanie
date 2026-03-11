"""Switch platform for Podlewanie."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .binary_sensor import DEVICE_INFO
from .const import DOMAIN
from .coordinator import PodlewanieCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Podlewanie switches from config entry."""
    coordinator: PodlewanieCoordinator = hass.data[DOMAIN]["coordinator"]

    entities: list[SwitchEntity] = []

    for zone in coordinator.zones:
        entities.append(ZoneEnabledSwitch(coordinator, zone.key))

    entities.append(MasterEnabledSwitch(coordinator))

    async_add_entities(entities)


class ZoneEnabledSwitch(
    CoordinatorEntity[PodlewanieCoordinator], SwitchEntity
):
    """Switch to enable/disable a zone in schedules."""

    _attr_icon = "mdi:sprinkler"
    _attr_device_info = DEVICE_INFO

    def __init__(
        self, coordinator: PodlewanieCoordinator, zone_key: str
    ) -> None:
        super().__init__(coordinator)
        self._zone_key = zone_key
        zone = coordinator.get_zone(zone_key)
        self._attr_name = f"Podlewanie {zone.name} Enabled"
        self._attr_unique_id = f"podlewanie_{zone_key}_enabled"

    @property
    def is_on(self) -> bool:
        zone = self.coordinator.get_zone(self._zone_key)
        return zone.enabled if zone else False

    async def async_turn_on(self, **kwargs) -> None:
        zone = self.coordinator.get_zone(self._zone_key)
        if zone:
            zone.enabled = True
            self.coordinator.async_set_updated_data(
                self.coordinator.data or {}
            )

    async def async_turn_off(self, **kwargs) -> None:
        zone = self.coordinator.get_zone(self._zone_key)
        if zone:
            zone.enabled = False
            self.coordinator.async_set_updated_data(
                self.coordinator.data or {}
            )


class MasterEnabledSwitch(
    CoordinatorEntity[PodlewanieCoordinator], SwitchEntity
):
    """Master ON/OFF switch for the entire irrigation system."""

    _attr_icon = "mdi:sprinkler-variant"
    _attr_device_info = DEVICE_INFO

    def __init__(self, coordinator: PodlewanieCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_name = "Podlewanie Enabled"
        self._attr_unique_id = "podlewanie_enabled"

    @property
    def is_on(self) -> bool:
        return self.coordinator.master_enabled

    async def async_turn_on(self, **kwargs) -> None:
        self.coordinator.master_enabled = True
        self.coordinator.async_set_updated_data(
            self.coordinator.data or {}
        )

    async def async_turn_off(self, **kwargs) -> None:
        self.coordinator.master_enabled = False
        await self.coordinator.sequencer.cancel()
        self.coordinator.async_set_updated_data(
            self.coordinator.data or {}
        )
