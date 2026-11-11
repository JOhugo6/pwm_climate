"""Offline source-update regressions using fake HA state/listener services."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from custom_components.pwm_climate import climate


def build_runtime(monkeypatch):
    subscriptions = []
    tasks = []
    readings = {
        "sensor.old_temperature": climate.State("20"),
        "sensor.old_humidity": climate.State("48"),
        "sensor.new_temperature": climate.State("22"),
        "sensor.new_humidity": climate.State("55"),
    }
    hass = climate.HomeAssistant()
    hass.states = SimpleNamespace(get=readings.get)

    def create_task(coro):
        task = asyncio.create_task(coro)
        tasks.append(task)
        return task

    hass.async_create_task = create_task

    def subscribe(_hass, entities, callback):
        subscription = SimpleNamespace(entities=entities, callback=callback, removed=False)
        subscriptions.append(subscription)

        def remove():
            subscription.removed = True

        return remove

    monkeypatch.setattr(climate, "async_track_state_change_event", subscribe)
    entry = climate.ConfigEntry(entry_id="stable-id", data={
        climate.CONF_TEMPERATURE_ENTITY: "sensor.old_temperature",
        climate.CONF_HUMIDITY_ENTITY: "sensor.old_humidity",
        climate.CONF_OUTPUT_ENTITY: "switch.valve",
    }, options={climate.CONF_KP: 12.5, climate.CONF_PWM_PERIOD: 730})
    controller = climate.PWMClimateController(hass, entry)
    controller.hass = hass
    controller.entity_id = "climate.stable"
    controller.async_write_ha_state = lambda: None
    controller._attr_hvac_mode = climate.HVACMode.HEAT
    controller._manual_override = True
    controller._attr_preset_mode = climate.PRESET_MANUAL
    controller._attr_target_temperature = 24.5
    controller._async_sync_current_temperature_from_state(readings["sensor.old_temperature"])
    controller._async_sync_current_humidity_from_state(readings["sensor.old_humidity"])
    controller._async_subscribe_temperature_listener()
    controller._async_subscribe_humidity_listener()
    applied_duties = []

    async def apply_pwm(**kwargs):
        # Observe calculated demand without invoking any output adapter/service.
        applied_duties.append(kwargs["duty_ratio"])

    controller._async_apply_pwm = apply_pwm
    return controller, entry, hass, readings, subscriptions, tasks, applied_duties


def event(entity_id, value):
    return climate.Event({"entity_id": entity_id, "new_state": climate.State(value)})


def assert_preserved(controller):
    assert controller.entity_id == "climate.stable"
    assert controller.unique_id == "stable-id"
    assert controller.device_info.identifiers == {(climate.DOMAIN, "stable-id")}
    assert controller._output_entity_id == "switch.valve"
    assert controller._attr_hvac_mode == climate.HVACMode.HEAT
    assert controller._attr_target_temperature == 24.5
    assert controller._manual_override is True
    assert controller._attr_preset_mode == climate.PRESET_MANUAL
    assert controller._p_gain == 12.5
    assert controller._pwm_period_setting_seconds == 730


def test_update_rebinds_sources_ignores_queued_old_callbacks_and_accepts_new_readings(monkeypatch):
    async def scenario():
        controller, entry, hass, readings, subscriptions, tasks, duties = build_runtime(monkeypatch)
        old_temperature, old_humidity = subscriptions
        entry.options = {**entry.options, climate.CONF_TEMPERATURE_ENTITY: "sensor.new_temperature",
                         climate.CONF_HUMIDITY_ENTITY: "sensor.new_humidity"}
        await controller._async_config_entry_updated(hass, entry)
        assert old_temperature.removed and old_humidity.removed
        active = [s for s in subscriptions if not s.removed]
        assert [s.entities for s in active] == [["sensor.new_temperature"], ["sensor.new_humidity"]]
        assert controller._attr_current_temperature == 22
        assert controller._attr_current_humidity == 55
        assert duties[-1] == pytest.approx(0.3125)
        # Simulate events queued before unsubscription, both valid and unavailable.
        for value in ("1", "unavailable"):
            old_temperature.callback(event("sensor.old_temperature", value))
            old_humidity.callback(event("sensor.old_humidity", value))
        assert controller._attr_current_temperature == 22
        assert controller._attr_current_humidity == 55
        assert tasks == []
        active[0].callback(event("sensor.new_temperature", "23"))
        active[1].callback(event("sensor.new_humidity", "57"))
        await asyncio.gather(*tasks)
        assert controller._attr_current_temperature == 23
        assert controller._attr_current_humidity == 57
        assert duties[-1] == pytest.approx(0.1875)
        assert_preserved(controller)
    asyncio.run(scenario())


@pytest.mark.parametrize("value", [None, "unknown", "unavailable", "not-numeric", "nan", "inf", "-inf"])
def test_invalid_new_sources_clear_old_readings_and_force_zero_demand(monkeypatch, value):
    async def scenario():
        controller, entry, hass, readings, subscriptions, tasks, duties = build_runtime(monkeypatch)
        if value is None:
            readings.pop("sensor.new_temperature")
            readings.pop("sensor.new_humidity")
        else:
            readings["sensor.new_temperature"] = climate.State(value)
            readings["sensor.new_humidity"] = climate.State(value)
        entry.options = {**entry.options, climate.CONF_TEMPERATURE_ENTITY: "sensor.new_temperature",
                         climate.CONF_HUMIDITY_ENTITY: "sensor.new_humidity"}
        await controller._async_config_entry_updated(hass, entry)
        assert controller._current_temperature is None
        assert controller._attr_current_temperature is None
        assert controller._attr_current_humidity is None
        assert controller._control_output_percent == 0
        assert controller._duty_cycle_percent == 0
        assert duties == [0]
        assert [s.entities for s in subscriptions if not s.removed] == [
            ["sensor.new_temperature"], ["sensor.new_humidity"]]
        assert_preserved(controller)
    asyncio.run(scenario())


def test_removing_humidity_unsubscribes_ignores_old_events_and_survives_reconstruction(monkeypatch):
    async def scenario():
        controller, entry, hass, readings, subscriptions, tasks, duties = build_runtime(monkeypatch)
        temperature, humidity = subscriptions
        entry.options = {**entry.options, climate.CONF_HUMIDITY_ENTITY: None}
        await controller._async_config_entry_updated(hass, entry)
        assert humidity.removed
        assert not temperature.removed
        assert controller._humidity_sensor_entity_id is None
        assert controller._attr_current_humidity is None
        assert controller._unsub_humidity_listener is None
        humidity.callback(event("sensor.old_humidity", "60"))
        assert controller._attr_current_humidity is None
        assert controller._attr_current_temperature == 20
        assert_preserved(controller)
        restarted = climate.PWMClimateController(hass, entry)
        restarted.hass = hass
        restarted.entity_id = "climate.stable"
        restarted._async_subscribe_humidity_listener()
        assert restarted._humidity_sensor_entity_id is None
        assert restarted._unsub_humidity_listener is None
        # Re-adding attaches a listener and reads the selected source.
        entry.options = {**entry.options, climate.CONF_HUMIDITY_ENTITY: "sensor.new_humidity"}
        await controller._async_config_entry_updated(hass, entry)
        assert controller._humidity_sensor_entity_id == "sensor.new_humidity"
        assert controller._attr_current_humidity == 55
        assert subscriptions[-1].entities == ["sensor.new_humidity"]
        assert not subscriptions[-1].removed
        assert_preserved(controller)
    asyncio.run(scenario())


@pytest.mark.parametrize("field,source,other_index", [
    (climate.CONF_TEMPERATURE_ENTITY, "sensor.new_temperature", 1),
    (climate.CONF_HUMIDITY_ENTITY, "sensor.new_humidity", 0),
])
def test_changing_one_source_leaves_other_listener_and_reading_in_place(monkeypatch, field, source, other_index):
    async def scenario():
        controller, entry, hass, readings, subscriptions, tasks, duties = build_runtime(monkeypatch)
        untouched = subscriptions[other_index]
        entry.options = {**entry.options, field: source}
        await controller._async_config_entry_updated(hass, entry)
        assert not untouched.removed
        assert controller._attr_current_temperature == (22 if field == climate.CONF_TEMPERATURE_ENTITY else 20)
        assert controller._attr_current_humidity == (55 if field == climate.CONF_HUMIDITY_ENTITY else 48)
        assert_preserved(controller)
    asyncio.run(scenario())
