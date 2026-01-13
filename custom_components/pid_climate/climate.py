"""Climate platform for PID Climate integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CONF_HUMIDITY_ENTITY,
    CONF_HVAC_MODES,
    CONF_MAX_TEMPERATURE,
    CONF_MIN_TEMPERATURE,
    CONF_NAME,
    CONF_OUTPUT_ENTITY,
    CONF_PWM_PERIOD,
    CONF_TEMPERATURE_ENTITY,
    CONF_TEMPERATURE_STEP,
    DEFAULT_MAX_TEMPERATURE,
    DEFAULT_MIN_TEMPERATURE,
    DEFAULT_PWM_PERIOD,
    DEFAULT_TEMPERATURE_STEP,
    DOMAIN,
    HVAC_MODE_DEFAULT_TEMPERATURES,
)

_LOGGER = logging.getLogger(DOMAIN)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([PIDClimate(hass, entry)])


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_knx_mode_temperatures(raw: Mapping[Any, Any]) -> dict[int, float]:
    normalized: dict[int, float] = {}
    for key, value in raw.items():
        try:
            normalized[int(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return normalized


class PIDClimate(ClimateEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    # KNX DPT 20.102 -> HA HVACMode (HA has fewer modes than KNX).
    _knx_to_ha_hvac_mode: dict[int, HVACMode] = {
        0: HVACMode.AUTO,  # Auto
        1: HVACMode.HEAT,  # Comfort
        2: HVACMode.HEAT,  # Standby
        3: HVACMode.HEAT,  # Economy
        4: HVACMode.HEAT,  # Building protection
    }

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry

        self._attr_unique_id = entry.entry_id
        self._attr_name = entry.data.get(CONF_NAME, entry.title)

        self._temperature_sensor_entity_id: str = entry.data[CONF_TEMPERATURE_ENTITY]
        self._output_entity_id: str = entry.data[CONF_OUTPUT_ENTITY]
        self._humidity_sensor_entity_id: str | None = entry.data.get(CONF_HUMIDITY_ENTITY)

        self._knx_mode_temperatures = _normalize_knx_mode_temperatures(
            entry.options.get(
                CONF_HVAC_MODES,
                entry.data.get(CONF_HVAC_MODES, HVAC_MODE_DEFAULT_TEMPERATURES),
            )
        )

        self._attr_min_temp = _coerce_float(
            entry.options.get(CONF_MIN_TEMPERATURE, entry.data.get(CONF_MIN_TEMPERATURE)),
            DEFAULT_MIN_TEMPERATURE,
        )
        self._attr_max_temp = _coerce_float(
            entry.options.get(CONF_MAX_TEMPERATURE, entry.data.get(CONF_MAX_TEMPERATURE)),
            DEFAULT_MAX_TEMPERATURE,
        )
        self._attr_target_temperature_step = _coerce_float(
            entry.options.get(CONF_TEMPERATURE_STEP, entry.data.get(CONF_TEMPERATURE_STEP)),
            DEFAULT_TEMPERATURE_STEP,
        )
        self._pwm_period_minutes = _coerce_int(
            entry.options.get(CONF_PWM_PERIOD, entry.data.get(CONF_PWM_PERIOD)),
            DEFAULT_PWM_PERIOD,
        )

        self._attr_hvac_modes = self._compute_hvac_modes()
        self._attr_hvac_mode = HVACMode.HEAT if HVACMode.HEAT in self._attr_hvac_modes else HVACMode.AUTO
        self._last_hvac_mode = self._attr_hvac_mode
        self._knx_hvac_mode: int | None = 1 if self._attr_hvac_mode == HVACMode.HEAT else 0

        self._attr_current_temperature: float | None = None
        self._attr_target_temperature: float = self._default_target_temperature(self._attr_hvac_mode)

        self._unsub_temp = None
        self._last_output_value: float | None = None

        _LOGGER.debug(
            "PIDClimate init name=%s temp_sensor=%s output=%s pwm_period_min=%s",
            self._attr_name,
            self._temperature_sensor_entity_id,
            self._output_entity_id,
            self._pwm_period_minutes,
        )

    def _compute_hvac_modes(self) -> list[HVACMode]:
        modes: list[HVACMode] = [HVACMode.OFF]

        if 0 in self._knx_mode_temperatures:
            modes.append(HVACMode.AUTO)

        if any(mode in self._knx_mode_temperatures for mode in (1, 2, 3, 4)):
            modes.append(HVACMode.HEAT)

        if HVACMode.HEAT not in modes:
            modes.append(HVACMode.HEAT)

        return modes

    def _default_target_temperature(self, hvac_mode: HVACMode) -> float:
        if hvac_mode == HVACMode.AUTO:
            return self._knx_mode_temperatures.get(0, 22.0)
        if hvac_mode == HVACMode.HEAT:
            return self._knx_mode_temperatures.get(1, 22.0)
        return self._knx_mode_temperatures.get(1, 22.0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "temperature_entity": self._temperature_sensor_entity_id,
            "output_entity": self._output_entity_id,
            "humidity_entity": self._humidity_sensor_entity_id,
            "pwm_period_minutes": self._pwm_period_minutes,
            "knx_hvac_mode": self._knx_hvac_mode,
        }

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self._attr_target_temperature = float(temperature)
        _LOGGER.info("PID Climate setpoint changed to %.1f °C", self._attr_target_temperature)

        await self._async_update_output_hook()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        self._attr_hvac_mode = hvac_mode

        if hvac_mode != HVACMode.OFF:
            self._last_hvac_mode = hvac_mode
            self._attr_target_temperature = self._default_target_temperature(hvac_mode)
            self._knx_hvac_mode = 0 if hvac_mode == HVACMode.AUTO else 1
        else:
            self._knx_hvac_mode = None

        _LOGGER.info(
            "PID Climate HVAC mode changed to %s (target=%.1f °C)",
            hvac_mode,
            self._attr_target_temperature,
        )

        await self._async_update_output_hook()
        self.async_write_ha_state()

    @callback
    def _handle_temperature_change(self, event: Event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None or new_state.state in (None, "unknown", "unavailable"):
            return

        try:
            self._attr_current_temperature = float(new_state.state)
        except ValueError:
            _LOGGER.debug("Ignoring non-numeric temperature state: %s", new_state.state)
            return

        _LOGGER.info("PID Climate temperature updated to %.1f °C", self._attr_current_temperature)
        self.hass.async_create_task(self._async_update_output_hook())
        self.async_write_ha_state()

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        if self._attr_hvac_mode != HVACMode.OFF:
            return

        target_mode = self._last_hvac_mode
        if target_mode == HVACMode.OFF or target_mode not in self._attr_hvac_modes:
            target_mode = HVACMode.HEAT if HVACMode.HEAT in self._attr_hvac_modes else HVACMode.AUTO

        await self.async_set_hvac_mode(target_mode)

    async def async_added_to_hass(self) -> None:
        self._async_sync_current_temperature_from_state(
            self.hass.states.get(self._temperature_sensor_entity_id)
        )

        self._unsub_temp = async_track_state_change_event(
            self.hass,
            [self._temperature_sensor_entity_id],
            self._handle_temperature_change,
        )

        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        if self._unsub_temp is not None:
            self._unsub_temp()
            self._unsub_temp = None

    def _async_sync_current_temperature_from_state(self, state: State | None) -> None:
        if state is None or state.state in (None, "unknown", "unavailable"):
            return
        try:
            self._attr_current_temperature = float(state.state)
        except ValueError:
            _LOGGER.debug("Ignoring non-numeric temperature state: %s", state.state)

    async def _async_update_output_hook(self) -> None:
        if self._attr_hvac_mode == HVACMode.OFF:
            await self._async_set_output_to_min()
            return

        _LOGGER.debug(
            "Output hook: hvac_mode=%s current=%s target=%s output_entity=%s pwm_period_min=%s",
            self._attr_hvac_mode,
            self._attr_current_temperature,
            self._attr_target_temperature,
            self._output_entity_id,
            self._pwm_period_minutes,
        )

    async def _async_set_output_to_min(self) -> None:
        output_state = self.hass.states.get(self._output_entity_id)
        output_min = _coerce_float(output_state.attributes.get("min") if output_state else None, 0.0)
        await self._async_set_output_value(output_min)

    async def _async_set_output_value(self, value: float) -> None:
        if self._last_output_value == value:
            return

        try:
            await self.hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": self._output_entity_id, "value": value},
                blocking=True,
            )
        except Exception:
            _LOGGER.exception("Failed setting %s to %s", self._output_entity_id, value)
            return

        self._last_output_value = value
