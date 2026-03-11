"""The Podlewanie integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
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
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN not in config:
        return True

    # Store YAML config for use by config entry setup
    hass.data[DOMAIN]["yaml_config"] = config[DOMAIN]

    # Auto-import: create config entry if YAML is present but no entry exists
    if not hass.config_entries.async_entries(DOMAIN):
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Podlewanie from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    yaml_config = hass.data[DOMAIN].get("yaml_config")
    if yaml_config is None:
        _LOGGER.error(
            "No YAML configuration found for podlewanie. "
            "Add 'podlewanie:' section to configuration.yaml"
        )
        return False

    coordinator = PodlewanieCoordinator(hass, yaml_config)
    await coordinator.async_setup()
    await coordinator.async_refresh()

    hass.data[DOMAIN]["coordinator"] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    from .services import async_register_services

    await async_register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        coordinator = hass.data[DOMAIN].get("coordinator")
        if coordinator:
            await coordinator.async_unload()
        hass.data[DOMAIN].pop("coordinator", None)

    return unload_ok
