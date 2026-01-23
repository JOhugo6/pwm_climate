"""PWM output adapter for Home Assistant entities."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

from homeassistant.const import ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(DOMAIN)

_BINARY_DOMAINS = {"switch", "input_boolean", "light"}
_NUMBER_DOMAINS = {"number", "input_number"}


def _get_entity_domain(entity_id: str | None) -> str | None:
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

    def set_name(self, name: str | None) -> None:
        if name:
            self._name = name

    def update_output_entity(self, entity_id: str | None) -> None:
        self._entity_id = entity_id
        self._domain, self._mode = self._resolve_output_mode(entity_id)
        self._last_state = None
        self._last_value = None
        self._warned_unsupported = False

    @property
    def supports_output(self) -> bool:
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
        try:
            percent = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(percent):
            return None
        return max(0.0, min(100.0, percent))

    async def _async_set_binary_output(self, is_on: bool) -> None:
        # Avoid redundant service calls for binary entities.
        if self._last_state is not None and self._last_state == is_on:
            return
        service = "turn_on" if is_on else "turn_off"
        if await self._async_call_service(
            self._domain or "switch",
            service,
            {"entity_id": self._entity_id},
        ):
            self._last_state = is_on
            self._last_value = None

    async def _async_set_number_output(self, percent: float) -> None:
        # Avoid redundant service calls for numeric entities.
        if self._last_value is not None and math.isclose(
            self._last_value,
            percent,
            rel_tol=0.0,
            abs_tol=1e-6,
        ):
            return
        if await self._async_call_service(
            self._domain or "number",
            "set_value",
            {"entity_id": self._entity_id, "value": percent},
        ):
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
        try:
            await self._hass.services.async_call(
                domain,
                service,
                data,
                blocking=True,
            )
        except Exception:
            _LOGGER.exception(
                "Failed setting %s via %s.%s",
                self._entity_id,
                domain,
                service,
            )
            return False
        return True

    def _log_unsupported_once(self) -> None:
        if self._warned_unsupported:
            return
        self._warned_unsupported = True
        if not self._entity_id:
            _LOGGER.warning("Missing output entity for %s", self._name)
        else:
            _LOGGER.warning("Unsupported output entity for %s: %s", self._name, self._entity_id)
