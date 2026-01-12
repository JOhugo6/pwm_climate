from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector

from .const import (
    DOMAIN,

    CONF_TEMPERATURE_ENTITY,
    CONF_OUTPUT_ENTITY,
    CONF_HUMIDITY_ENTITY,

    CONF_MIN_TEMPERATURE,
    CONF_MAX_TEMPERATURE,
    CONF_TEMPERATURE_STEP,
    CONF_PWM_PERIOD,

    CONF_HVAC_MODES,

    DEFAULT_MIN_TEMPERATURE,
    DEFAULT_MAX_TEMPERATURE,
    DEFAULT_TEMPERATURE_STEP,
    DEFAULT_PWM_PERIOD,


    HVAC_MODE_LABELS,
    HVAC_MODE_DEFAULT_TEMPERATURES,
)


class PIDClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for PID Climate."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Initial configuration step."""

        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        # ─────────────────────────────────────────────
        # HVAC mode temperature fields
        # ─────────────────────────────────────────────
        hvac_mode_fields: dict[Any, Any] = {}

        for mode_id, label in HVAC_MODE_LABELS.items():
            hvac_mode_fields[
                vol.Required(
                    str(mode_id),
                    default=HVAC_MODE_DEFAULT_TEMPERATURES[mode_id],
                )
            ] = vol.Coerce(float)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): str,

                vol.Required(CONF_TEMPERATURE_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
                        )
                    ),

                vol.Required(CONF_OUTPUT_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="number",
                        )
                    ),

                vol.Optional(CONF_HUMIDITY_ENTITY):
                    selector.EntitySelector(
                        selector.EntitySelectorConfig(
                            domain="sensor",
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

                vol.Optional(
                    CONF_PWM_PERIOD,
                    default=DEFAULT_PWM_PERIOD,
                ): vol.Coerce(int),

                # ─────────────────────────────────────
                # HVAC modes → target temperatures
                # ─────────────────────────────────────
                vol.Required(CONF_HVAC_MODES): vol.Schema(hvac_mode_fields),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )
