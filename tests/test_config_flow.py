from __future__ import annotations

import asyncio
import importlib
from dataclasses import dataclass, field
from typing import Any

import pytest

config_flow = importlib.import_module("custom_components.pwm_climate.config_flow")


@dataclass(slots=True)
class RegistryEntry:
    entity_id: str
    domain: str = "sensor"
    device_class: str | None = None


@dataclass(slots=True)
class State:
    entity_id: str
    state: str = "unknown"
    attributes: dict[str, Any] = field(default_factory=dict)


class FakeEntityRegistry:
    def __init__(self, entries: dict[str, RegistryEntry]) -> None:
        self.entities = entries


class FakeStateMachine:
    def __init__(self, states: list[State]) -> None:
        self._states = {state.entity_id: state for state in states}

    def async_all(self, domain: str) -> list[State]:
        prefix = f"{domain}."
        return [state for entity_id, state in self._states.items() if entity_id.startswith(prefix)]

    def get(self, entity_id: str) -> State | None:
        return self._states.get(entity_id)


class FakeHass:
    def __init__(self, *, entries: dict[str, RegistryEntry], states: list[State]) -> None:
        self.entity_registry = FakeEntityRegistry(entries)
        self.states = FakeStateMachine(states)


def _build_flow(*, entries: dict[str, RegistryEntry], states: list[State]) -> config_flow.PWMClimateConfigFlow:
    flow = config_flow.PWMClimateConfigFlow.__new__(config_flow.PWMClimateConfigFlow)
    flow.hass = FakeHass(entries=entries, states=states)
    return flow


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def test_get_temperature_entities_discovers_registry_and_state_matches() -> None:
    flow = _build_flow(
        entries={
            "sensor.registry_temperature": RegistryEntry(
                entity_id="sensor.registry_temperature",
                device_class="temperature",
            ),
            "sensor.registry_unit": RegistryEntry(
                entity_id="sensor.registry_unit",
            ),
            "sensor.registry_other": RegistryEntry(
                entity_id="sensor.registry_other",
            ),
            "light.ignored": RegistryEntry(
                entity_id="light.ignored",
                domain="light",
                device_class="temperature",
            ),
        },
        states=[
            State(
                entity_id="sensor.registry_unit",
                attributes={"unit_of_measurement": "°C"},
            ),
            State(
                entity_id="sensor.runtime_temperature",
                attributes={"device_class": "temperature"},
            ),
            State(
                entity_id="sensor.runtime_other",
                attributes={"unit_of_measurement": "kWh"},
            ),
        ],
    )

    assert flow._get_temperature_entities() == [
        "sensor.registry_temperature",
        "sensor.registry_unit",
        "sensor.runtime_temperature",
    ]


def test_async_step_user_accepts_valid_temperature_entity() -> None:
    async def scenario() -> None:
        flow = _build_flow(
            entries={
                "sensor.study_temperature": RegistryEntry(
                    entity_id="sensor.study_temperature",
                    device_class="temperature",
                ),
            },
            states=[],
        )

        result = await flow.async_step_user(
            {
                config_flow.CONF_NAME: "Study PWM",
                config_flow.CONF_TEMPERATURE_ENTITY: "sensor.study_temperature",
            }
        )

        assert result["type"] == "create_entry"
        assert result["title"] == "Study PWM"
        assert result["data"] == {
            config_flow.CONF_NAME: "Study PWM",
            config_flow.CONF_TEMPERATURE_ENTITY: "sensor.study_temperature",
        }

    _run(scenario())


def test_async_step_user_rejects_invalid_temperature_entity() -> None:
    async def scenario() -> None:
        flow = _build_flow(
            entries={
                "sensor.study_temperature": RegistryEntry(
                    entity_id="sensor.study_temperature",
                    device_class="temperature",
                ),
            },
            states=[],
        )

        result = await flow.async_step_user(
            {
                config_flow.CONF_NAME: "Study PWM",
                config_flow.CONF_TEMPERATURE_ENTITY: "sensor.invalid_temperature",
            }
        )

        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"][config_flow.CONF_TEMPERATURE_ENTITY] == "invalid_temperature_entity"

    _run(scenario())
