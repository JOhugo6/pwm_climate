from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,

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

    def _build_preset_defaults(self) -> dict[int, float]:
        # Build the active preset map by overlaying entry data and options.
        return resolve_preset_temperatures(self.entry.data, self.entry.options)

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        if user_input is not None:
            # Save options as-is; validation is handled by selectors.
            return self.async_create_entry(title="", data=user_input)

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
        )
