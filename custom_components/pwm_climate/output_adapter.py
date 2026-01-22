"""Output adapter for PWM Climate Controller."""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from typing import Any

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_BINARY_DOMAINS = {"switch", "input_boolean", "light"}
_NUMBER_DOMAINS = {"number", "input_number"}
_CLIMATE_DOMAINS = {"climate"}


def _get_entity_domain(entity_id: str | None) -> str | None:
    if not entity_id or "." not in entity_id:
        return None
    return entity_id.split(".", 1)[0]


def resolve_output_mode(entity_id: str | None) -> tuple[str | None, str | None]:
    domain = _get_entity_domain(entity_id)
    if domain in _BINARY_DOMAINS:
        return domain, "binary"
    if domain in _NUMBER_DOMAINS:
        return domain, "number"
    if domain in _CLIMATE_DOMAINS:
        return domain, "climate"
    return domain, None


class PWMOutputAdapter:
    """Translate PWM on/off to Home Assistant service calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_id: str | None,
        *,
        on_value_provider: Callable[[], float | None] | None = None,
        number_on_value: float = 100.0,
        number_off_value: float = 0.0,
        context: str | None = None,
    ) -> None:
        self._hass = hass
        self._on_value_provider = on_value_provider
        self._number_on_value = number_on_value
        self._number_off_value = number_off_value
        self._context = context
        self._entity_id: str | None = None
        self._domain: str | None = None
        self._mode: str | None = None
        self._last_state: bool | None = None
        self._last_value: float | None = None
        self.update_entity(entity_id)

    @property
    def mode(self) -> str | None:
        return self._mode

    @property
    def supported(self) -> bool:
        return self._mode is not None and bool(self._entity_id)

    def update_entity(self, entity_id: str | None) -> None:
        self._entity_id = entity_id
        self._domain, self._mode = resolve_output_mode(entity_id)
        self._last_state = None
        self._last_value = None
        if self._mode is None and self._domain:
            label = f" for {self._context}" if self._context else ""
            _LOGGER.warning("Unsupported output domain%s: %s", label, self._domain)

    async def async_set_state(self, is_on: bool) -> None:
        if not self._entity_id or self._mode is None:
            return

        if self._mode == "binary":
            if self._last_state is not None and self._last_state == is_on:
                return
            service_domain = self._domain or "switch"
            service = "turn_on" if is_on else "turn_off"
            await self._async_call(service_domain, service, {"entity_id": self._entity_id})
            self._last_state = is_on
            self._last_value = None
            return

        if self._mode == "number":
            value = self._number_on_value if is_on else self._number_off_value
            if not math.isfinite(value):
                return
            safe_value = max(0.0, min(100.0, value))
            if (
                self._last_value is not None
                and math.isclose(self._last_value, safe_value, rel_tol=0.0, abs_tol=1e-6)
            ):
                return
            service_domain = self._domain or "number"
            await self._async_call(
                service_domain,
                "set_value",
                {"entity_id": self._entity_id, "value": safe_value},
            )
            self._last_state = is_on
            self._last_value = safe_value
            return

        if self._mode == "climate":
            if is_on:
                temperature = None
                if self._on_value_provider:
                    try:
                        temperature = self._on_value_provider()
                    except Exception:
                        _LOGGER.exception(
                            "Failed reading climate temperature for %s",
                            self._entity_id,
                        )
                        return
                try:
                    temperature_value = float(temperature) if temperature is not None else None
                except (TypeError, ValueError):
                    temperature_value = None
                if temperature_value is None or not math.isfinite(temperature_value):
                    _LOGGER.debug(
                        "Skipping climate output for %s: missing temperature",
                        self._entity_id,
                    )
                    return
                if (
                    self._last_state is True
                    and self._last_value is not None
                    and math.isclose(
                        self._last_value,
                        temperature_value,
                        rel_tol=0.0,
                        abs_tol=1e-6,
                    )
                ):
                    return
                await self._async_call(
                    "climate",
                    "set_temperature",
                    {"entity_id": self._entity_id, "temperature": temperature_value},
                )
                self._last_state = True
                self._last_value = temperature_value
                return

            if self._last_state is False:
                return
            await self._async_call("climate", "turn_off", {"entity_id": self._entity_id})
            self._last_state = False
            self._last_value = None

    async def _async_call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        try:
            await self._hass.services.async_call(domain, service, data, blocking=True)
        except Exception:
            _LOGGER.exception(
                "Failed calling %s.%s for %s",
                domain,
                service,
                self._entity_id,
            )
