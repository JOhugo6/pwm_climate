"""Climate platform for PID Climate integration."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Mapping
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVACMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
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

MIN_VALID_TEMPERATURE = -50.0
MAX_VALID_TEMPERATURE = 150.0


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


def _merge_hvac_mode_temperatures(
    base: dict[int, float],
    raw: Mapping[Any, Any] | None,
) -> dict[int, float]:
    if not raw:
        return base

    for key, value in raw.items():
        try:
            mode = int(key)
        except (TypeError, ValueError):
            continue

        if mode not in base:
            continue

        try:
            base[mode] = float(value)
        except (TypeError, ValueError):
            continue

    return base


def _resolve_hvac_mode_temperatures(entry: ConfigEntry) -> dict[int, float]:
    temperatures = dict(HVAC_MODE_DEFAULT_TEMPERATURES)
    temperatures = _merge_hvac_mode_temperatures(temperatures, entry.data.get(CONF_HVAC_MODES))
    temperatures = _merge_hvac_mode_temperatures(
        temperatures,
        entry.options.get(CONF_HVAC_MODES),
    )
    return temperatures


def _extract_temperature_value(state: State | None) -> tuple[float | None, str | None]:
    if state is None:
        return None, "missing"

    raw = state.state
    if raw is None:
        return None, "missing"

    value = str(raw).strip()
    if not value:
        return None, "missing"

    lowered = value.lower()
    if lowered in (STATE_UNKNOWN, STATE_UNAVAILABLE):
        return None, "invalid_state"

    try:
        temperature = float(value)
    except ValueError:
        return None, "non_numeric"

    if not math.isfinite(temperature):
        return None, "out_of_range"

    if temperature < MIN_VALID_TEMPERATURE or temperature > MAX_VALID_TEMPERATURE:
        return None, "out_of_range"

    return temperature, None


def _parse_temperature_state(state: State | None) -> float | None:
    temperature, _ = _extract_temperature_value(state)
    return temperature


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

        self._temperature_entity_id: str = entry.data[CONF_TEMPERATURE_ENTITY]
        self._output_entity_id: str = entry.data[CONF_OUTPUT_ENTITY]
        self._humidity_sensor_entity_id: str | None = entry.data.get(CONF_HUMIDITY_ENTITY)

        self._knx_mode_temperatures = _resolve_hvac_mode_temperatures(entry)

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

        self._unsub_temperature_listener: Callable[[], None] | None = None
        self._unsub_entry_update_listener: Callable[[], None] | None = None
        self._last_output_value: float | None = None
        self._is_removing = False

        _LOGGER.debug(
            "PIDClimate init name=%s temp_sensor=%s output=%s pwm_period_min=%s",
            self._attr_name,
            self._temperature_entity_id,
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
            return self._knx_mode_temperatures.get(0, HVAC_MODE_DEFAULT_TEMPERATURES[0])
        if hvac_mode == HVACMode.HEAT:
            return self._knx_mode_temperatures.get(1, HVAC_MODE_DEFAULT_TEMPERATURES[1])
        return self._knx_mode_temperatures.get(1, HVAC_MODE_DEFAULT_TEMPERATURES[1])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "temperature_entity": self._temperature_entity_id,
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
    def _async_temperature_changed(self, event: Event) -> None:
        if self._is_removing:
            return

        old_state: State | None = event.data.get("old_state")
        new_state: State | None = event.data["new_state"]
        if old_state is not None and new_state is not None and old_state.state == new_state.state:
            return

        temperature, error = _extract_temperature_value(new_state)
        if temperature is None:
            if error == "non_numeric":
                _LOGGER.warning(
                    "Non-numeric temperature state for %s: %s",
                    self._temperature_entity_id,
                    new_state.state if new_state is not None else None,
                )
            else:
                _LOGGER.debug(
                    "Ignoring invalid temperature state for %s: %s",
                    self._temperature_entity_id,
                    new_state.state if new_state is not None else None,
                )
            return

        self._attr_current_temperature = temperature
        _LOGGER.debug(
            "Temperature update for %s from %s: %s",
            self.entity_id,
            self._temperature_entity_id,
            temperature,
        )
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
        self._async_sync_current_temperature_from_state(self.hass.states.get(self._temperature_entity_id))
        self._async_subscribe_temperature_listener()
        self.async_on_remove(self._async_unsubscribe_temperature_listener)

        self._unsub_entry_update_listener = self._entry.add_update_listener(
            self._async_config_entry_updated
        )

        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        self._is_removing = True
        self._async_unsubscribe_temperature_listener()

        if self._unsub_entry_update_listener is not None:
            self._unsub_entry_update_listener()
            self._unsub_entry_update_listener = None

    def _async_sync_current_temperature_from_state(self, state: State | None) -> None:
        temperature = _parse_temperature_state(state)
        if temperature is None:
            return

        self._attr_current_temperature = temperature

    @callback
    def _async_unsubscribe_temperature_listener(self) -> None:
        if self._unsub_temperature_listener is None:
            return

        self._unsub_temperature_listener()
        self._unsub_temperature_listener = None
        _LOGGER.debug("Unregistered temperature listener for %s", self.entity_id)

    @callback
    def _async_subscribe_temperature_listener(self) -> None:
        if self._is_removing:
            return

        self._async_unsubscribe_temperature_listener()

        if not self._temperature_entity_id:
            _LOGGER.debug(
                "No temperature entity configured for %s; listener not registered",
                self.entity_id,
            )
            return

        self._unsub_temperature_listener = async_track_state_change_event(
            self.hass,
            [self._temperature_entity_id],
            self._async_temperature_changed,
        )
        _LOGGER.info(
            "Registered temperature listener for %s (%s)",
            self.entity_id,
            self._temperature_entity_id,
        )

    async def _async_config_entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        if self._is_removing:
            return

        temperature_entity_id = entry.data.get(CONF_TEMPERATURE_ENTITY)

        if isinstance(temperature_entity_id, str) and temperature_entity_id:
            if temperature_entity_id != self._temperature_entity_id:
                _LOGGER.debug(
                    "Updating temperature sensor for %s: %s -> %s",
                    self.entity_id,
                    self._temperature_entity_id,
                    temperature_entity_id,
                )
                self._temperature_entity_id = temperature_entity_id
                self._async_sync_current_temperature_from_state(
                    hass.states.get(self._temperature_entity_id)
                )
                self._async_subscribe_temperature_listener()

        self._knx_mode_temperatures = _resolve_hvac_mode_temperatures(entry)
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
        if self._attr_hvac_mode not in self._attr_hvac_modes:
            self._attr_hvac_mode = HVACMode.OFF if HVACMode.OFF in self._attr_hvac_modes else self._attr_hvac_modes[0]

        self.async_write_ha_state()

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
