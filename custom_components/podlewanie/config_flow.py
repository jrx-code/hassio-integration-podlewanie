"""Config flow for Podlewanie integration (v2 — UI-only config)."""

from __future__ import annotations

import copy
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TimeSelector,
)

from .const import (
    DEFAULT_BUCKET_MAX,
    DEFAULT_FLUSH_DURATION,
    DEFAULT_FORECAST_HOURS,
    DEFAULT_FORECAST_RAIN_THRESHOLD,
    DEFAULT_HIBERNATION_BELOW,
    DEFAULT_INTER_ZONE_DELAY,
    DEFAULT_MAX_DURATION,
    DEFAULT_MOISTURE_THRESHOLD,
    DEFAULT_OPTIONS,
    DEFAULT_PUMP_OFF_BELOW,
    DEFAULT_PUMP_ON_ABOVE,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_RECOVERY_ABOVE,
    DOMAIN,
    MONTH_NAMES,
    WEEKDAY_NAMES,
)


def _slugify(name: str) -> str:
    """Create a slug key from a human name."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def _month_options() -> list[SelectOptionDict]:
    return [
        SelectOptionDict(value=str(m), label=n)
        for m, n in MONTH_NAMES.items()
    ]


def _weekday_options() -> list[SelectOptionDict]:
    return [
        SelectOptionDict(value=k, label=v)
        for k, v in WEEKDAY_NAMES.items()
    ]


# ── ConfigFlow ──────────────────────────────────────────────────────────


class PodlewanieConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Podlewanie."""

    VERSION = 2

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — just confirm adding."""
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Podlewanie",
                data={},
                options=copy.deepcopy(DEFAULT_OPTIONS),
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )

    async def async_step_import(
        self, import_data: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle import from YAML configuration (v1 migration)."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        from . import _yaml_to_options  # noqa: PLC0415

        options = _yaml_to_options(import_data) if import_data else copy.deepcopy(DEFAULT_OPTIONS)
        return self.async_create_entry(
            title="Podlewanie",
            data={},
            options=options,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> PodlewanieOptionsFlow:
        """Get the options flow handler."""
        return PodlewanieOptionsFlow()


# ── OptionsFlow ─────────────────────────────────────────────────────────


class PodlewanieOptionsFlow(OptionsFlow):
    """Handle Podlewanie options — menu-driven zone/schedule/weather config."""

    def __init__(self) -> None:
        """Initialize."""
        self._options: dict[str, Any] = {}
        self._zone_data: dict[str, Any] = {}
        self._schedule_data: dict[str, Any] = {}
        self._selected_zone: str = ""
        self._selected_schedule: str = ""

    # ── helpers ──

    def _ensure_options(self) -> None:
        if not self._options:
            self._options = copy.deepcopy(dict(self.config_entry.options))

    def _save(self) -> ConfigFlowResult:
        return self.async_create_entry(data=self._options)

    # ── main menu ──

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Main options menu."""
        self._ensure_options()

        menu_options = ["add_zone"]
        if self._options.get("zones"):
            menu_options.extend(["edit_zone", "remove_zone"])
        menu_options.extend([
            "schedules",
            "weather",
            "tank",
            "antifreeze",
            "et_settings",
            "sequencer",
        ])

        return self.async_show_menu(
            step_id="init",
            menu_options=menu_options,
        )

    # ── zone: add (2 steps) ──

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add zone — step 1: basic info."""
        if user_input is not None:
            self._zone_data = user_input
            return await self.async_step_add_zone_sensors()

        return self.async_show_form(
            step_id="add_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): TextSelector(),
                    vol.Required("valve"): EntitySelector(
                        EntitySelectorConfig(domain=["switch", "valve"])
                    ),
                    vol.Required("area_m2", default=40.0): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=1000, step=0.5,
                            unit_of_measurement="m\u00b2",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required("duration", default=15): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=120, step=1,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required("max_duration", default=DEFAULT_MAX_DURATION): NumberSelector(
                        NumberSelectorConfig(
                            min=1, max=180, step=1,
                            unit_of_measurement="min",
                            mode=NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

    async def async_step_add_zone_sensors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add zone — step 2: optional sensors."""
        if user_input is not None:
            name = self._zone_data["name"]
            key = _slugify(name)

            zones = list(self._options.get("zones", []))
            existing_keys = {z["key"] for z in zones}
            if key in existing_keys:
                i = 2
                while f"{key}_{i}" in existing_keys:
                    i += 1
                key = f"{key}_{i}"

            zone = {
                "key": key,
                "name": name,
                "valve": self._zone_data["valve"],
                "area_m2": self._zone_data["area_m2"],
                "duration": int(self._zone_data["duration"]),
                "max_duration": int(self._zone_data["max_duration"]),
                "soil_moisture": user_input.get("soil_moisture"),
                "soil_temperature": user_input.get("soil_temperature"),
                "soil_battery": user_input.get("soil_battery"),
                "flow_meter": user_input.get("flow_meter"),
            }
            zones.append(zone)
            self._options["zones"] = zones
            return self._save()

        return self.async_show_form(
            step_id="add_zone_sensors",
            data_schema=vol.Schema(
                {
                    vol.Optional("soil_moisture"): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional("soil_temperature"): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional("soil_battery"): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional("flow_meter"): EntitySelector(
                        EntitySelectorConfig(domain="sensor")
                    ),
                }
            ),
        )

    # ── zone: edit ──

    async def async_step_edit_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select zone to edit."""
        zones = self._options.get("zones", [])
        if not zones:
            return await self.async_step_init()

        if user_input is not None:
            self._selected_zone = user_input["zone"]
            return await self.async_step_edit_zone_settings()

        return self.async_show_form(
            step_id="edit_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=z["key"], label=z["name"])
                                for z in zones
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_zone_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit zone settings form."""
        zones = self._options.get("zones", [])
        current = next((z for z in zones if z["key"] == self._selected_zone), None)
        if current is None:
            return await self.async_step_init()

        if user_input is not None:
            current["name"] = user_input["name"]
            current["valve"] = user_input["valve"]
            current["area_m2"] = user_input["area_m2"]
            current["duration"] = int(user_input["duration"])
            current["max_duration"] = int(user_input["max_duration"])
            current["soil_moisture"] = user_input.get("soil_moisture")
            current["soil_temperature"] = user_input.get("soil_temperature")
            current["soil_battery"] = user_input.get("soil_battery")
            current["flow_meter"] = user_input.get("flow_meter")
            return self._save()

        schema = {
            vol.Required("name", default=current["name"]): TextSelector(),
            vol.Required("valve", default=current["valve"]): EntitySelector(
                EntitySelectorConfig(domain=["switch", "valve"])
            ),
            vol.Required("area_m2", default=current["area_m2"]): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=1000, step=0.5,
                    unit_of_measurement="m\u00b2",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required("duration", default=current["duration"]): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=120, step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required("max_duration", default=current["max_duration"]): NumberSelector(
                NumberSelectorConfig(
                    min=1, max=180, step=1,
                    unit_of_measurement="min",
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
        # Optional sensors — use default only if currently set
        for field in ("soil_moisture", "soil_temperature", "soil_battery", "flow_meter"):
            if current.get(field):
                schema[vol.Optional(field, default=current[field])] = EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                )
            else:
                schema[vol.Optional(field)] = EntitySelector(
                    EntitySelectorConfig(domain="sensor")
                )

        return self.async_show_form(
            step_id="edit_zone_settings",
            data_schema=vol.Schema(schema),
        )

    # ── zone: remove ──

    async def async_step_remove_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select zone to remove."""
        zones = self._options.get("zones", [])
        if not zones:
            return await self.async_step_init()

        if user_input is not None:
            self._selected_zone = user_input["zone"]
            return await self.async_step_remove_zone_confirm()

        return self.async_show_form(
            step_id="remove_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(value=z["key"], label=z["name"])
                                for z in zones
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_remove_zone_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm zone removal."""
        if user_input is not None:
            zones = [z for z in self._options.get("zones", []) if z["key"] != self._selected_zone]
            self._options["zones"] = zones
            return self._save()

        return self.async_show_form(
            step_id="remove_zone_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"zone": self._selected_zone},
        )

    # ── schedules: sub-menu ──

    async def async_step_schedules(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Schedules sub-menu."""
        menu_options = ["add_schedule"]
        if self._options.get("schedules"):
            menu_options.extend(["edit_schedule", "remove_schedule"])
        return self.async_show_menu(
            step_id="schedules",
            menu_options=menu_options,
        )

    async def async_step_add_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add a schedule."""
        if user_input is not None:
            schedules = list(self._options.get("schedules", []))
            key = _slugify(user_input["key"])
            existing_keys = {s["key"] for s in schedules}
            if key in existing_keys:
                i = 2
                while f"{key}_{i}" in existing_keys:
                    i += 1
                key = f"{key}_{i}"

            schedule = {
                "key": key,
                "time": user_input["time"],
                "months": [int(m) for m in user_input["months"]],
                "weekdays": user_input["weekdays"],
                "retry_next_day": user_input.get("retry_next_day", False),
            }
            schedules.append(schedule)
            self._options["schedules"] = schedules
            return self._save()

        return self.async_show_form(
            step_id="add_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("key"): TextSelector(),
                    vol.Required("time"): TimeSelector(),
                    vol.Required("months"): SelectSelector(
                        SelectSelectorConfig(
                            options=_month_options(),
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required("weekdays"): SelectSelector(
                        SelectSelectorConfig(
                            options=_weekday_options(),
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("retry_next_day", default=False): BooleanSelector(),
                }
            ),
        )

    async def async_step_edit_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select schedule to edit."""
        schedules = self._options.get("schedules", [])
        if not schedules:
            return await self.async_step_schedules()

        if user_input is not None:
            self._selected_schedule = user_input["schedule"]
            return await self.async_step_edit_schedule_settings()

        return self.async_show_form(
            step_id="edit_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=s["key"],
                                    label=f"{s['key']} ({s['time']})",
                                )
                                for s in schedules
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_schedule_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit schedule settings."""
        schedules = self._options.get("schedules", [])
        current = next(
            (s for s in schedules if s["key"] == self._selected_schedule), None
        )
        if current is None:
            return await self.async_step_schedules()

        if user_input is not None:
            current["time"] = user_input["time"]
            current["months"] = [int(m) for m in user_input["months"]]
            current["weekdays"] = user_input["weekdays"]
            current["retry_next_day"] = user_input.get("retry_next_day", False)
            return self._save()

        return self.async_show_form(
            step_id="edit_schedule_settings",
            data_schema=vol.Schema(
                {
                    vol.Required("time", default=current["time"]): TimeSelector(),
                    vol.Required(
                        "months", default=[str(m) for m in current["months"]]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_month_options(),
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Required(
                        "weekdays", default=current["weekdays"]
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=_weekday_options(),
                            multiple=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional(
                        "retry_next_day",
                        default=current.get("retry_next_day", False),
                    ): BooleanSelector(),
                }
            ),
        )

    async def async_step_remove_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Select schedule to remove."""
        schedules = self._options.get("schedules", [])
        if not schedules:
            return await self.async_step_schedules()

        if user_input is not None:
            self._selected_schedule = user_input["schedule"]
            return await self.async_step_remove_schedule_confirm()

        return self.async_show_form(
            step_id="remove_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required("schedule"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=s["key"],
                                    label=f"{s['key']} ({s['time']})",
                                )
                                for s in schedules
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_remove_schedule_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm schedule removal."""
        if user_input is not None:
            schedules = [
                s for s in self._options.get("schedules", [])
                if s["key"] != self._selected_schedule
            ]
            self._options["schedules"] = schedules
            return self._save()

        return self.async_show_form(
            step_id="remove_schedule_confirm",
            data_schema=vol.Schema({}),
            description_placeholders={"schedule": self._selected_schedule},
        )

    # ── weather ──

    async def async_step_weather(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Weather settings form."""
        weather = self._options.get("weather", {})

        if user_input is not None:
            self._options["weather"] = {
                "rain_sensors": user_input.get("rain_sensors", []),
                "rain_binary": user_input.get("rain_binary"),
                "forecast_entity": user_input.get("forecast_entity"),
                "forecast_hours": int(user_input.get("forecast_hours", DEFAULT_FORECAST_HOURS)),
                "rain_threshold": user_input.get("rain_threshold", DEFAULT_RAIN_THRESHOLD),
                "forecast_rain_threshold": user_input.get(
                    "forecast_rain_threshold", DEFAULT_FORECAST_RAIN_THRESHOLD
                ),
            }
            return self._save()

        schema: dict = {}
        rain_sensors = weather.get("rain_sensors", [])
        if rain_sensors:
            schema[vol.Optional("rain_sensors", default=rain_sensors)] = EntitySelector(
                EntitySelectorConfig(domain="sensor", multiple=True)
            )
        else:
            schema[vol.Optional("rain_sensors")] = EntitySelector(
                EntitySelectorConfig(domain="sensor", multiple=True)
            )

        rain_binary = weather.get("rain_binary")
        if rain_binary:
            schema[vol.Optional("rain_binary", default=rain_binary)] = EntitySelector(
                EntitySelectorConfig(domain="binary_sensor")
            )
        else:
            schema[vol.Optional("rain_binary")] = EntitySelector(
                EntitySelectorConfig(domain="binary_sensor")
            )

        forecast = weather.get("forecast_entity")
        if forecast:
            schema[vol.Optional("forecast_entity", default=forecast)] = EntitySelector(
                EntitySelectorConfig(domain="weather")
            )
        else:
            schema[vol.Optional("forecast_entity")] = EntitySelector(
                EntitySelectorConfig(domain="weather")
            )

        schema[vol.Required("forecast_hours", default=weather.get("forecast_hours", DEFAULT_FORECAST_HOURS))] = NumberSelector(
            NumberSelectorConfig(min=1, max=168, step=1, unit_of_measurement="h", mode=NumberSelectorMode.BOX)
        )
        schema[vol.Required("rain_threshold", default=weather.get("rain_threshold", DEFAULT_RAIN_THRESHOLD))] = NumberSelector(
            NumberSelectorConfig(min=0.1, max=50.0, step=0.1, unit_of_measurement="mm/h", mode=NumberSelectorMode.BOX)
        )
        schema[vol.Required("forecast_rain_threshold", default=weather.get("forecast_rain_threshold", DEFAULT_FORECAST_RAIN_THRESHOLD))] = NumberSelector(
            NumberSelectorConfig(min=0.1, max=100.0, step=0.1, unit_of_measurement="mm", mode=NumberSelectorMode.BOX)
        )

        return self.async_show_form(
            step_id="weather",
            data_schema=vol.Schema(schema),
        )

    # ── tank ──

    async def async_step_tank(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Tank settings form."""
        tank = self._options.get("tank") or {}
        is_enabled = self._options.get("tank") is not None

        if user_input is not None:
            if not user_input.get("enabled", False):
                self._options["tank"] = None
            else:
                self._options["tank"] = {
                    "level_sensor": user_input["level_sensor"],
                    "pump_switch": user_input.get("pump_switch"),
                    "pump_on_above": user_input.get("pump_on_above", DEFAULT_PUMP_ON_ABOVE),
                    "pump_off_below": user_input.get("pump_off_below", DEFAULT_PUMP_OFF_BELOW),
                }
            return self._save()

        schema: dict = {
            vol.Required("enabled", default=is_enabled): BooleanSelector(),
        }

        level = tank.get("level_sensor")
        if level:
            schema[vol.Optional("level_sensor", default=level)] = EntitySelector(
                EntitySelectorConfig(domain="sensor")
            )
        else:
            schema[vol.Optional("level_sensor")] = EntitySelector(
                EntitySelectorConfig(domain="sensor")
            )

        pump = tank.get("pump_switch")
        if pump:
            schema[vol.Optional("pump_switch", default=pump)] = EntitySelector(
                EntitySelectorConfig(domain="switch")
            )
        else:
            schema[vol.Optional("pump_switch")] = EntitySelector(
                EntitySelectorConfig(domain="switch")
            )

        schema[vol.Required("pump_on_above", default=tank.get("pump_on_above", DEFAULT_PUMP_ON_ABOVE))] = NumberSelector(
            NumberSelectorConfig(min=5, max=100, step=1, unit_of_measurement="%", mode=NumberSelectorMode.BOX)
        )
        schema[vol.Required("pump_off_below", default=tank.get("pump_off_below", DEFAULT_PUMP_OFF_BELOW))] = NumberSelector(
            NumberSelectorConfig(min=1, max=100, step=1, unit_of_measurement="%", mode=NumberSelectorMode.BOX)
        )

        return self.async_show_form(
            step_id="tank",
            data_schema=vol.Schema(schema),
        )

    # ── antifreeze: sub-menu ──

    async def async_step_antifreeze(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Antifreeze sub-menu or enable."""
        af = self._options.get("antifreeze")
        if af is None:
            return await self.async_step_antifreeze_enable()

        menu_options = ["antifreeze_settings", "add_tier", "antifreeze_disable"]
        if af.get("tiers"):
            menu_options.insert(2, "remove_tier")
        return self.async_show_menu(
            step_id="antifreeze",
            menu_options=menu_options,
        )

    async def async_step_antifreeze_enable(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Enable antifreeze with default settings."""
        if user_input is not None:
            self._options["antifreeze"] = {
                "flush_duration": DEFAULT_FLUSH_DURATION,
                "tiers": [],
                "hibernation_below": DEFAULT_HIBERNATION_BELOW,
                "recovery_above": DEFAULT_RECOVERY_ABOVE,
            }
            return self._save()

        return self.async_show_form(
            step_id="antifreeze_enable",
            data_schema=vol.Schema({}),
        )

    async def async_step_antifreeze_disable(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Disable antifreeze."""
        if user_input is not None:
            self._options["antifreeze"] = None
            return self._save()

        return self.async_show_form(
            step_id="antifreeze_disable",
            data_schema=vol.Schema({}),
        )

    async def async_step_antifreeze_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit antifreeze settings."""
        af = self._options.get("antifreeze", {})

        if user_input is not None:
            af["flush_duration"] = int(user_input["flush_duration"])
            af["hibernation_below"] = user_input["hibernation_below"]
            af["recovery_above"] = user_input["recovery_above"]
            self._options["antifreeze"] = af
            return self._save()

        return self.async_show_form(
            step_id="antifreeze_settings",
            data_schema=vol.Schema(
                {
                    vol.Required("flush_duration", default=af.get("flush_duration", DEFAULT_FLUSH_DURATION)): NumberSelector(
                        NumberSelectorConfig(min=5, max=120, step=1, unit_of_measurement="s", mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required("hibernation_below", default=af.get("hibernation_below", DEFAULT_HIBERNATION_BELOW)): NumberSelector(
                        NumberSelectorConfig(min=-30, max=5, step=0.5, unit_of_measurement="\u00b0C", mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required("recovery_above", default=af.get("recovery_above", DEFAULT_RECOVERY_ABOVE)): NumberSelector(
                        NumberSelectorConfig(min=-10, max=20, step=0.5, unit_of_measurement="\u00b0C", mode=NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    async def async_step_add_tier(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Add antifreeze tier."""
        af = self._options.get("antifreeze", {})

        if user_input is not None:
            tiers = list(af.get("tiers", []))
            tiers.append({
                "temp_max": user_input["temp_max"],
                "interval": int(user_input["interval"]),
            })
            tiers.sort(key=lambda t: t["temp_max"])
            af["tiers"] = tiers
            self._options["antifreeze"] = af
            return self._save()

        return self.async_show_form(
            step_id="add_tier",
            data_schema=vol.Schema(
                {
                    vol.Required("temp_max"): NumberSelector(
                        NumberSelectorConfig(min=-20, max=10, step=0.5, unit_of_measurement="\u00b0C", mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required("interval"): NumberSelector(
                        NumberSelectorConfig(min=5, max=360, step=5, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
                    ),
                }
            ),
        )

    async def async_step_remove_tier(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Remove antifreeze tier."""
        af = self._options.get("antifreeze", {})
        tiers = af.get("tiers", [])
        if not tiers:
            return await self.async_step_antifreeze()

        if user_input is not None:
            idx = int(user_input["tier"])
            tiers = [t for i, t in enumerate(tiers) if i != idx]
            af["tiers"] = tiers
            self._options["antifreeze"] = af
            return self._save()

        return self.async_show_form(
            step_id="remove_tier",
            data_schema=vol.Schema(
                {
                    vol.Required("tier"): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                SelectOptionDict(
                                    value=str(i),
                                    label=f"\u2264 {t['temp_max']}\u00b0C \u2192 every {t['interval']} min",
                                )
                                for i, t in enumerate(tiers)
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    # ── ET settings ──

    async def async_step_et_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Evapotranspiration settings."""
        et = self._options.get("et", {})

        if user_input is not None:
            self._options["et"] = {
                "enabled": user_input.get("enabled", True),
                "bucket_max": user_input.get("bucket_max", DEFAULT_BUCKET_MAX),
                "moisture_threshold": int(user_input.get("moisture_threshold", DEFAULT_MOISTURE_THRESHOLD)),
            }
            return self._save()

        return self.async_show_form(
            step_id="et_settings",
            data_schema=vol.Schema(
                {
                    vol.Required("enabled", default=et.get("enabled", True)): BooleanSelector(),
                    vol.Required("bucket_max", default=et.get("bucket_max", DEFAULT_BUCKET_MAX)): NumberSelector(
                        NumberSelectorConfig(min=5, max=100, step=0.5, unit_of_measurement="mm", mode=NumberSelectorMode.BOX)
                    ),
                    vol.Required("moisture_threshold", default=et.get("moisture_threshold", DEFAULT_MOISTURE_THRESHOLD)): NumberSelector(
                        NumberSelectorConfig(min=10, max=90, step=1, unit_of_measurement="%", mode=NumberSelectorMode.SLIDER)
                    ),
                }
            ),
        )

    # ── sequencer ──

    async def async_step_sequencer(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Sequencer settings."""
        seq = self._options.get("sequencer", {})

        if user_input is not None:
            self._options["sequencer"] = {
                "inter_zone_delay": int(user_input["inter_zone_delay"]),
            }
            return self._save()

        return self.async_show_form(
            step_id="sequencer",
            data_schema=vol.Schema(
                {
                    vol.Required("inter_zone_delay", default=seq.get("inter_zone_delay", DEFAULT_INTER_ZONE_DELAY)): NumberSelector(
                        NumberSelectorConfig(min=0, max=300, step=5, unit_of_measurement="s", mode=NumberSelectorMode.SLIDER)
                    ),
                }
            ),
        )
