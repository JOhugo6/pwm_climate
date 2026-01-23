from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    DOMAIN,

    CONF_TEMPERATURE_ENTITY,
    CONF_OUTPUT_ENTITY,
    CONF_HUMIDITY_ENTITY,

    CONF_DEFAULT_PRESET,
    CONF_MIN_TEMPERATURE,
    CONF_MAX_TEMPERATURE,
    CONF_TEMPERATURE_STEP,
    CONF_PWM_PERIOD,
    CONF_KP,

    DEFAULT_MIN_TEMPERATURE,
    DEFAULT_MAX_TEMPERATURE,
    DEFAULT_TEMPERATURE_STEP,
    DEFAULT_PWM_PERIOD,
    DEFAULT_KP,


    DEFAULT_PRESET,
    PRESET_LABELS,
    PRESET_DEFAULT_TEMPERATURES,
    PRESET_TEMPERATURE_KEYS,
    PRESET_NAMES,
)
from .options_flow import PWMClimateOptionsFlowHandler


class PWMClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for PWM Climate Controller."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> PWMClimateOptionsFlowHandler:
        # Hand over to the options flow handler for edits after initial setup.
        return PWMClimateOptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Initial configuration step."""

        # Collect validation errors for the form and reuse them on redisplay.
        errors: dict[str, str] = {}
        # Build the list of eligible temperature sensors for the selector.
        temperature_entities = self._async_get_temperature_entities()

        if user_input is not None:
            # Validate that the selected sensor is really a temperature entity.
            if user_input[CONF_TEMPERATURE_ENTITY] not in temperature_entities:
                errors[CONF_TEMPERATURE_ENTITY] = "invalid_temperature_entity"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        # ─────────────────────────────────────────────
        # HVAC mode temperature fields
        # ─────────────────────────────────────────────
        # Build preset temperature fields dynamically for the form.
        preset_fields: dict[Any, Any] = {}

        for preset_id in PRESET_LABELS:
            key = PRESET_TEMPERATURE_KEYS[preset_id]
            preset_fields[
                vol.Required(
                    key,
                    default=PRESET_DEFAULT_TEMPERATURES[preset_id],
                )
            ] = selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=5,
                    max=40,
                    step=0.5,
                    unit_of_measurement="°C",
                    mode=selector.NumberSelectorMode.SLIDER,
                )
            )

        # Main config fields for entity selection and control parameters.
        # Preset fields are injected below so the full form is built in one schema.
        schema_data = {
                vol.Required(CONF_NAME): str,

                vol.Required(CONF_TEMPERATURE_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                            include_entities=temperature_entities,
                        )
                    ),

                vol.Required(CONF_OUTPUT_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain=[
                                "number",
                                "input_number",
                                "switch",
                                "input_boolean",
                                "light",
                                "climate",
                            ],
                        )
                    ),

                vol.Optional(CONF_HUMIDITY_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                        )
                    ),

                vol.Required(
                    CONF_DEFAULT_PRESET,
                    default=DEFAULT_PRESET,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=PRESET_NAMES,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),

                vol.Optional(
                    CONF_MIN_TEMPERATURE,
                    default=DEFAULT_MIN_TEMPERATURE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=40,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),

                vol.Optional(
                    CONF_MAX_TEMPERATURE,
                    default=DEFAULT_MAX_TEMPERATURE,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=5,
                        max=40,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),

                vol.Optional(
                    CONF_TEMPERATURE_STEP,
                    default=DEFAULT_TEMPERATURE_STEP,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),

                vol.Required(
                    CONF_KP,
                    default=DEFAULT_KP,
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=100,
                        step=0.1,
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),

                vol.Optional(
                    CONF_PWM_PERIOD,
                    default=DEFAULT_PWM_PERIOD,
                ): vol.Coerce(int),

                # ─────────────────────────────────────
                # HVAC modes → target temperatures
                # ─────────────────────────────────────
            }

        schema_data.update(preset_fields)
        schema = vol.Schema(schema_data)

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    def _async_get_temperature_entities(self) -> list[str]:
        # Filter sensor entities by device_class or unit_of_measurement.
        registry = er.async_get(self.hass)
        registry_entries = {
            entry.entity_id: entry
            for entry in registry.entities.values()
            if entry.domain == "sensor"
        }

        # Merge registry entities and runtime states to catch both.
        entities: set[str] = set(registry_entries)
        entities.update(state.entity_id for state in self.hass.states.async_all("sensor"))

        # Keep only entities that look like temperature sensors.
        valid_entities: list[str] = []
        for entity_id in sorted(entities):
            entry = registry_entries.get(entity_id)
            state = self.hass.states.get(entity_id)
            if self._is_temperature_sensor(entry, state):
                valid_entities.append(entity_id)

        return valid_entities

    @staticmethod
    def _is_temperature_sensor(entry: Any | None, state: Any | None) -> bool:
        # Accept device_class temperature or unit of measurement in C.
        device_class = entry.device_class if entry and entry.device_class else None
        unit = None

        if state:
            device_class = state.attributes.get("device_class", device_class)
            unit = state.attributes.get("unit_of_measurement")

        return device_class == SensorDeviceClass.TEMPERATURE or unit == "°C"
