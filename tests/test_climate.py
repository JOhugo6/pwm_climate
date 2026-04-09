from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass

climate = importlib.import_module("custom_components.pwm_climate.climate")


@dataclass(slots=True)
class WriteRecorder:
    calls: int = 0

    def __call__(self) -> None:
        self.calls += 1


def _build_controller(*, humidity: float | None = 42.0) -> tuple[object, WriteRecorder]:
    controller = climate.PWMClimateController.__new__(climate.PWMClimateController)
    recorder = WriteRecorder()

    controller._is_removing = False
    controller._attr_current_humidity = humidity
    controller._humidity_sensor_entity_id = "sensor.study_humidity"
    controller.entity_id = "climate.study"
    controller.async_write_ha_state = recorder

    return controller, recorder


def test_async_humidity_changed_ignores_event_without_new_state(
    caplog,
) -> None:
    controller, recorder = _build_controller(humidity=48.0)
    caplog.set_level(logging.DEBUG, logger=climate.DOMAIN)

    controller._async_humidity_changed(
        climate.Event({"old_state": climate.State("47.0")})
    )

    assert controller._attr_current_humidity == 48.0
    assert recorder.calls == 0
    assert any("no usable new_state" in record.getMessage() for record in caplog.records)


def test_async_humidity_changed_ignores_event_with_none_new_state(
    caplog,
) -> None:
    controller, recorder = _build_controller(humidity=48.0)
    caplog.set_level(logging.DEBUG, logger=climate.DOMAIN)

    controller._async_humidity_changed(climate.Event({"new_state": None}))

    assert controller._attr_current_humidity == 48.0
    assert recorder.calls == 0
    assert any("no usable new_state" in record.getMessage() for record in caplog.records)


def test_async_humidity_changed_deduplicates_same_state() -> None:
    controller, recorder = _build_controller(humidity=48.0)

    controller._async_humidity_changed(
        climate.Event(
            {
                "old_state": climate.State("51.0"),
                "new_state": climate.State("51.0"),
            }
        )
    )

    assert controller._attr_current_humidity == 48.0
    assert recorder.calls == 0


def test_async_humidity_changed_updates_humidity_for_valid_state() -> None:
    controller, recorder = _build_controller(humidity=48.0)

    controller._async_humidity_changed(
        climate.Event(
            {
                "old_state": climate.State("48.0"),
                "new_state": climate.State("55.5"),
            }
        )
    )

    assert controller._attr_current_humidity == 55.5
    assert recorder.calls == 1


def test_async_humidity_changed_ignores_invalid_state() -> None:
    controller, recorder = _build_controller(humidity=48.0)

    controller._async_humidity_changed(
        climate.Event(
            {
                "old_state": climate.State("48.0"),
                "new_state": climate.State("unavailable"),
            }
        )
    )

    assert controller._attr_current_humidity == 48.0
    assert recorder.calls == 0
