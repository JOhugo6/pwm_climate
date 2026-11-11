from __future__ import annotations

import asyncio
from typing import Any

import pytest
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from custom_components.pwm_climate import options_flow
from custom_components.pwm_climate.const import (
    CONF_HUMIDITY_ENTITY, CONF_TEMPERATURE_ENTITY, CONF_KP, CONF_OUTPUT_ENTITY,
    CONF_PWM_PERIOD, PRESET_TEMPERATURE_KEYS,
)
from test_config_flow import FakeHass, RegistryEntry, State


def build_flow(*, data=None, options=None):
    entry = ConfigEntry(data=data or {
        CONF_TEMPERATURE_ENTITY: "sensor.old_temperature",
        CONF_HUMIDITY_ENTITY: "sensor.old_humidity",
    }, options=options or {})
    flow = options_flow.PWMClimateOptionsFlowHandler(entry)
    flow.hass = FakeHass(entries={
        "sensor.old_temperature": RegistryEntry("sensor.old_temperature", device_class="temperature"),
        "sensor.old_humidity": RegistryEntry("sensor.old_humidity", device_class="humidity"),
    }, states=[
        State("sensor.new_temperature", "21", {"unit_of_measurement": "°C"}),
        State("sensor.new_humidity", "45", {"device_class": "humidity"}),
        State("sensor.unit_humidity", "44", {"unit_of_measurement": "%"}),
        State("sensor.battery", "80", {"device_class": "battery", "unit_of_measurement": "%"}),
        State("sensor.energy", "3", {"unit_of_measurement": "kWh"}),
    ])
    return flow


def form_fields(result):
    return {
        getattr(marker, "schema", getattr(marker, "key", None)): (marker, validator)
        for marker, validator in result["data_schema"].schema.items()
    }


def run(coro):
    return asyncio.run(coro)


@pytest.mark.parametrize("options,temperature,humidity", [
    ({}, "sensor.old_temperature", "sensor.old_humidity"),
    ({CONF_TEMPERATURE_ENTITY: "sensor.new_temperature", CONF_HUMIDITY_ENTITY: "sensor.new_humidity"},
     "sensor.new_temperature", "sensor.new_humidity"),
    ({CONF_HUMIDITY_ENTITY: None}, "sensor.old_temperature", None),
    ({CONF_HUMIDITY_ENTITY: ""}, "sensor.old_temperature", ""),
])
def test_options_form_prefills_effective_sources(options, temperature, humidity):
    flow = build_flow(options=options)
    result = run(flow.async_step_init())
    fields = form_fields(result)
    assert fields[CONF_TEMPERATURE_ENTITY][0].description["suggested_value"] == temperature
    assert fields[CONF_HUMIDITY_ENTITY][0].description["suggested_value"] == humidity
    assert "sensor.new_temperature" in fields[CONF_TEMPERATURE_ENTITY][1].config.include_entities
    humidity_choices = fields[CONF_HUMIDITY_ENTITY][1].config.include_entities
    assert "sensor.unit_humidity" in humidity_choices
    assert "sensor.battery" not in humidity_choices
    assert "sensor.energy" not in humidity_choices


def test_real_schema_omission_clears_humidity_and_reopened_form_does_not_revive_data():
    # This checks actual Voluptuous defaults/omission, not just a manually
    # constructed payload sent directly to async_step_init.
    if not hasattr(vol, "UNDEFINED"):
        pytest.skip("Install real voluptuous to verify form schema semantics")
    flow = build_flow()
    form = run(flow.async_step_init())
    payload = form["data_schema"]({CONF_TEMPERATURE_ENTITY: "sensor.new_temperature"})
    assert CONF_HUMIDITY_ENTITY not in payload
    result = run(flow.async_step_init(payload))
    assert result["type"] == "create_entry"
    assert result["data"][CONF_HUMIDITY_ENTITY] is None
    flow.entry.options = result["data"]
    reopened = run(flow.async_step_init())
    fields = form_fields(reopened)
    assert fields[CONF_HUMIDITY_ENTITY][0].description["suggested_value"] is None
    # Selecting humidity again survives the same real schema path.
    payload = reopened["data_schema"]({
        CONF_TEMPERATURE_ENTITY: "sensor.new_temperature",
        CONF_HUMIDITY_ENTITY: "sensor.new_humidity",
    })
    restored = run(flow.async_step_init(payload))
    assert restored["data"][CONF_HUMIDITY_ENTITY] == "sensor.new_humidity"
    with pytest.raises(vol.Invalid):
        reopened["data_schema"]({})


