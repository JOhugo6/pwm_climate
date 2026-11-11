from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import selector

from .const import (
    CONF_TEMPERATURE_ENTITY,
    CONF_HUMIDITY_ENTITY,
    CONF_HVAC_MODES,

    # PWM / climate params
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

    CONF_DEFAULT_PRESET,
    DEFAULT_PRESET,
    PRESET_LABELS,
    PRESET_TEMPERATURE_KEYS,
    PRESET_NAMES,
)
from .preset_helpers import resolve_preset_temperatures
from .source_helpers import measurement_entities


class PWMClimateOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for PWM Climate Controller integration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        # Keep the original entry so we can read defaults and current options.
        self.entry = entry

    def _get_option_value(self, key: str, default: Any) -> Any:
        # Prefer options over initial entry data for current defaults.
        value = self.entry.options.get(key)
        if value is None:
            value = self.entry.data.get(key, default)
        return default if value is None else value

    def _get_source_value(self, key: str) -> Any:
        # An explicit None overrides entry.data for a removed optional source.
        return self.entry.options.get(key, self.entry.data.get(key))

    def _build_preset_defaults(self) -> dict[int, float]:
        # Build the active preset map by overlaying entry data and options.
        return resolve_preset_temperatures(self.entry.data, self.entry.options)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        temperature_entities = measurement_entities(self.hass, "temperature", "°C")
        humidity_entities = measurement_entities(self.hass, "humidity", "%")
        # Older setup accepted any sensor for display-only humidity. Keep that
        # effective source editable without accepting new incompatible sources.
        existing_humidity = self._get_source_value(CONF_HUMIDITY_ENTITY)
        if (
            isinstance(existing_humidity, str)
            and existing_humidity.startswith("sensor.")
            and existing_humidity not in humidity_entities
        ):
            registry = er.async_get(self.hass)
            if existing_humidity in registry.entities or self.hass.states.get(existing_humidity) is not None:
                humidity_entities = sorted([*humidity_entities, existing_humidity])
        if user_input is not None:
            if user_input.get(CONF_TEMPERATURE_ENTITY) not in temperature_entities:
                errors[CONF_TEMPERATURE_ENTITY] = "invalid_temperature_entity"
            humidity_entity = user_input.get(CONF_HUMIDITY_ENTITY)
            if humidity_entity not in (None, "") and humidity_entity not in humidity_entities:
                errors[CONF_HUMIDITY_ENTITY] = "invalid_humidity_entity"
            if not errors:
                # Keep options not exposed in this form (including future keys).
                options = {**self.entry.options, **user_input}
                # Legacy nested preset aliases override flat fields at runtime.
                # Keep the representation and unknown keys, updating aliases for
                # sliders submitted by this form so edits take effect.
                nested = options.get(CONF_HVAC_MODES)
                if isinstance(nested, Mapping):
                    nested = dict(nested)
                    label_to_id = {label: preset_id for preset_id, label in PRESET_LABELS.items()}
                    for key in nested:
                        try:
                            preset_id = label_to_id[key] if key in label_to_id else int(key)
                        except (TypeError, ValueError):
                            continue
                        flat_key = PRESET_TEMPERATURE_KEYS.get(preset_id)
                        if flat_key in user_input:
                            nested[key] = user_input[flat_key]
                    options[CONF_HVAC_MODES] = nested
                # An omitted optional field means the user cleared it. Persist the
                # absence explicitly so the original entry.data cannot revive it.
                options[CONF_HUMIDITY_ENTITY] = humidity_entity or None
                return self.async_create_entry(title="", data=options)

        def current_value(key: str) -> Any:
            if user_input is not None:
                return user_input.get(key)
            return self._get_source_value(key)

        # ─────────────────────────────────────────────
        # HVAC mode temperature sliders
        # ─────────────────────────────────────────────
        # Build preset temperature fields for the options form.
        preset_fields: dict[Any, Any] = {}

        # Resolve current preset defaults (entry data + existing options).
        current_presets = self._build_preset_defaults()

        for preset_id in PRESET_LABELS:
            key = PRESET_TEMPERATURE_KEYS[preset_id]
            preset_fields[
                vol.Optional(
                    key,
                    default=current_presets[preset_id],
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

        # General tuning and limit options.
        # Preset sliders are appended below so the form uses one schema.
        schema_data = {
                vol.Required(
                    CONF_TEMPERATURE_ENTITY,
                    description={"suggested_value": current_value(CONF_TEMPERATURE_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", include_entities=temperature_entities,
                    )
                ),
                # Suggested values prefill the UI without re-inserting a deleted
                # field during Voluptuous validation, unlike default=.
                vol.Optional(
                    CONF_HUMIDITY_ENTITY,
                    description={"suggested_value": current_value(CONF_HUMIDITY_ENTITY)},
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", include_entities=humidity_entities,
                    )
                ),
                vol.Optional(
                    CONF_DEFAULT_PRESET,
                    default=self._get_option_value(CONF_DEFAULT_PRESET, DEFAULT_PRESET),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=PRESET_NAMES,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),

                vol.Optional(
                    CONF_MIN_TEMPERATURE,
                    default=self._get_option_value(CONF_MIN_TEMPERATURE, DEFAULT_MIN_TEMPERATURE),
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
                    default=self._get_option_value(CONF_MAX_TEMPERATURE, DEFAULT_MAX_TEMPERATURE),
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
                    default=self._get_option_value(CONF_TEMPERATURE_STEP, DEFAULT_TEMPERATURE_STEP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0.1,
                        max=2.0,
                        step=0.1,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.SLIDER,
                    )
                ),

                vol.Optional(
                    CONF_KP,
                    default=self._get_option_value(CONF_KP, DEFAULT_KP),
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
                    default=self._get_option_value(CONF_PWM_PERIOD, DEFAULT_PWM_PERIOD),
                ): vol.Coerce(int),

                # HVAC modes → target temperatures
            }

        schema_data.update(preset_fields)
        schema = vol.Schema(schema_data)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )
