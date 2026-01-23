from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from .const import (
    CONF_HVAC_MODES,
    PRESET_DEFAULT_TEMPERATURES,
    PRESET_LABELS,
    PRESET_TEMPERATURE_KEYS,
)


def _coerce_preset_temperature(value: Any) -> float | None:
    # Accept numeric-like values, including comma decimal strings.
    if value is None:
        return None

    if isinstance(value, str):
        # Allow comma decimal separator for locales that use it.
        value = value.strip()
        if not value:
            return None
        if "," in value and "." not in value:
            value = value.replace(",", ".")

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(number):
        return None

    return number


def _apply_flat_preset_temperatures(
    base: dict[int, float],
    source: Mapping[str, Any] | None,
) -> dict[int, float]:
    # Overlay flat key/value pairs using PRESET_TEMPERATURE_KEYS mapping.
    if not isinstance(source, Mapping):
        return base

    for preset_id, key in PRESET_TEMPERATURE_KEYS.items():
        if key not in source:
            continue
        temperature = _coerce_preset_temperature(source[key])
        if temperature is None:
            continue
        base[preset_id] = temperature

    return base


def _merge_preset_temperatures(
    base: dict[int, float],
    raw: Mapping[Any, Any] | None,
) -> dict[int, float]:
    # Merge nested "hvac_modes" style dictionaries into the base map.
    if not isinstance(raw, Mapping):
        return base

    # Build label -> id lookup so we can accept both ids and labels.
    label_to_id = {label: preset_id for preset_id, label in PRESET_LABELS.items()}

    for key, value in raw.items():
        preset_id: int | None = None
        if isinstance(key, str) and key in label_to_id:
            preset_id = label_to_id[key]
        else:
            try:
                preset_id = int(key)
            except (TypeError, ValueError):
                continue

        if preset_id not in base:
            continue

        temperature = _coerce_preset_temperature(value)
        if temperature is None:
            continue

        base[preset_id] = temperature

    return base


def resolve_preset_temperatures(
    entry_data: Mapping[str, Any] | None,
    entry_options: Mapping[str, Any] | None,
) -> dict[int, float]:
    # Start from defaults and overlay data then options (options take precedence).
    temperatures = dict(PRESET_DEFAULT_TEMPERATURES)

    # Apply flat keys and nested hvac_modes from entry data.
    temperatures = _apply_flat_preset_temperatures(temperatures, entry_data)
    hvac_data = entry_data.get(CONF_HVAC_MODES) if isinstance(entry_data, Mapping) else None
    temperatures = _merge_preset_temperatures(temperatures, hvac_data)

    # Apply flat keys and nested hvac_modes from entry options.
    temperatures = _apply_flat_preset_temperatures(temperatures, entry_options)
    hvac_options = (
        entry_options.get(CONF_HVAC_MODES) if isinstance(entry_options, Mapping) else None
    )
    temperatures = _merge_preset_temperatures(temperatures, hvac_options)

    return temperatures
