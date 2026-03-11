"""The Podlewanie integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import PodlewanieCoordinator
from .schema import CONFIG_SCHEMA as PODLEWANIE_SCHEMA

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]

CONFIG_SCHEMA = vol.Schema(
    {vol.Optional(DOMAIN): PODLEWANIE_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Podlewanie integration from YAML."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    coordinator = PodlewanieCoordinator(hass, conf)
    await coordinator.async_setup()
    await coordinator.async_refresh()

    hass.data[DOMAIN] = coordinator

    # Discover platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(hass, platform, DOMAIN, {}, config)
        )

    # Register services
    from .services import async_register_services

    await async_register_services(hass)

    return True


async def async_unload(hass: HomeAssistant) -> bool:
    """Unload the integration."""
    coordinator: PodlewanieCoordinator = hass.data.get(DOMAIN)
    if coordinator:
        await coordinator.async_unload()
    hass.data.pop(DOMAIN, None)
    return True
