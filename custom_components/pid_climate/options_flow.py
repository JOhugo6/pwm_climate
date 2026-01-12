from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    DOMAIN,

    # obecné PID / klima parametry
    CONF_MIN_TEMPERATURE,
    CONF_MAX_TEMPERATURE,
    CONF_TEMPERATURE_STEP,
    CONF_PWM_PERIOD,

    DEFAULT_MIN_TEMPERATURE,
    DEFAULT_MAX_TEMPERATURE,
    DEFAULT_TEMPERATURE_STEP,
    DEFAULT_PWM_PERIOD,

    # HVAC
    CONF_HVAC_MODE_TEMPERATURES,
    HVAC_MODES,
    DEFAULT_HVAC_MODE_TEMPERATURES,
)


class PIDClimateOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for PID Climate integration."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.entry = entry

    async def async_step_init(self, user_input: dict | None = None):
        """Main options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.entry.options
        data = self.entry.data

        # --- obecné hodnoty ---
        min_temp = options.get(
            CONF_MIN_TEMPERATURE,
            data.get(CONF_MIN_TEMPERATURE, DEFAULT_MIN_TEMPERATURE),
        )
        max_temp = options.get(
            CONF_MAX_TEMPERATURE,
            data.get(CONF_MAX_TEMPERATURE, DEFAULT_MAX_TEMPERATURE),
        )
        temp_step = options.get(
            CONF_TEMPERATURE_STEP,
            data.get(CONF_TEMPERATURE_STEP, DEFAULT_TEMPERATURE_STEP),
        )
        pwm_period = options.get(
            CONF_PWM_PERIOD,
            data.get(CONF_PWM_PERIOD, DEFAULT_PWM_PERIOD),
        )

        # --- HVAC teploty ---
        hvac_mode_temps = options.get(
            CONF_HVAC_MODE_TEMPERATURES,
            data.get(CONF_HVAC_MODE_TEMPERATURES, DEFAULT_HVAC_MODE_TEMPERATURES),
        )

        schema: dict = {
            vol.Optional(
                CONF_MIN_TEMPERATURE,
                default=min_temp,
            ): vol.Coerce(float),

            vol.Optional(
                CONF_MAX_TEMPERATURE,
                default=max_temp,
            ): vol.Coerce(float),

            vol.Optional(
                CONF_TEMPERATURE_STEP,
                default=temp_step,
            ): vol.Coerce(float),

            vol.Optional(
                CONF_PWM_PERIOD,
                default=pwm_period,
            ): vol.Coerce(int),
        }

        # --- HVAC módy (DPT 20.102 kompatibilní) ---
        for mode in HVAC_MODES:
            schema[
                vol.Optional(
                    f"{CONF_HVAC_MODE_TEMPERATURES}.{mode}",
                    default=hvac_mode_temps.get(
                        mode,
                        DEFAULT_HVAC_MODE_TEMPERATURES[mode],
                    ),
                )
            ] = vol.Coerce(float)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )


@callback
def async_get_options_flow(
    entry: config_entries.ConfigEntry,
) -> PIDClimateOptionsFlowHandler:
    """Return the options flow handler."""
    return PIDClimateOptionsFlowHandler(entry)
