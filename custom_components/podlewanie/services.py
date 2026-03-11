"""Service handlers for the Podlewanie integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import PodlewanieCoordinator

_LOGGER = logging.getLogger(__name__)

SERVICE_MANUAL_RUN = "manual_run"
SERVICE_RUN_SEQUENCE = "run_sequence"
SERVICE_CANCEL = "cancel"
SERVICE_ADJUST_TIME = "adjust_time"
SERVICE_ENABLE = "enable"
SERVICE_DISABLE = "disable"
SERVICE_RELOAD = "reload"

ATTR_ZONE = "zone"
ATTR_DURATION = "duration"
ATTR_PERCENTAGE = "percentage"

SERVICE_MANUAL_RUN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): cv.string,
        vol.Optional(ATTR_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=120)
        ),
    }
)

SERVICE_ADJUST_TIME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): cv.string,
        vol.Required(ATTR_PERCENTAGE): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=200)
        ),
    }
)

SERVICE_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ZONE): cv.string,
    }
)


async def async_register_services(hass: HomeAssistant) -> None:
    """Register Podlewanie services."""

    async def handle_manual_run(call: ServiceCall) -> None:
        coordinator: PodlewanieCoordinator = hass.data[DOMAIN]
        zone_key = call.data[ATTR_ZONE]
        duration = call.data.get(ATTR_DURATION)

        zone = coordinator.get_zone(zone_key)
        if zone is None:
            _LOGGER.error("Unknown zone: %s", zone_key)
            return

        _LOGGER.info(
            "Manual run: zone=%s, duration=%s",
            zone_key,
            duration or "default",
        )
        await coordinator.sequencer.run_single(zone, duration)

    async def handle_run_sequence(call: ServiceCall) -> None:
        coordinator: PodlewanieCoordinator = hass.data[DOMAIN]
        _LOGGER.info("Running full irrigation sequence")
        await coordinator.sequencer.run_sequence(
            season_multiplier=coordinator.season_multiplier
        )

    async def handle_cancel(call: ServiceCall) -> None:
        coordinator: PodlewanieCoordinator = hass.data[DOMAIN]
        _LOGGER.info("Cancelling irrigation")
        await coordinator.sequencer.cancel()

    async def handle_adjust_time(call: ServiceCall) -> None:
        coordinator: PodlewanieCoordinator = hass.data[DOMAIN]
        zone_key = call.data[ATTR_ZONE]
        percentage = call.data[ATTR_PERCENTAGE]

        zone = coordinator.get_zone(zone_key)
        if zone is None:
            _LOGGER.error("Unknown zone: %s", zone_key)
            return

        zone.adjustment = percentage
        _LOGGER.info("Zone %s adjustment set to %.0f%%", zone_key, percentage)
        coordinator.async_set_updated_data(coordinator.data or {})

    async def handle_enable(call: ServiceCall) -> None:
        coordinator: PodlewanieCoordinator = hass.data[DOMAIN]
        zone_key = call.data[ATTR_ZONE]

        zone = coordinator.get_zone(zone_key)
        if zone is None:
            _LOGGER.error("Unknown zone: %s", zone_key)
            return

        zone.enabled = True
        _LOGGER.info("Zone %s enabled", zone_key)
        coordinator.async_set_updated_data(coordinator.data or {})

    async def handle_disable(call: ServiceCall) -> None:
        coordinator: PodlewanieCoordinator = hass.data[DOMAIN]
        zone_key = call.data[ATTR_ZONE]

        zone = coordinator.get_zone(zone_key)
        if zone is None:
            _LOGGER.error("Unknown zone: %s", zone_key)
            return

        zone.enabled = False
        _LOGGER.info("Zone %s disabled", zone_key)
        coordinator.async_set_updated_data(coordinator.data or {})

    async def handle_reload(call: ServiceCall) -> None:
        _LOGGER.info("Reload requested — restart HA to reload YAML config")

    hass.services.async_register(
        DOMAIN, SERVICE_MANUAL_RUN, handle_manual_run, SERVICE_MANUAL_RUN_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_RUN_SEQUENCE, handle_run_sequence
    )
    hass.services.async_register(DOMAIN, SERVICE_CANCEL, handle_cancel)
    hass.services.async_register(
        DOMAIN, SERVICE_ADJUST_TIME, handle_adjust_time, SERVICE_ADJUST_TIME_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_ENABLE, handle_enable, SERVICE_ZONE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DISABLE, handle_disable, SERVICE_ZONE_SCHEMA
    )
    hass.services.async_register(DOMAIN, SERVICE_RELOAD, handle_reload)
