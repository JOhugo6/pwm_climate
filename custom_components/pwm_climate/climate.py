"""Climate platform for PWM Climate Controller integration."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Callable, Mapping
from typing import Any

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import ATTR_PRESET_MODE, HVACMode
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
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_DEFAULT_PRESET,
    CONF_HUMIDITY_ENTITY,
    CONF_MAX_TEMPERATURE,
    CONF_MIN_TEMPERATURE,
    CONF_NAME,
    CONF_OUTPUT_ENTITY,
    CONF_PWM_PERIOD,
    CONF_KP,
    CONF_TEMPERATURE_ENTITY,
    CONF_TEMPERATURE_STEP,
    DEFAULT_PRESET,
    DEFAULT_MAX_TEMPERATURE,
    DEFAULT_MIN_TEMPERATURE,
    DEFAULT_PWM_PERIOD,
    DEFAULT_KP,
    DEFAULT_TEMPERATURE_STEP,
    DOMAIN,
    PRESET_DEFAULT_TEMPERATURES,
    PRESET_LABELS,
    PRESET_MANUAL,
    PRESET_NAMES,
)
from .preset_helpers import resolve_preset_temperatures
from .output_adapter import PWMOutputAdapter
from .pwm_timer import SoftwarePWMTimer

_LOGGER = logging.getLogger(DOMAIN)
# Reasons that require PWM cycle restart (e.g., period or target changes).
# Reasons that require PWM cycle restart (period/target changes or major state shifts).
_PWM_RESTART_REASONS = {
    "config_update",
    "hvac_mode_change",
    "regulation_change",
    "startup",
    "temperature_change",
    "temperature_unavailable",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    # Register a single climate entity per config entry.
    async_add_entities([PWMClimateController(hass, entry)])


def _coerce_float(value: Any, default: float) -> float:
    # Read numeric settings from config with safe fallback.
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_optional_float(value: Any) -> float | None:
    # Parse a float, returning None for invalid or non-finite values.
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _coerce_int(value: Any, default: int) -> int:
    # Read integer settings from config with safe fallback.
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _resolve_preset_temperatures(entry: ConfigEntry) -> dict[str, float]:
    # Start from defaults and then overlay config data/options (newer wins).
    temperatures_by_id = resolve_preset_temperatures(entry.data, entry.options)
    # Convert numeric ids into label -> temperature mapping used by the entity.
    return {
        PRESET_LABELS[preset_id]: temperature
        for preset_id, temperature in temperatures_by_id.items()
        if preset_id in PRESET_LABELS
    }


def _resolve_default_preset(entry: ConfigEntry, presets: Mapping[str, float]) -> str:
    # Pick a valid default preset from options/data, then fallback to defaults.
    candidate = entry.options.get(CONF_DEFAULT_PRESET, entry.data.get(CONF_DEFAULT_PRESET))
    if isinstance(candidate, str) and candidate in presets:
        return candidate
    if DEFAULT_PRESET in presets:
        return DEFAULT_PRESET
    return next(iter(presets), DEFAULT_PRESET)


def _resolve_output_entity_id(entry: ConfigEntry) -> str | None:
    # Prefer the configured option value, then fall back to legacy entry data.
    for candidate in (
        entry.options.get(CONF_OUTPUT_ENTITY),
        entry.data.get(CONF_OUTPUT_ENTITY),
    ):
        if isinstance(candidate, str) and candidate.strip():
            return candidate

    _LOGGER.error(
        "Missing output entity for config entry %s; output control will be disabled",
        entry.title,
    )
    return None


def _extract_temperature_value(state: State | None) -> tuple[float | None, str | None]:
    # Normalize a temperature state to (float or None, error tag) for logging.
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
    except (TypeError, ValueError):
        return None, "non_numeric"

    if not math.isfinite(temperature):
        return None, "non_numeric"

    return temperature, None


def _extract_humidity_value(state: State | None) -> tuple[float | None, str | None]:
    # Normalize a humidity state to (float or None, error tag) for logging.
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


class PWMClimateController(ClimateEntity, RestoreEntity):
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        # Keep references to Home Assistant core and config entry.
        self._hass = hass
        self._config_entry = entry

        # Core entity metadata exposed to Home Assistant.
        self._attr_unique_id = self._config_entry.entry_id
        self._attr_name = self._config_entry.data.get(CONF_NAME, self._config_entry.title)

        # Options override initial entry data for the sensor/entity bindings.
        self._temperature_entity_id: str | None = self._config_entry.options.get(
            CONF_TEMPERATURE_ENTITY,
            self._config_entry.data.get(CONF_TEMPERATURE_ENTITY),
        )
        self._output_entity_id = _resolve_output_entity_id(self._config_entry)
        self._humidity_sensor_entity_id: str | None = self._config_entry.options.get(
            CONF_HUMIDITY_ENTITY,
            self._config_entry.data.get(CONF_HUMIDITY_ENTITY),
        )

        # Resolve preset temperatures and active preset state.
        self._preset_temperatures = _resolve_preset_temperatures(self._config_entry)
        self._default_preset = _resolve_default_preset(self._config_entry, self._preset_temperatures)
        self._active_preset = self._default_preset
        self._manual_override = False

        # Load limits and tuning parameters from config.
        self._attr_min_temp = _coerce_float(
            self._config_entry.options.get(
                CONF_MIN_TEMPERATURE,
                self._config_entry.data.get(CONF_MIN_TEMPERATURE),
            ),
            DEFAULT_MIN_TEMPERATURE,
        )
        self._attr_max_temp = _coerce_float(
            self._config_entry.options.get(
                CONF_MAX_TEMPERATURE,
                self._config_entry.data.get(CONF_MAX_TEMPERATURE),
            ),
            DEFAULT_MAX_TEMPERATURE,
        )
        self._attr_target_temperature_step = _coerce_float(
            self._config_entry.options.get(
                CONF_TEMPERATURE_STEP,
                self._config_entry.data.get(CONF_TEMPERATURE_STEP),
            ),
            DEFAULT_TEMPERATURE_STEP,
        )
        self._pwm_period_setting_seconds = _coerce_int(
            self._config_entry.options.get(
                CONF_PWM_PERIOD,
                self._config_entry.data.get(CONF_PWM_PERIOD),
            ),
            DEFAULT_PWM_PERIOD,
        )
        self._p_gain = _coerce_float(
            self._config_entry.options.get(
                CONF_KP,
                self._config_entry.data.get(CONF_KP),
            ),
            DEFAULT_KP,
        )

        # Expose available modes and presets to the frontend.
        self._attr_hvac_modes = self._compute_hvac_modes()
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_preset_modes = list(PRESET_NAMES)
        self._attr_preset_mode = self._active_preset

        # Runtime state exposed to HA and used for control.
        self._current_temperature: float | None = None
        self._attr_current_temperature: float | None = self._current_temperature
        # Target temperature follows active preset unless manual override is set.
        self._attr_target_temperature: float = self._get_preset_temperature(self._active_preset)
        self._attr_current_humidity: float | None = None
        # Output adapter translates PWM state into HA services.
        self._output_adapter = PWMOutputAdapter(
            self._hass,
            entity_id=self._output_entity_id,
            name=self._attr_name,
            get_climate_temperature=self._get_output_temperature,
        )

        # Handles to listener unsubscribe callbacks.
        self._unsub_temperature_listener: Callable[[], None] | None = None
        self._unsub_regulation_listener: Callable[[], None] | None = None
        self._unsub_humidity_listener: Callable[[], None] | None = None
        self._unsub_entry_update_listener: Callable[[], None] | None = None
        self._regulation_update_task: asyncio.Task[None] | None = None
        self._pending_regulation_update_reason: str | None = None
        self._is_removing = False
        # Serialize output updates to avoid overlapping PWM recalculations.
        self._pwm_lock = asyncio.Lock()
        # Software PWM timer drives on/off phases based on duty ratio.
        self._pwm_timer = SoftwarePWMTimer(
            set_output=self._output_adapter.async_set_pwm_output,
            name=self._attr_name,
            create_task=self._hass.async_create_task,
        )
        # Cached control outputs for diagnostics.
        self._duty_cycle_percent: float | None = None
        self._p_output: float = 0.0
        self._control_output_percent: float | None = self._p_output

        _LOGGER.debug(
            "PWMClimateController init name=%s temp_sensor=%s output=%s pwm_period_seconds=%s",
            self._attr_name,
            self._temperature_entity_id,
            self._output_entity_id,
            self._pwm_period_setting_seconds,
        )

    def _compute_hvac_modes(self) -> list[HVACMode]:
        # Integration supports only OFF and HEAT at the moment.
        return [HVACMode.OFF, HVACMode.HEAT]

    def _is_preset_off(self) -> bool:
        # Treat "off" and "building protection" as no-heat presets.
        preset = self._attr_preset_mode
        if not isinstance(preset, str):
            return False
        normalized = preset.strip().casefold()
        if normalized == "off":
            return True
        protection = PRESET_LABELS.get(4)
        if isinstance(protection, str) and normalized == protection.strip().casefold():
            return True
        return False

    def _get_preset_temperature(self, preset: str) -> float:
        temperature = self._preset_temperatures.get(preset)
        if temperature is not None and math.isfinite(temperature):
            return temperature
        return PRESET_DEFAULT_TEMPERATURES[0]

    def _get_output_temperature(self) -> float | None:
        return self._attr_target_temperature

    def _calculate_proportional_output(
        self,
        current_temperature: float,
        target_temperature: float,
        kp: float,
    ) -> tuple[float, float]:
        # Simple P controller: output = kp * error, clamped to 0..100.
        error = target_temperature - current_temperature
        output = kp * error
        if not math.isfinite(output):
            output = 0.0
        output = max(0.0, min(100.0, output))
        return float(output), error

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Expose diagnostic attributes for dashboards and troubleshooting.
        return {
            "temperature_entity": self._temperature_entity_id,
            "output_entity": self._output_entity_id,
            "humidity_entity": self._humidity_sensor_entity_id,
            "pwm_period_seconds": self._pwm_period_setting_seconds,
            "default_preset": self._default_preset,
            "active_preset": self._active_preset,
            "manual_override": self._manual_override,
            "control_output_percent": self._control_output_percent,
            "duty_cycle_percent": self._duty_cycle_percent,
        }

    def _set_target_temperature(self, temperature: float, *, reason: str) -> None:
        # Update the target setpoint and log the reason.
        self._attr_target_temperature = float(temperature)
        _LOGGER.debug(
            "Setpoint change for %s -> %.2f (reason=%s)",
            self.entity_id,
            self._attr_target_temperature,
            reason,
        )

    async def _async_apply_preset(
        self,
        preset: str,
        *,
        reason: str,
    ) -> None:
        # Apply a preset and clear manual override.
        if preset not in self._preset_temperatures:
            preset = self._default_preset

        self._active_preset = preset
        self._manual_override = False
        self._attr_preset_mode = preset
        self._set_target_temperature(self._get_preset_temperature(preset), reason=reason)

        self.async_write_ha_state()

    async def _async_apply_manual_override(self, temperature: float) -> None:
        # Manual setpoint forces preset to manual until another preset is selected.
        self._manual_override = True
        self._attr_preset_mode = PRESET_MANUAL
        self._set_target_temperature(temperature, reason="manual_override")
        self.async_write_ha_state()

    async def _async_restore_state(self) -> None:
        # Restore last HVAC mode, presets, and setpoint if available.
        last_state = await self.async_get_last_state()
        if last_state is None:
            return

        restored_hvac: HVACMode | None = None
        try:
            restored_hvac = HVACMode(last_state.state)
        except ValueError:
            restored_hvac = None

        if restored_hvac in self._attr_hvac_modes:
            self._attr_hvac_mode = restored_hvac

        preset_mode = last_state.attributes.get(ATTR_PRESET_MODE)
        active_preset = last_state.attributes.get("active_preset")

        if isinstance(active_preset, str) and active_preset in self._preset_temperatures:
            self._active_preset = active_preset
        elif isinstance(preset_mode, str) and preset_mode in self._preset_temperatures:
            self._active_preset = preset_mode
        else:
            self._active_preset = self._default_preset

        self._manual_override = bool(
            preset_mode == PRESET_MANUAL or last_state.attributes.get("manual_override")
        )
        self._attr_preset_mode = PRESET_MANUAL if self._manual_override else self._active_preset

        restored_target = last_state.attributes.get(ATTR_TEMPERATURE)
        if restored_target is not None:
            restored_target = _coerce_float(restored_target, self._attr_target_temperature)

        if self._manual_override:
            if restored_target is not None:
                self._set_target_temperature(restored_target, reason="restore_manual")
            else:
                self._set_target_temperature(
                    self._get_preset_temperature(self._active_preset),
                    reason="restore_manual_default",
                )
        else:
            if restored_target is not None:
                self._set_target_temperature(restored_target, reason="restore_target")
            else:
                self._set_target_temperature(
                    self._get_preset_temperature(self._active_preset),
                    reason="restore_preset",
                )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        # User setpoint becomes a manual override.
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        await self._async_apply_manual_override(float(temperature))

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        # Switch to a specific preset and update target temperature.
        if preset_mode not in self._attr_preset_modes:
            _LOGGER.debug("Ignoring unknown preset %s", preset_mode)
            return

        await self._async_apply_preset(
            preset_mode,
            reason="preset_selection",
        )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        # Update HVAC mode and restart PWM if needed.
        if hvac_mode not in self._attr_hvac_modes:
            _LOGGER.debug("Ignoring unsupported HVAC mode: %s", hvac_mode)
            return

        previous_mode = self._attr_hvac_mode
        was_off = previous_mode == HVACMode.OFF
        if hvac_mode == previous_mode:
            return

        self._attr_hvac_mode = hvac_mode

        if hvac_mode == HVACMode.OFF:
            _LOGGER.info(
                "HVAC %s -> OFF for %s; forcing P output to 0",
                previous_mode,
                self.entity_id,
            )
        elif hvac_mode == HVACMode.HEAT and was_off:
            # When turning on, reset to default preset and clear manual override.
            await self._async_stop_pwm_task(reason="hvac_off_to_heat")
            self._manual_override = False
            self._active_preset = self._default_preset
            self._attr_preset_mode = self._active_preset
            self._set_target_temperature(
                self._get_preset_temperature(self._active_preset),
                reason="default_preset",
            )
            _LOGGER.info(
                "HVAC OFF -> HEAT for %s; applying default preset %s (target=%.1f)",
                self.entity_id,
                self._active_preset,
                self._attr_target_temperature,
            )
        else:
            _LOGGER.info(
                "HVAC mode changed for %s: %s -> %s",
                self.entity_id,
                previous_mode,
                hvac_mode,
            )

        self.async_write_ha_state()
        await self._async_update_output(reason="hvac_mode_change")

    @callback
    def _handle_regulation_input_change(self, *, reason: str) -> None:
        # Coalesce repeated regulation updates into one tracked task.
        if self._is_removing:
            return

        self._pending_regulation_update_reason = reason

        task = self._regulation_update_task
        if task is not None and not task.done():
            return

        task = self.hass.async_create_task(self._async_process_regulation_updates())
        self._regulation_update_task = task
        task.add_done_callback(self._async_on_regulation_update_task_done)

    async def _async_process_regulation_updates(self) -> None:
        # Apply the latest requested regulation update and rerun if a newer request arrives.
        while not self._is_removing:
            reason = self._pending_regulation_update_reason
            if reason is None:
                return

            self._pending_regulation_update_reason = None
            await self._async_update_output(reason=reason)

    @callback
    def _async_on_regulation_update_task_done(self, task: asyncio.Task[None]) -> None:
        if self._regulation_update_task is task:
            self._regulation_update_task = None

        try:
            exception = task.exception()
        except asyncio.CancelledError:
            _LOGGER.debug("Cancelled regulation update task for %s", self.entity_id)
            return

        if exception is not None:
            _LOGGER.error(
                "Regulation update task failed for %s",
                self.entity_id,
                exc_info=exception,
            )

    async def _async_cancel_regulation_update_task(self) -> None:
        self._pending_regulation_update_reason = None
        task = self._regulation_update_task
        if task is None:
            return

        if task.done():
            if self._regulation_update_task is task:
                self._regulation_update_task = None
            return

        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @callback
    def _async_regulation_state_changed(self, event: Event) -> None:
        # React to changes on our own climate entity (preset/target adjustments).
        if self._is_removing:
            return

        old_state: State | None = event.data.get("old_state")
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            _LOGGER.debug(
                "Ignoring regulation input change for %s: new_state is None",
                self.entity_id,
            )
            return

        # Compare preset and target temperature to avoid unnecessary recalculations.
        old_preset = old_state.attributes.get(ATTR_PRESET_MODE) if old_state else None
        new_preset = new_state.attributes.get(ATTR_PRESET_MODE)
        preset_changed = old_preset != new_preset

        old_target = (
            _coerce_optional_float(old_state.attributes.get(ATTR_TEMPERATURE))
            if old_state
            else None
        )
        new_target = _coerce_optional_float(new_state.attributes.get(ATTR_TEMPERATURE))
        if old_target is None or new_target is None:
            target_changed = old_target != new_target
        else:
            target_changed = not math.isclose(
                new_target,
                old_target,
                rel_tol=0.0,
                abs_tol=1e-6,
            )

        if not preset_changed and not target_changed:
            return

        if preset_changed:
            if new_target is None:
                _LOGGER.info("Preset changed to %s", new_preset)
            else:
                _LOGGER.info("Preset changed to %s (target=%.1f)", new_preset, new_target)

        if target_changed:
            if new_target is None:
                _LOGGER.info("Target temperature cleared")
            else:
                _LOGGER.info("Target temperature changed to %.1f", new_target)

        self._handle_regulation_input_change(reason="regulation_change")

    @callback
    def _async_temperature_changed(self, event: Event) -> None:
        # Update current temperature and recompute output if sensor changes.
        if self._is_removing:
            return

        old_state: State | None = event.data.get("old_state")
        new_state: State | None = event.data.get("new_state")
        if new_state is None:
            _LOGGER.debug(
                "Ignoring temperature state for %s: new_state is None",
                self._temperature_entity_id,
            )
            return

        if new_state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            _LOGGER.debug(
                "Temperature state unavailable for %s: state=%s",
                self._temperature_entity_id,
                new_state.state,
            )
            if self._current_temperature is not None:
                self._current_temperature = None
                self._attr_current_temperature = None
                self.async_write_ha_state()
                self._handle_regulation_input_change(reason="temperature_unavailable")
            return

        temperature, error = _extract_temperature_value(new_state)
        if temperature is None:
            raw_state = new_state.state
            _LOGGER.debug(
                "Ignoring temperature state for %s: %s (reason=%s)",
                self._temperature_entity_id,
                raw_state,
                error,
            )
            return

        old_temperature: float | None = None
        old_display: Any = None
        if old_state is not None:
            old_temperature, _old_error = _extract_temperature_value(old_state)
            old_display = old_temperature if old_temperature is not None else old_state.state

        previous_temperature = (
            old_temperature if old_temperature is not None else self._current_temperature
        )
        previous_display = (
            old_display if old_display is not None else self._current_temperature
        )
        if (
            previous_temperature is not None
            and math.isclose(
                temperature,
                previous_temperature,
                rel_tol=0.0,
                abs_tol=1e-6,
            )
        ):
            return

        self._current_temperature = temperature
        self._attr_current_temperature = temperature
        _LOGGER.info(
            "Temperature updated for %s (%s): %s -> %s",
            self.entity_id,
            self._temperature_entity_id,
            previous_display,
            temperature,
        )
        self.async_write_ha_state()
        self._handle_regulation_input_change(reason="temperature_change")

    @callback
    def _async_humidity_changed(self, event: Event) -> None:
        # Update humidity attribute when sensor changes.
        if self._is_removing:
            return

        event_data = event.data if isinstance(event.data, Mapping) else {}
        old_state: State | None = event_data.get("old_state")
        new_state: State | None = event_data.get("new_state")
        if new_state is None:
            _LOGGER.debug(
                "Ignoring humidity event for %s because event payload has no usable new_state",
                self._humidity_sensor_entity_id,
            )
            return

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
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_added_to_hass(self) -> None:
        # Restore state, sync sensors, start PWM, and register listeners.
        await super().async_added_to_hass()
        # Use entity_id once available for clearer log messages.
        self._pwm_timer.set_name(self.entity_id or self._attr_name)
        self._output_adapter.set_name(self.entity_id or self._attr_name)
        # Restore persisted state (HVAC mode, preset, target).
        await self._async_restore_state()
        # Seed current temperature/humidity from existing HA states.
        self._async_sync_current_temperature_from_state(
            self.hass.states.get(self._temperature_entity_id),
            log_initial=True,
        )
        await self._async_update_output(reason="startup")
        # Subscribe to changes that drive control updates.
        self._async_subscribe_temperature_listener()
        self.async_on_remove(self._async_unsubscribe_temperature_listener)

        self._async_subscribe_regulation_listener()
        self.async_on_remove(self._async_unsubscribe_regulation_listener)

        self._async_subscribe_humidity_listener()
        self._async_sync_current_humidity_from_state(
            self.hass.states.get(self._humidity_sensor_entity_id)
            if self._humidity_sensor_entity_id
            else None,
            log_initial=True,
        )
        self.async_on_remove(self._async_unsubscribe_humidity_listener)

        # React to config entry updates (options changes).
        self._unsub_entry_update_listener = self._config_entry.add_update_listener(
            self._async_config_entry_updated
        )

        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        # Mark as removing and tear down listeners/PWM loop.
        self._is_removing = True
        self._async_unsubscribe_temperature_listener()
        self._async_unsubscribe_regulation_listener()
        self._async_unsubscribe_humidity_listener()
        await self._async_cancel_regulation_update_task()
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
        # Read current temperature from a HA state object.
        temperature, error = _extract_temperature_value(state)
        if temperature is None:
            if self._current_temperature is not None:
                self._current_temperature = None
                self._attr_current_temperature = None
            if log_initial:
                raw_state = state.state if state is not None else None
                if error == "non_numeric":
                    _LOGGER.debug(
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
        self._current_temperature = temperature
        if log_initial:
            _LOGGER.debug(
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
        # Read current humidity from a HA state object.
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
    def _async_unsubscribe_regulation_listener(self) -> None:
        if self._unsub_regulation_listener is None:
            return

        self._unsub_regulation_listener()
        self._unsub_regulation_listener = None
        _LOGGER.debug("Unregistered regulation listener for %s", self.entity_id)

    @callback
    def _async_unsubscribe_humidity_listener(self) -> None:
        if self._unsub_humidity_listener is None:
            return

        self._unsub_humidity_listener()
        self._unsub_humidity_listener = None
        _LOGGER.debug("Unregistered humidity listener for %s", self.entity_id)

    @callback
    def _async_subscribe_temperature_listener(self) -> None:
        # (Re)register listener for temperature sensor changes.
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
        _LOGGER.debug(
            "Registered temperature listener for %s (%s)",
            self.entity_id,
            self._temperature_entity_id,
        )

    @callback
    def _async_subscribe_regulation_listener(self) -> None:
        # (Re)register listener for self state changes.
        if self._is_removing:
            return

        self._async_unsubscribe_regulation_listener()

        if not self.entity_id:
            _LOGGER.debug(
                "No entity_id available for %s; regulation listener not registered",
                self._attr_name,
            )
            return

        self._unsub_regulation_listener = async_track_state_change_event(
            self.hass,
            [self.entity_id],
            self._async_regulation_state_changed,
        )
        _LOGGER.debug("Registered regulation listener for %s", self.entity_id)

    @callback
    def _async_subscribe_humidity_listener(self) -> None:
        # (Re)register listener for humidity sensor changes.
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
        # Refresh config values and restart PWM if timing changed.
        if self._is_removing:
            return

        # Keep a reference to the updated entry for future reads.
        self._config_entry = entry

        temperature_entity_id = self._config_entry.options.get(
            CONF_TEMPERATURE_ENTITY,
            self._config_entry.data.get(CONF_TEMPERATURE_ENTITY),
        )
        humidity_entity_id = self._config_entry.options.get(
            CONF_HUMIDITY_ENTITY,
            self._config_entry.data.get(CONF_HUMIDITY_ENTITY),
        )

        if isinstance(temperature_entity_id, str) and temperature_entity_id:
            if temperature_entity_id != self._temperature_entity_id:
                _LOGGER.debug(
                    "Updating temperature sensor for %s: %s -> %s",
                    self.entity_id,
                    self._temperature_entity_id,
                    temperature_entity_id,
                )
                self._temperature_entity_id = temperature_entity_id
                self._async_subscribe_temperature_listener()
                self._async_sync_current_temperature_from_state(
                    hass.states.get(self._temperature_entity_id)
                )

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

        output_entity_id = self._config_entry.options.get(
            CONF_OUTPUT_ENTITY,
            self._config_entry.data.get(CONF_OUTPUT_ENTITY),
        )
        if isinstance(output_entity_id, str) and output_entity_id:
            if output_entity_id != self._output_entity_id:
                old_output_entity_id = self._output_entity_id
                self._output_entity_id = output_entity_id
                self._output_adapter.update_output_entity(self._output_entity_id)
                _LOGGER.debug(
                    "Updating output entity for %s: %s -> %s",
                    self.entity_id,
                    old_output_entity_id,
                    output_entity_id,
                )

        previous_pwm_period = self._pwm_period_setting_seconds
        previous_active_preset_temp = self._preset_temperatures.get(self._active_preset)

        self._preset_temperatures = _resolve_preset_temperatures(self._config_entry)
        self._default_preset = _resolve_default_preset(self._config_entry, self._preset_temperatures)
        if self._active_preset not in self._preset_temperatures:
            self._active_preset = self._default_preset
            if not self._manual_override:
                self._attr_preset_mode = self._active_preset
        self._attr_min_temp = _coerce_float(
            self._config_entry.options.get(
                CONF_MIN_TEMPERATURE,
                self._config_entry.data.get(CONF_MIN_TEMPERATURE),
            ),
            DEFAULT_MIN_TEMPERATURE,
        )
        self._attr_max_temp = _coerce_float(
            self._config_entry.options.get(
                CONF_MAX_TEMPERATURE,
                self._config_entry.data.get(CONF_MAX_TEMPERATURE),
            ),
            DEFAULT_MAX_TEMPERATURE,
        )
        self._attr_target_temperature_step = _coerce_float(
            self._config_entry.options.get(
                CONF_TEMPERATURE_STEP,
                self._config_entry.data.get(CONF_TEMPERATURE_STEP),
            ),
            DEFAULT_TEMPERATURE_STEP,
        )
        self._pwm_period_setting_seconds = _coerce_int(
            self._config_entry.options.get(
                CONF_PWM_PERIOD,
                self._config_entry.data.get(CONF_PWM_PERIOD),
            ),
            DEFAULT_PWM_PERIOD,
        )
        self._p_gain = _coerce_float(
            self._config_entry.options.get(
                CONF_KP,
                self._config_entry.data.get(CONF_KP),
            ),
            DEFAULT_KP,
        )
        if self._pwm_period_setting_seconds != previous_pwm_period:
            await self._async_stop_pwm_task(reason="pwm_period_change")

        if not self._manual_override:
            new_active_temp = self._preset_temperatures.get(self._active_preset)
            if new_active_temp is not None and (
                previous_active_preset_temp is None
                or not math.isclose(
                    new_active_temp,
                    previous_active_preset_temp,
                    rel_tol=0.0,
                    abs_tol=1e-6,
                )
            ):
                self._set_target_temperature(new_active_temp, reason="preset_temp_update")
        self._attr_hvac_modes = self._compute_hvac_modes()
        if self._attr_hvac_mode not in self._attr_hvac_modes:
            self._attr_hvac_mode = HVACMode.OFF if HVACMode.OFF in self._attr_hvac_modes else self._attr_hvac_modes[0]

        self.async_write_ha_state()
        await self._async_update_output(reason="config_update")

    async def _async_stop_pwm_task(self, *, reason: str | None = None) -> None:
        await self._pwm_timer.stop(reason=reason)

    async def _async_apply_pwm(
        self,
        *,
        duty_ratio: float,
        force_restart: bool = False,
        restart_reason: str | None = None,
    ) -> None:
        # Enforce HVAC/preset off rules and apply PWM timing.
        if not self._output_adapter.supports_output:
            await self._pwm_timer.stop(reason="unsupported_output")
            return

        preset_off = self._is_preset_off()
        period_seconds = float(max(self._pwm_period_setting_seconds, 1))
        duty_ratio = max(0.0, min(1.0, duty_ratio))
        # Track the reason why output is forced off for logging/diagnostics.
        off_reason: str | None = None
        if self._attr_hvac_mode != HVACMode.HEAT:
            duty_ratio = 0.0
            off_reason = "hvac_off"
        elif preset_off:
            duty_ratio = 0.0
            off_reason = "preset_off"
        elif duty_ratio <= 0.0:
            off_reason = "duty=0%"

        if off_reason is not None:
            _LOGGER.debug(
                "PWM stop (off mode) for %s (hvac=%s preset_off=%s duty=%.1f%%)",
                self.entity_id,
                self._attr_hvac_mode,
                preset_off,
                duty_ratio * 100.0,
            )

        await self._pwm_timer.apply(
            period_seconds=period_seconds,
            duty_ratio=duty_ratio,
            force_restart=force_restart,
            restart_reason=restart_reason,
            off_reason=off_reason,
        )

    async def _async_update_output(self, *, reason: str) -> None:
        # Serialize output updates so PWM duty changes stay consistent.
        if self._is_removing:
            return

        force_pwm_restart = reason in _PWM_RESTART_REASONS
        async with self._pwm_lock:
            await self._async_update_output_hook(reason=reason)
            duty_percent = await self._async_update_output_internal()
            self._duty_cycle_percent = duty_percent
            _LOGGER.debug("Duty cycle for %s: %.2f%%", self.entity_id, duty_percent)
            await self._async_apply_pwm(
                duty_ratio=duty_percent / 100.0,
                force_restart=force_pwm_restart,
                restart_reason=reason,
            )

    async def _async_update_output_hook(self, *, reason: str = "state_change") -> None:
        if self._is_removing:
            return

        _LOGGER.debug(
            "P output recalculation for %s (reason=%s current=%s target=%s hvac=%s)",
            self.entity_id,
            reason,
            self._attr_current_temperature,
            self._attr_target_temperature,
            self._attr_hvac_mode,
        )

    async def _async_update_output_internal(self) -> float:
        # Compute P-control output and update entity state if it changed.
        current = self._attr_current_temperature
        target = self._attr_target_temperature
        # Default to 0% output when we cannot compute a valid control signal.
        skip_reason: str | None = None
        output = 0.0
        error: float | None = None
        if current is None:
            skip_reason = "missing_temperature"
        else:
            output, error = self._calculate_proportional_output(
                current,
                target,
                self._p_gain,
            )
            if self._attr_hvac_mode == HVACMode.OFF:
                output = 0.0
                skip_reason = "hvac_off"
            elif self._is_preset_off():
                output = 0.0
                skip_reason = "preset_off"

        _LOGGER.debug(
            "P-control %s for %s (reason=%s current=%s target=%s error=%s kp=%s output=%.2f%%)",
            "calculation" if skip_reason is None else "skipped",
            self.entity_id,
            skip_reason or "ok",
            current,
            target,
            error,
            self._p_gain,
            output,
        )

        previous_output = self._p_output
        self._p_output = float(output)
        self._control_output_percent = self._p_output
        if not math.isclose(previous_output, output, rel_tol=0.0, abs_tol=1e-6):
            _LOGGER.debug("P output updated: %.2f%%", output)
            self.async_write_ha_state()
        return self._p_output

