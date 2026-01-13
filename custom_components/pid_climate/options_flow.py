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
)


class PIDClimateOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for PID Climate integration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # ─────────────────────────────────────────────
        # HVAC mode temperature sliders
        # ─────────────────────────────────────────────
        hvac_mode_schema: dict[Any, Any] = {}

        current_hvac_modes = self.entry.options.get(
            CONF_HVAC_MODES,
            HVAC_MODE_DEFAULT_TEMPERATURES,
        )

        for mode_id, label in HVAC_MODE_LABELS.items():
            hvac_mode_schema[
                vol.Optional(
                    str(mode_id),
                    default=current_hvac_modes.get(
                        mode_id,
                        HVAC_MODE_DEFAULT_TEMPERATURES[mode_id],
                    ),
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

        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_MIN_TEMPERATURE,
                    default=self.entry.options.get(
                        CONF_MIN_TEMPERATURE,
                        DEFAULT_MIN_TEMPERATURE,
                    ),
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
                    default=self.entry.options.get(
                        CONF_MAX_TEMPERATURE,
                        DEFAULT_MAX_TEMPERATURE,
                    ),
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
                    default=self.entry.options.get(
                        CONF_TEMPERATURE_STEP,
                        DEFAULT_TEMPERATURE_STEP,
                    ),
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
                    default=self.entry.options.get(
                        CONF_PWM_PERIOD,
                        DEFAULT_PWM_PERIOD,
                    ),
                ): vol.Coerce(int),

                # HVAC modes → target temperatures
                vol.Optional(
                    CONF_HVAC_MODES,
                    default=current_hvac_modes,
                ): vol.Schema(hvac_mode_schema),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=schema,
        )
