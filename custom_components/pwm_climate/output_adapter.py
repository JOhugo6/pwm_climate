"""PWM output adapter for Home Assistant entities."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import Callable
from typing import Any

from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(DOMAIN)

# Domains treated as on/off outputs.
_BINARY_DOMAINS = {"switch", "input_boolean", "light"}
# Domains treated as numeric outputs (0-100%).
_NUMBER_DOMAINS = {"number", "input_number"}
# Maximum time to wait for a blocking Home Assistant service call.
_DEFAULT_SERVICE_CALL_TIMEOUT = 10.0
# Availability probing timings for services/entities that may load late.
_DEFAULT_AVAILABILITY_TIMEOUT = 10.0
_DEFAULT_AVAILABILITY_INTERVAL = 0.25
_DEFAULT_AVAILABILITY_COOLDOWN = 30.0


def _get_entity_domain(entity_id: str | None) -> str | None:
    # Parse "domain.entity" into "domain" with basic validation.
    if not entity_id or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


class PWMOutputAdapter:
    """Translate PWM state and power into service calls for a target entity."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entity_id: str | None,
        name: str | None = None,
        get_climate_temperature: Callable[[], float | None] | None = None,
    ) -> None:
        self._hass = hass
        self._entity_id = entity_id
        self._name = name or "PWM output"
        self._get_climate_temperature = get_climate_temperature

        # Resolve output mode once and cache last applied values.
        self._domain, self._mode = self._resolve_output_mode(entity_id)
        self._last_state: bool | None = None
        self._last_value: float | None = None
        self._warned_unsupported = False
        self._next_availability_check = 0.0

    def set_name(self, name: str | None) -> None:
        # Update friendly name used in logs.
        if name:
            self._name = name

    def update_output_entity(self, entity_id: str | None) -> None:
        # Swap target entity and reset cached output state.
        self._entity_id = entity_id
        self._domain, self._mode = self._resolve_output_mode(entity_id)
        self._last_state = None
        self._last_value = None
        self._warned_unsupported = False
        self._next_availability_check = 0.0

    @property
    def supports_output(self) -> bool:
        # Only true when we have a target entity and a supported mode.
        return self._entity_id is not None and self._mode is not None

    async def async_set_pwm_output(self, is_on: bool, power_percent: float) -> None:
        # Route PWM state to the appropriate HA service based on entity domain.
        if not self._entity_id or self._mode is None:
            self._log_unsupported_once()
            return

        power_percent = self._normalize_percent(power_percent)
        if power_percent is None:
            return

        if self._mode == "binary":
            await self._async_set_binary_output(is_on)
            return

        if self._mode == "number":
            await self._async_set_number_output(power_percent)
            return

        if self._mode == "climate":
            await self._async_set_climate_output(is_on)
            return

    def _resolve_output_mode(self, entity_id: str | None) -> tuple[str | None, str | None]:
        # Map entity domain to a supported output mode.
        domain = _get_entity_domain(entity_id)
        if domain in _BINARY_DOMAINS:
            return domain, "binary"
        if domain in _NUMBER_DOMAINS:
            return domain, "number"
        if domain == "climate":
            return domain, "climate"
        if domain:
            _LOGGER.warning("Unsupported output domain for %s: %s", self._name, domain)
        return domain, None

    @staticmethod
    def _normalize_percent(value: float) -> float | None:
        # Normalize to a finite float in [0, 100].
        try:
            percent = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(percent):
            return None
        return max(0.0, min(100.0, percent))

    async def _async_set_binary_output(self, is_on: bool) -> None:
        await self._async_set_output_value(
            current_value=self._last_state,
            new_value=is_on,
            is_unchanged=lambda current, new: current == new,
            domain=self._domain or "switch",
            service="turn_on" if is_on else "turn_off",
            data={"entity_id": self._entity_id},
            update_cache=self._set_binary_output_cache,
        )

    async def _async_set_number_output(self, percent: float) -> None:
        await self._async_set_output_value(
            current_value=self._last_value,
            new_value=percent,
            is_unchanged=lambda current, new: math.isclose(
                current,
                new,
                rel_tol=0.0,
                abs_tol=1e-6,
            ),
            domain=self._domain or "number",
            service="set_value",
            data={"entity_id": self._entity_id, "value": percent},
            update_cache=self._set_number_output_cache,
        )

    async def _async_set_output_value(
        self,
        *,
        current_value: float | bool | None,
        new_value: float | bool,
        is_unchanged: Callable[[float | bool, float | bool], bool],
        domain: str,
        service: str,
        data: dict[str, Any],
        update_cache: Callable[[float | bool], None],
    ) -> None:
        # Shared write path for binary and numeric outputs.
        if current_value is not None and is_unchanged(current_value, new_value):
            return
        if await self._async_call_service(domain, service, data):
            update_cache(new_value)

    def _set_binary_output_cache(self, is_on: bool) -> None:
        self._last_state = is_on
        self._last_value = None

    def _set_number_output_cache(self, percent: float) -> None:
        self._last_value = percent
        self._last_state = None

    async def _async_set_climate_output(self, is_on: bool) -> None:
        # Climate output is driven by setpoint temperature when "on".
        if is_on:
            temperature = self._resolve_climate_temperature()
            if temperature is None:
                return
            if self._last_value is not None and math.isclose(
                self._last_value,
                temperature,
                rel_tol=0.0,
                abs_tol=1e-6,
            ):
                return
            if await self._async_call_service(
                "climate",
                "set_temperature",
                {
                    "entity_id": self._entity_id,
                    ATTR_TEMPERATURE: temperature,
                },
            ):
                self._last_value = temperature
                self._last_state = True
        else:
            if self._last_state is False:
                return
            if await self._async_call_service(
                "climate",
                "turn_off",
                {"entity_id": self._entity_id},
            ):
                self._last_state = False

    def _resolve_climate_temperature(self) -> float | None:
        # Ask the parent climate entity for the target setpoint.
        if self._get_climate_temperature is None:
            _LOGGER.warning(
                "No output temperature provider for %s; skipping climate output",
                self._name,
            )
            return None
        temperature = self._get_climate_temperature()
        if temperature is None or not math.isfinite(temperature):
            _LOGGER.warning(
                "Invalid output temperature for %s: %s",
                self._name,
                temperature,
            )
            return None
        return float(temperature)

    async def _async_call_service(self, domain: str, service: str, data: dict[str, Any]) -> bool:
        # Verify service + entity exist before calling to avoid noisy errors.
        if not await self._async_ensure_service(domain, service):
            _LOGGER.error(
                "Service %s.%s not found while setting %s; check output entity/domain setup",
                domain,
                service,
                self._entity_id,
            )
            return False
        if not await self._async_ensure_entity(self._entity_id):
            _LOGGER.error(
                "Output entity %s not found while calling %s.%s",
                self._entity_id,
                domain,
                service,
            )
            return False
        target_entity = data.get("entity_id", self._entity_id)
        try:
            async with asyncio.timeout(_DEFAULT_SERVICE_CALL_TIMEOUT):
                await self._hass.services.async_call(
                    domain,
                    service,
                    data,
                    blocking=True,
                )
        except TimeoutError:
            _LOGGER.error(
                "Timed out after %.1fs calling %s.%s for output entity %s",
                _DEFAULT_SERVICE_CALL_TIMEOUT,
                domain,
                service,
                target_entity,
            )
            return False
        except asyncio.CancelledError:
            raise
        except HomeAssistantError as err:
            _LOGGER.error(
                "Failed calling %s.%s for output entity %s: %s",
                domain,
                service,
                target_entity,
                err,
            )
            return False
        return True

    def _should_wait_for_availability(self) -> bool:
        # Throttle availability checks to avoid spamming logs.
        return time.monotonic() >= self._next_availability_check

    def _set_availability_backoff(self) -> None:
        # Backoff window after failed availability checks.
        self._next_availability_check = time.monotonic() + _DEFAULT_AVAILABILITY_COOLDOWN

    async def _async_wait_for(self, predicate: Callable[[], bool]) -> bool:
        # Poll a predicate until it returns True or we hit the timeout.
        deadline = time.monotonic() + _DEFAULT_AVAILABILITY_TIMEOUT
        while time.monotonic() < deadline:
            if predicate():
                return True
            await asyncio.sleep(_DEFAULT_AVAILABILITY_INTERVAL)
        return predicate()

    async def _async_ensure_service(self, domain: str, service: str) -> bool:
        # Wait briefly for service registration on startup if needed.
        if self._hass.services.has_service(domain, service):
            return True
        if not self._should_wait_for_availability():
            return False
        if await self._async_wait_for(lambda: self._hass.services.has_service(domain, service)):
            self._next_availability_check = 0.0
            return True
        self._set_availability_backoff()
        return False

    async def _async_ensure_entity(self, entity_id: str | None) -> bool:
        # Wait briefly for entity registration on startup if needed.
        if not entity_id:
            return False
        if self._hass.states.get(entity_id) is not None:
            return True
        if not self._should_wait_for_availability():
            return False
        if await self._async_wait_for(lambda: self._hass.states.get(entity_id) is not None):
            self._next_availability_check = 0.0
            return True
        self._set_availability_backoff()
        return False

    def _log_unsupported_once(self) -> None:
        # Emit a single warning when output entity is missing or unsupported.
        if self._warned_unsupported:
            return
        self._warned_unsupported = True
        if not self._entity_id:
            _LOGGER.warning("Missing output entity for %s", self._name)
        else:
            _LOGGER.warning("Unsupported output entity for %s: %s", self._name, self._entity_id)
