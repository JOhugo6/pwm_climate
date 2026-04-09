from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging
from collections.abc import Coroutine
from dataclasses import dataclass, field
from typing import Any

import pytest

climate = importlib.import_module("custom_components.pwm_climate.climate")


@dataclass(slots=True)
class WriteRecorder:
    calls: int = 0

    def __call__(self) -> None:
        self.calls += 1


@dataclass(slots=True)
class TaskTrackingHass:
    created_tasks: list[asyncio.Task[Any]] = field(default_factory=list)

    def async_create_task(self, coro: Any) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self.created_tasks.append(task)
        return task


def _build_controller(*, humidity: float | None = 42.0) -> tuple[object, WriteRecorder]:
    controller = climate.PWMClimateController.__new__(climate.PWMClimateController)
    recorder = WriteRecorder()

    controller._is_removing = False
    controller._attr_current_humidity = humidity
    controller._humidity_sensor_entity_id = "sensor.study_humidity"
    controller.entity_id = "climate.study"
    controller.async_write_ha_state = recorder

    return controller, recorder


def _build_regulation_controller() -> tuple[object, TaskTrackingHass, WriteRecorder]:
    controller = climate.PWMClimateController.__new__(climate.PWMClimateController)
    hass = TaskTrackingHass()
    recorder = WriteRecorder()

    controller._hass = hass
    controller.hass = hass
    controller._is_removing = False
    controller._attr_current_temperature = 20.0
    controller._attr_target_temperature = 21.0
    controller._attr_hvac_mode = climate.HVACMode.HEAT
    controller._attr_preset_mode = "comfort"
    controller._attr_current_humidity = 42.0
    controller._humidity_sensor_entity_id = "sensor.study_humidity"
    controller._temperature_entity_id = "sensor.study_temperature"
    controller.entity_id = "climate.study"
    controller.async_write_ha_state = recorder
    controller._async_stop_pwm_task = _noop_async_stop_pwm_task
    controller._async_unsubscribe_temperature_listener = lambda: None
    controller._async_unsubscribe_regulation_listener = lambda: None
    controller._async_unsubscribe_humidity_listener = lambda: None
    controller._unsub_entry_update_listener = None
    controller._pwm_lock = asyncio.Lock()
    controller._regulation_update_task = None
    controller._pending_regulation_update_reason = None

    return controller, hass, recorder


def _tracked_task(controller: object) -> asyncio.Task[Any] | None:
    return getattr(controller, "_regulation_update_task", None)


def _pending_reason(controller: object) -> str | None:
    return getattr(controller, "_pending_regulation_update_reason", None)


async def _noop_async_stop_pwm_task(*, reason: str) -> None:
    del reason


def _run(coro: Coroutine[Any, Any, Any]) -> Any:
    return asyncio.run(coro)


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


def test_handle_regulation_input_change_coalesces_pending_updates_and_uses_latest_reason() -> None:
    async def scenario() -> None:
        controller, hass, _recorder = _build_regulation_controller()
        release_first_update = asyncio.Event()
        first_update_started = asyncio.Event()
        seen_reasons: list[str] = []

        async def fake_update_output(*, reason: str) -> None:
            seen_reasons.append(reason)
            if len(seen_reasons) == 1:
                first_update_started.set()
                await release_first_update.wait()

        controller._async_update_output = fake_update_output

        controller._handle_regulation_input_change(reason="temperature_change")
        await asyncio.wait_for(first_update_started.wait(), timeout=1.0)
        await asyncio.sleep(0)

        assert len(hass.created_tasks) == 1
        assert _tracked_task(controller) is not None
        assert _pending_reason(controller) is None
        assert seen_reasons == ["temperature_change"]

        controller._handle_regulation_input_change(reason="regulation_change")
        controller._handle_regulation_input_change(reason="manual_override")

        await asyncio.sleep(0)
        assert len(hass.created_tasks) == 1
        assert seen_reasons == ["temperature_change"]
        assert _pending_reason(controller) == "manual_override"

        release_first_update.set()
        await asyncio.wait_for(hass.created_tasks[0], timeout=1.0)
        await asyncio.sleep(0)

        assert seen_reasons == ["temperature_change", "manual_override"]
        assert len(hass.created_tasks) == 1
        assert _tracked_task(controller) is None
        assert _pending_reason(controller) is None

    _run(scenario())


def test_handle_regulation_input_change_clears_tracked_task_after_normal_completion() -> None:
    async def scenario() -> None:
        controller, hass, _recorder = _build_regulation_controller()
        update_started = asyncio.Event()
        allow_finish = asyncio.Event()

        async def fake_update_output(*, reason: str) -> None:
            del reason
            update_started.set()
            await allow_finish.wait()

        controller._async_update_output = fake_update_output

        controller._handle_regulation_input_change(reason="temperature_change")
        await asyncio.wait_for(update_started.wait(), timeout=1.0)
        await asyncio.sleep(0)

        assert len(hass.created_tasks) == 1
        assert _tracked_task(controller) is not None

        allow_finish.set()
        await asyncio.wait_for(hass.created_tasks[0], timeout=1.0)
        await asyncio.sleep(0)

        assert hass.created_tasks[0].done()
        assert _tracked_task(controller) is None
        assert _pending_reason(controller) is None

    _run(scenario())


def test_async_will_remove_from_hass_cancels_pending_regulation_update_task() -> None:
    async def scenario() -> None:
        controller, hass, _recorder = _build_regulation_controller()
        update_started = asyncio.Event()

        async def fake_update_output(*, reason: str) -> None:
            del reason
            update_started.set()
            await asyncio.Event().wait()

        controller._async_update_output = fake_update_output

        controller._handle_regulation_input_change(reason="temperature_change")
        await asyncio.wait_for(update_started.wait(), timeout=1.0)
        await asyncio.sleep(0)

        assert len(hass.created_tasks) == 1
        assert _tracked_task(controller) is not None

        await controller.async_will_remove_from_hass()
        await asyncio.sleep(0)

        tracked_task = hass.created_tasks[0]
        assert tracked_task.cancelled() or tracked_task.done()
        assert controller._is_removing is True
        assert _tracked_task(controller) is None
        assert _pending_reason(controller) is None

        if not tracked_task.done():
            tracked_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tracked_task

    _run(scenario())


def test_handle_regulation_input_change_logs_task_failure(caplog) -> None:
    caplog.set_level(logging.ERROR, logger=climate.DOMAIN)

    async def scenario() -> None:
        controller, hass, _recorder = _build_regulation_controller()

        async def fake_update_output(*, reason: str) -> None:
            raise RuntimeError(f"boom:{reason}")

        controller._async_update_output = fake_update_output

        controller._handle_regulation_input_change(reason="temperature_change")

        with pytest.raises(RuntimeError, match="boom:temperature_change"):
            await asyncio.wait_for(hass.created_tasks[0], timeout=1.0)
        await asyncio.sleep(0)

        assert _tracked_task(controller) is None
        assert _pending_reason(controller) is None

    _run(scenario())

    assert any(
        record.getMessage() == "Regulation update task failed for climate.study"
        and record.exc_info is not None
        and isinstance(record.exc_info[1], RuntimeError)
        for record in caplog.records
    )
