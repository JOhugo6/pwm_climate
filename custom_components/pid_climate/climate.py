"""Climate platform for PID Climate integration."""

from __future__ import annotations

import asyncio
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
    HVAC_MODE_TEMPERATURE_KEYS,
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


def _apply_flat_hvac_mode_temperatures(
    base: dict[int, float],
    source: Mapping[str, Any] | None,
) -> dict[int, float]:
    if not source:
        return base

    for mode_id, key in HVAC_MODE_TEMPERATURE_KEYS.items():
        if key not in source:
            continue
        try:
            base[mode_id] = float(source[key])
        except (TypeError, ValueError):
            continue

    return base


def _resolve_hvac_mode_temperatures(entry: ConfigEntry) -> dict[int, float]:
    temperatures = dict(HVAC_MODE_DEFAULT_TEMPERATURES)
    temperatures = _apply_flat_hvac_mode_temperatures(temperatures, entry.data)
    temperatures = _merge_hvac_mode_temperatures(temperatures, entry.data.get(CONF_HVAC_MODES))
    temperatures = _apply_flat_hvac_mode_temperatures(temperatures, entry.options)
    temperatures = _merge_hvac_mode_temperatures(temperatures, entry.options.get(CONF_HVAC_MODES))
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


def _extract_humidity_value(state: State | None) -> tuple[float | None, str | None]:
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
        humidity = float(value)
    except ValueError:
        return None, "non_numeric"

    if not math.isfinite(humidity):
        return None, "non_numeric"

    return humidity, None


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
        self._attr_current_humidity: float | None = None

        self._unsub_temperature_listener: Callable[[], None] | None = None
        self._unsub_humidity_listener: Callable[[], None] | None = None
        self._unsub_entry_update_listener: Callable[[], None] | None = None
        self._last_output_value: float | None = None
        self._is_removing = False
        self._pwm_task: asyncio.Task | None = None
        self._pwm_lock = asyncio.Lock()
        self._pwm_ratio: float | None = None
        self._pwm_period_seconds: float | None = None
        self._pwm_output_min: float | None = None
        self._pwm_output_max: float | None = None
        self._pwm_output_mode: str | None = None

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
        self.hass.async_create_task(self._async_update_output_hook())

    @callback
    def _async_humidity_changed(self, event: Event) -> None:
        if self._is_removing:
            return

        old_state: State | None = event.data.get("old_state")
        new_state: State | None = event.data["new_state"]
        if old_state is not None and new_state is not None and old_state.state == new_state.state:
            return

        humidity, _error = _extract_humidity_value(new_state)
        if humidity is None:
            _LOGGER.debug(
                "Ignoring invalid humidity state for %s: %s",
                self._humidity_sensor_entity_id,
                new_state.state if new_state is not None else None,
            )
            return

        self._attr_current_humidity = humidity
        _LOGGER.debug(
            "Humidity update for %s from %s: %s",
            self.entity_id,
            self._humidity_sensor_entity_id,
            humidity,
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
        self._async_subscribe_temperature_listener()
        self._async_sync_current_temperature_from_state(
            self.hass.states.get(self._temperature_entity_id),
            log_initial=True,
        )
        self.async_on_remove(self._async_unsubscribe_temperature_listener)

        self._async_subscribe_humidity_listener()
        self._async_sync_current_humidity_from_state(
            self.hass.states.get(self._humidity_sensor_entity_id)
            if self._humidity_sensor_entity_id
            else None,
            log_initial=True,
        )
        self.async_on_remove(self._async_unsubscribe_humidity_listener)

        self._unsub_entry_update_listener = self._entry.add_update_listener(
            self._async_config_entry_updated
        )

        self.async_write_ha_state()
        await self._async_update_output_hook()

    async def async_will_remove_from_hass(self) -> None:
        self._is_removing = True
        self._async_unsubscribe_temperature_listener()
        self._async_unsubscribe_humidity_listener()
        await self._async_stop_pwm_task(reason="remove")

        if self._unsub_entry_update_listener is not None:
            self._unsub_entry_update_listener()
            self._unsub_entry_update_listener = None

    def _async_sync_current_temperature_from_state(
        self,
        state: State | None,
        *,
        log_initial: bool = False,
    ) -> bool:
        temperature, error = _extract_temperature_value(state)
        if temperature is None:
            if log_initial:
                raw_state = state.state if state is not None else None
                if error == "non_numeric":
                    _LOGGER.warning(
                        "Non-numeric temperature state for %s: %s",
                        self._temperature_entity_id,
                        raw_state,
                    )
                else:
                    _LOGGER.debug(
                        "Ignoring invalid temperature state for %s: %s",
                        self._temperature_entity_id,
                        raw_state,
                    )
            return False

        self._attr_current_temperature = temperature
        if log_initial:
            _LOGGER.info(
                "Initial temperature for %s from %s: %s",
                self.entity_id,
                self._temperature_entity_id,
                temperature,
            )
        return True

    def _async_sync_current_humidity_from_state(
        self,
        state: State | None,
        *,
        log_initial: bool = False,
    ) -> bool:
        if not self._humidity_sensor_entity_id:
            return False

        humidity, _error = _extract_humidity_value(state)
        if humidity is None:
            if log_initial:
                raw_state = state.state if state is not None else None
                _LOGGER.debug(
                    "Ignoring invalid humidity state for %s: %s",
                    self._humidity_sensor_entity_id,
                    raw_state,
                )
            return False

        self._attr_current_humidity = humidity
        if log_initial:
            _LOGGER.debug(
                "Initial humidity for %s from %s: %s",
                self.entity_id,
                self._humidity_sensor_entity_id,
                humidity,
            )
        return True

    @callback
    def _async_unsubscribe_temperature_listener(self) -> None:
        if self._unsub_temperature_listener is None:
            return

        self._unsub_temperature_listener()
        self._unsub_temperature_listener = None
        _LOGGER.debug("Unregistered temperature listener for %s", self.entity_id)

    @callback
    def _async_unsubscribe_humidity_listener(self) -> None:
        if self._unsub_humidity_listener is None:
            return

        self._unsub_humidity_listener()
        self._unsub_humidity_listener = None
        _LOGGER.debug("Unregistered humidity listener for %s", self.entity_id)

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

    @callback
    def _async_subscribe_humidity_listener(self) -> None:
        if self._is_removing:
            return

        self._async_unsubscribe_humidity_listener()

        if not self._humidity_sensor_entity_id:
            _LOGGER.debug(
                "No humidity entity configured for %s; listener not registered",
                self.entity_id,
            )
            return

        self._unsub_humidity_listener = async_track_state_change_event(
            self.hass,
            [self._humidity_sensor_entity_id],
            self._async_humidity_changed,
        )
        _LOGGER.debug(
            "Registered humidity listener for %s (%s)",
            self.entity_id,
            self._humidity_sensor_entity_id,
        )

    async def _async_config_entry_updated(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        if self._is_removing:
            return

        temperature_entity_id = entry.data.get(CONF_TEMPERATURE_ENTITY)
        humidity_entity_id = entry.data.get(CONF_HUMIDITY_ENTITY)

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

        if isinstance(humidity_entity_id, str) and humidity_entity_id:
            if humidity_entity_id != self._humidity_sensor_entity_id:
                _LOGGER.debug(
                    "Updating humidity sensor for %s: %s -> %s",
                    self.entity_id,
                    self._humidity_sensor_entity_id,
                    humidity_entity_id,
                )
                self._humidity_sensor_entity_id = humidity_entity_id
                self._async_sync_current_humidity_from_state(
                    hass.states.get(self._humidity_sensor_entity_id)
                )
                self._async_subscribe_humidity_listener()
        elif self._humidity_sensor_entity_id:
            self._humidity_sensor_entity_id = None
            self._attr_current_humidity = None
            self._async_unsubscribe_humidity_listener()

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
        await self._async_update_output_hook()

    async def _async_stop_pwm_task(self, *, reason: str | None = None) -> None:
        if self._pwm_task is None:
            return

        if reason:
            _LOGGER.debug("Stopping PWM for %s (%s)", self.entity_id, reason)
        else:
            _LOGGER.debug("Stopping PWM for %s", self.entity_id)

        self._pwm_task.cancel()
        try:
            await self._pwm_task
        except asyncio.CancelledError:
            pass

        self._pwm_task = None
        self._pwm_ratio = None
        self._pwm_period_seconds = None
        self._pwm_output_min = None
        self._pwm_output_max = None

    async def _async_pwm_loop(
        self,
        output_on: float,
        output_off: float,
        on_seconds: float,
        off_seconds: float,
    ) -> None:
        try:
            while True:
                await self._async_set_output_value(output_on)
                await asyncio.sleep(on_seconds)
                await self._async_set_output_value(output_off)
                await asyncio.sleep(off_seconds)
        except asyncio.CancelledError:
            raise

    async def _async_set_stable_output(self, value: float, mode: str, reason: str) -> None:
        if mode != self._pwm_output_mode:
            if mode == "off":
                _LOGGER.info("PWM output fixed OFF for %s (%s)", self.entity_id, reason)
            elif mode == "on":
                _LOGGER.info("PWM output fixed ON for %s (%s)", self.entity_id, reason)
        self._pwm_output_mode = mode
        await self._async_set_output_value(value)

    async def _async_apply_pwm(
        self,
        *,
        output_min: float,
        output_max: float,
        duty_ratio: float,
    ) -> None:
        period_minutes = max(self._pwm_period_minutes, 1)
        period_seconds = float(period_minutes) * 60.0
        duty_ratio = max(0.0, min(1.0, duty_ratio))

        if self._attr_hvac_mode == HVACMode.OFF or duty_ratio <= 0.0:
            await self._async_stop_pwm_task(reason="off_or_zero")
            await self._async_set_stable_output(output_min, "off", "duty=0%/hvac_off")
            return

        if duty_ratio >= 1.0:
            await self._async_stop_pwm_task(reason="full_duty")
            await self._async_set_stable_output(output_max, "on", "duty=100%")
            return

        restart_pwm = True
        if self._pwm_task is not None:
            same_ratio = self._pwm_ratio is not None and math.isclose(
                self._pwm_ratio,
                duty_ratio,
                rel_tol=0.0,
                abs_tol=1e-6,
            )
            same_period = self._pwm_period_seconds is not None and math.isclose(
                self._pwm_period_seconds,
                period_seconds,
                rel_tol=0.0,
                abs_tol=0.01,
            )
            same_range = self._pwm_output_min == output_min and self._pwm_output_max == output_max
            restart_pwm = not (same_ratio and same_period and same_range)

            if restart_pwm:
                if self._pwm_ratio is not None and not same_ratio:
                    _LOGGER.debug(
                        "PWM ratio change for %s: %.1f%% -> %.1f%%",
                        self.entity_id,
                        self._pwm_ratio * 100.0,
                        duty_ratio * 100.0,
                    )
                await self._async_stop_pwm_task(reason="pwm_update")

        if restart_pwm:
            on_seconds = period_seconds * duty_ratio
            off_seconds = period_seconds - on_seconds
            _LOGGER.debug(
                "Starting PWM for %s (period=%.1fs duty=%.1f%% on=%.1fs off=%.1fs)",
                self.entity_id,
                period_seconds,
                duty_ratio * 100.0,
                on_seconds,
                off_seconds,
            )
            self._pwm_task = self.hass.async_create_task(
                self._async_pwm_loop(output_max, output_min, on_seconds, off_seconds)
            )
            self._pwm_ratio = duty_ratio
            self._pwm_period_seconds = period_seconds
            self._pwm_output_min = output_min
            self._pwm_output_max = output_max
            self._pwm_output_mode = "pwm"

    async def _async_update_output_hook(self) -> None:
        if self._is_removing:
            return

        async with self._pwm_lock:
            await self._async_update_output_internal()

    async def _async_update_output_internal(self) -> None:
        output_state = self.hass.states.get(self._output_entity_id)
        output_min = _coerce_float(output_state.attributes.get("min") if output_state else None, 0.0)
        output_max = _coerce_float(
            output_state.attributes.get("max") if output_state else None,
            output_min,
        )
        output_step = _coerce_float(
            output_state.attributes.get("step") if output_state else None,
            0.0,
        )

        if not math.isfinite(output_min):
            output_min = 0.0
        if not math.isfinite(output_max):
            output_max = output_min
        if not math.isfinite(output_step):
            output_step = 0.0

        output_min = max(output_min, 0.0)
        if output_max < output_min:
            output_max = output_min

        current = self._attr_current_temperature
        target = self._attr_target_temperature

        if self._attr_hvac_mode == HVACMode.OFF:
            await self._async_apply_pwm(output_min=output_min, output_max=output_max, duty_ratio=0.0)
            return

        if current is None:
            _LOGGER.debug(
                "Output hook: missing current temperature for %s; skipping output update",
                self.entity_id,
            )
            return

        if current >= target:
            new_value = output_min
        else:
            delta = target - current
            span = output_max - output_min
            temperature_band = self._attr_max_temp - self._attr_min_temp
            if not math.isfinite(temperature_band) or temperature_band <= 0:
                temperature_band = max(self._attr_target_temperature_step, 1.0)

            proportional = delta / temperature_band
            if proportional < 0:
                proportional = 0.0
            elif proportional > 1:
                proportional = 1.0

            new_value = output_min + (proportional * span)

        if new_value < output_min:
            new_value = output_min
        elif new_value > output_max:
            new_value = output_max

        if output_step > 0:
            new_value = round(new_value / output_step) * output_step
            if new_value < output_min:
                new_value = output_min
            elif new_value > output_max:
                new_value = output_max

        span = output_max - output_min
        if span <= 0:
            duty_ratio = 1.0 if new_value > 0 else 0.0
        else:
            duty_ratio = (new_value - output_min) / span

        duty_ratio = max(0.0, min(1.0, duty_ratio))

        _LOGGER.debug(
            "PWM update: current=%s target=%s output=%s duty=%.1f%%",
            current,
            target,
            new_value,
            duty_ratio * 100.0,
        )

        await self._async_apply_pwm(
            output_min=output_min,
            output_max=output_max,
            duty_ratio=duty_ratio,
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
