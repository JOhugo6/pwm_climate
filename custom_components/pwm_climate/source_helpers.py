"""Shared discovery and validation for selectable measurement sources."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers import entity_registry as er


def measurement_entities(hass: Any, device_class: str, unit: str) -> list[str]:
    """Include registry/state sensors, including legacy unit-only measurements."""
    registry = er.async_get(hass)
    entries = {
        entry.entity_id: entry
        for entry in registry.entities.values()
        if entry.domain == "sensor"
    }
    entities = set(entries)
    entities.update(state.entity_id for state in hass.states.async_all("sensor"))
    matches = []
    for entity_id in sorted(entities):
        entry = entries.get(entity_id)
        state = hass.states.get(entity_id)
        candidate_class = getattr(entry, "device_class", None)
        candidate_unit = None
        if state is not None:
            candidate_class = state.attributes.get("device_class", candidate_class)
            candidate_unit = state.attributes.get("unit_of_measurement")
        if candidate_class == device_class or (
            candidate_unit == unit and (device_class == "temperature" or not candidate_class)
        ):
            matches.append(entity_id)
    return matches
