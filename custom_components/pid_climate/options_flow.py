from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector

from .const import (
    DOMAIN,

    # PID / Climate params
    CONF_MIN_TEMPERATURE,
    CONF_MAX_TEMPERATURE,
    CONF_TEMPERATURE_STEP,
    CONF_PWM_PERIOD,

    DEFAULT_MIN_TEMPERATURE,
    DEFAULT_MAX_TEMPERATURE,
    DEFAULT_TEMPERATURE_STEP,
    DEFAULT_PWM_PERIOD,

    # HVAC
    CONF_HVAC_MODES,
    HVAC_MODE_LABELS,
    HVAC_MODE_DEFAULT_TEMPERATURES,
    HVAC_MODE_TEMPERATURE_KEYS,
)


class PIDClimateOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for PID Climate integration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    def _get_option_value(self, key: str, default: Any) -> Any:
        value = self.entry.options.get(key)
        if value is None:
            value = self.entry.data.get(key, default)
        return default if value is None else value

    def _apply_flat_hvac_mode_temperatures(
        self,
        base: dict[int, float],
        source: dict[str, Any] | None,
    ) -> dict[int, float]:
        if not isinstance(source, dict):
            return base

        for mode_id, key in HVAC_MODE_TEMPERATURE_KEYS.items():
            if key not in source:
                continue
            try:
                base[mode_id] = float(source[key])
            except (TypeError, ValueError):
                continue

        return base

    def _merge_hvac_mode_temperatures(
        self,
        base: dict[int, float],
        raw: dict[Any, Any] | None,
    ) -> dict[int, float]:
        if not isinstance(raw, dict):
            return base

        for key, value in raw.items():
            try:
                mode_id = int(key)
            except (TypeError, ValueError):
                continue
            if mode_id not in base:
                continue
            try:
                base[mode_id] = float(value)
            except (TypeError, ValueError):
                continue

        return base

    def _build_hvac_mode_defaults(self) -> dict[int, float]:
        defaults = dict(HVAC_MODE_DEFAULT_TEMPERATURES)
        defaults = self._apply_flat_hvac_mode_temperatures(defaults, self.entry.data)
        defaults = self._merge_hvac_mode_temperatures(defaults, self.entry.data.get(CONF_HVAC_MODES))
        defaults = self._apply_flat_hvac_mode_temperatures(defaults, self.entry.options)
        defaults = self._merge_hvac_mode_temperatures(defaults, self.entry.options.get(CONF_HVAC_MODES))
        return defaults

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # ─────────────────────────────────────────────
        # HVAC mode temperature sliders
        # ─────────────────────────────────────────────
        hvac_mode_fields: dict[Any, Any] = {}

        current_hvac_modes = self._build_hvac_mode_defaults()

        for mode_id in HVAC_MODE_LABELS:
            key = HVAC_MODE_TEMPERATURE_KEYS[mode_id]
            hvac_mode_fields[
                vol.Optional(
                    key,
                    default=current_hvac_modes[mode_id],
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

        schema_data = {
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
                    CONF_PWM_PERIOD,
                    default=self._get_option_value(CONF_PWM_PERIOD, DEFAULT_PWM_PERIOD),
                ): vol.Coerce(int),

                # HVAC modes → target temperatures
            }

        schema_data.update(hvac_mode_fields)
        schema = vol.Schema(schema_data)

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