@pytest.mark.parametrize("temperature,humidity", [
    ("sensor.new_temperature", "sensor.old_humidity"),
    ("sensor.old_temperature", "sensor.new_humidity"),
    ("sensor.new_temperature", "sensor.new_humidity"),
    ("sensor.old_temperature", None),
])
def test_changes_independent_and_existing_options_preserved(temperature, humidity):
    existing = {
        CONF_OUTPUT_ENTITY: "switch.valve", CONF_KP: 17.5, CONF_PWM_PERIOD: 750,
        PRESET_TEMPERATURE_KEYS[1]: 23.5, "future_option": {"nested": [1, 2]},
    }
    flow = build_flow(options=existing)
    original_data = dict(flow.entry.data)
    payload = {CONF_TEMPERATURE_ENTITY: temperature}
    if humidity is not None:
        payload[CONF_HUMIDITY_ENTITY] = humidity
    result = run(flow.async_step_init(payload))
    assert result["type"] == "create_entry"
    assert result["data"] == {**existing, **payload, CONF_HUMIDITY_ENTITY: humidity}
    assert flow.entry.options == existing
    assert flow.entry.data == original_data
    assert flow.entry.entry_id == "entry-id"


@pytest.mark.parametrize("key,value,error", [
    (CONF_TEMPERATURE_ENTITY, "sensor.energy", "invalid_temperature_entity"),
    (CONF_TEMPERATURE_ENTITY, "light.temperature", "invalid_temperature_entity"),
    (CONF_TEMPERATURE_ENTITY, None, "invalid_temperature_entity"),
    (CONF_HUMIDITY_ENTITY, "sensor.energy", "invalid_humidity_entity"),
    (CONF_HUMIDITY_ENTITY, "sensor.battery", "invalid_humidity_entity"),
    (CONF_HUMIDITY_ENTITY, "light.humidity", "invalid_humidity_entity"),
    (CONF_HUMIDITY_ENTITY, False, "invalid_humidity_entity"),
    (CONF_HUMIDITY_ENTITY, [], "invalid_humidity_entity"),
])
def test_invalid_sources_return_localized_field_errors_without_saving(key, value, error):
    flow = build_flow(options={CONF_KP: 20})
    payload = {CONF_TEMPERATURE_ENTITY: "sensor.new_temperature", CONF_HUMIDITY_ENTITY: "sensor.new_humidity"}
    payload[key] = value
    result = run(flow.async_step_init(payload))
    assert result["type"] == "form"
    assert result["errors"][key] == error
    assert flow.entry.options == {CONF_KP: 20}
    assert form_fields(result)[key][0].description["suggested_value"] == value


def test_existing_legacy_humidity_source_allows_tuning_only_save():
    flow = build_flow(options={CONF_HUMIDITY_ENTITY: "sensor.energy"})
    form = run(flow.async_step_init())
    assert "sensor.energy" in form_fields(form)[CONF_HUMIDITY_ENTITY][1].config.include_entities
    result = run(flow.async_step_init({CONF_TEMPERATURE_ENTITY: "sensor.old_temperature",
                                      CONF_HUMIDITY_ENTITY: "sensor.energy", CONF_KP: 16}))
    assert result["type"] == "create_entry"
    assert result["data"][CONF_KP] == 16
    assert result["data"][CONF_HUMIDITY_ENTITY] == "sensor.energy"


@pytest.mark.parametrize("invalid", ["light.humidity", False, 7])
def test_non_sensor_legacy_humidity_is_not_grandfathered(invalid):
    flow = build_flow(options={CONF_HUMIDITY_ENTITY: invalid})
    result = run(flow.async_step_init({CONF_TEMPERATURE_ENTITY: "sensor.old_temperature",
                                      CONF_HUMIDITY_ENTITY: invalid}))
    assert result["type"] == "form"
    assert result["errors"][CONF_HUMIDITY_ENTITY] == "invalid_humidity_entity"


@pytest.mark.parametrize("alias", ["1", 1, "Komfort"])
def test_real_schema_preserves_legacy_preset_map_but_applies_edited_slider(alias):
    if not hasattr(vol, "UNDEFINED"):
        pytest.skip("Install real voluptuous to verify form schema semantics")
    from custom_components.pwm_climate.const import CONF_HVAC_MODES
    from custom_components.pwm_climate.preset_helpers import resolve_preset_temperatures

    original = {CONF_HVAC_MODES: {alias: 24.0, "3": 19.5, "unknown": 99}}
    flow = build_flow(options=original)
    form = run(flow.async_step_init())
    payload = form["data_schema"]({
        CONF_TEMPERATURE_ENTITY: "sensor.old_temperature",
        CONF_HUMIDITY_ENTITY: "sensor.old_humidity",
        PRESET_TEMPERATURE_KEYS[1]: 23.0,
    })
    saved = run(flow.async_step_init(payload))["data"]
    effective = resolve_preset_temperatures(flow.entry.data, saved)
    assert effective[1] == 23.0
    assert effective[3] == 19.5
    assert saved[CONF_HVAC_MODES][alias] == 23.0
    assert saved[CONF_HVAC_MODES]["unknown"] == 99
    assert original[CONF_HVAC_MODES][alias] == 24.0
