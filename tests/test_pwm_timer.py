from __future__ import annotations

import asyncio
import importlib
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

import pytest

pwm_timer = importlib.import_module("custom_components.pwm_climate.pwm_timer")

ResultT = TypeVar("ResultT")
TimingSnapshot = pwm_timer._PWMTimingSnapshot


def _run(coroutine: Coroutine[Any, Any, ResultT]) -> ResultT:
    return asyncio.run(coroutine)


@dataclass(slots=True)
class DummyTask:
    cancelled: bool = False
    finished: bool = False

    def done(self) -> bool:
        return self.finished

    def cancel(self) -> None:
        self.cancelled = True
        self.finished = True

    def __await__(self) -> Any:
        async def _noop() -> None:
            return None

        return _noop().__await__()


def _dummy_create_task(coro: Any) -> DummyTask:
    coro.close()
    return DummyTask()


async def _noop_output(is_on: bool, duty_percent: float) -> None:
    del is_on, duty_percent


def test_apply_duty_change_publishes_coherent_snapshot() -> None:
    async def scenario() -> None:
        timer = pwm_timer.SoftwarePWMTimer(
            set_output=_noop_output,
            create_task=_dummy_create_task,
        )
        await timer.apply(period_seconds=20.0, duty_ratio=0.20)
        first_snapshot = timer._timing_snapshot
        assert first_snapshot is not None

        timer._update_event.clear()
        await asyncio.sleep(0.001)
        await timer.apply(period_seconds=20.0, duty_ratio=0.60)
        second_snapshot = timer._timing_snapshot
        assert second_snapshot is not None

        assert second_snapshot.period_seconds == pytest.approx(20.0)
        assert second_snapshot.ratio == pytest.approx(0.60)
        assert second_snapshot.duty_percent == pytest.approx(60.0)
        assert second_snapshot.on_seconds == pytest.approx(12.0)
        assert second_snapshot.off_seconds == pytest.approx(8.0)
        assert second_snapshot.cycle_start >= first_snapshot.cycle_start
        assert timer._update_event.is_set()

    _run(scenario())


def test_apply_period_change_and_force_restart_keep_snapshot_coherent() -> None:
    async def scenario() -> None:
        timer = pwm_timer.SoftwarePWMTimer(
            set_output=_noop_output,
            create_task=_dummy_create_task,
        )
        await timer.apply(period_seconds=12.0, duty_ratio=0.25)
        first_snapshot = timer._timing_snapshot
        assert first_snapshot is not None

        timer._update_event.clear()
        await asyncio.sleep(0.001)
        await timer.apply(period_seconds=15.0, duty_ratio=0.25)
        second_snapshot = timer._timing_snapshot
        assert second_snapshot is not None
        assert second_snapshot.period_seconds == pytest.approx(15.0)
        assert second_snapshot.on_seconds == pytest.approx(3.75)
        assert second_snapshot.off_seconds == pytest.approx(11.25)
        assert second_snapshot.cycle_start >= first_snapshot.cycle_start
        assert timer._update_event.is_set()

        timer._update_event.clear()
        await asyncio.sleep(0.001)
        await timer.apply(period_seconds=15.0, duty_ratio=0.25, force_restart=True)
        third_snapshot = timer._timing_snapshot
        assert third_snapshot is not None
        assert third_snapshot.period_seconds == pytest.approx(15.0)
        assert third_snapshot.ratio == pytest.approx(0.25)
        assert third_snapshot.on_seconds == pytest.approx(3.75)
        assert third_snapshot.off_seconds == pytest.approx(11.25)
        assert third_snapshot.cycle_start >= second_snapshot.cycle_start
        assert timer._update_event.is_set()

    _run(scenario())


def test_pwm_loop_uses_single_snapshot_per_iteration() -> None:
    async def scenario() -> None:
        outputs: list[tuple[bool, float]] = []

        async def record_output(is_on: bool, duty_percent: float) -> None:
            outputs.append((is_on, duty_percent))

        timer = pwm_timer.SoftwarePWMTimer(set_output=record_output)
        loop = asyncio.get_running_loop()
        base_cycle_start = loop.time()
        first_snapshot = TimingSnapshot(
            ratio=0.10,
            duty_percent=10.0,
            period_seconds=10.0,
            on_seconds=9.0,
            off_seconds=1.0,
            cycle_start=base_cycle_start,
        )
        second_snapshot = TimingSnapshot(
            ratio=0.80,
            duty_percent=80.0,
            period_seconds=2.0,
            on_seconds=1.6,
            off_seconds=0.4,
            cycle_start=base_cycle_start - 1.8,
        )

        class SwitchingSnapshot:
            def __init__(self) -> None:
                self._switched = False

            @property
            def ratio(self) -> float:
                return first_snapshot.ratio

            @property
            def period_seconds(self) -> float:
                if not self._switched:
                    timer._timing_snapshot = second_snapshot
                    self._switched = True
                return first_snapshot.period_seconds

            @property
            def duty_percent(self) -> float:
                return first_snapshot.duty_percent

            @property
            def on_seconds(self) -> float:
                return first_snapshot.on_seconds

            @property
            def cycle_start(self) -> float:
                return first_snapshot.cycle_start

        async def wait_once(delay: float) -> None:
            del delay
            timer._enabled = False

        timer._enabled = True
        timer._phase = None
        timer._timing_snapshot = SwitchingSnapshot()
        timer._async_wait_for_update = wait_once  # type: ignore[method-assign]

        await timer._async_pwm_loop()

        assert timer._timing_snapshot is second_snapshot
        assert outputs == [(True, 10.0)]

    _run(scenario())


def test_apply_zero_and_full_duty_bypass_pwm_loop() -> None:
    async def scenario() -> None:
        def forbidden_create_task(coro: Any) -> Any:
            coro.close()
            raise AssertionError("PWM loop should not be started for 0%/100% duty")

        off_outputs: list[tuple[bool, float]] = []

        async def off_output(is_on: bool, duty_percent: float) -> None:
            off_outputs.append((is_on, duty_percent))

        off_timer = pwm_timer.SoftwarePWMTimer(
            set_output=off_output,
            create_task=forbidden_create_task,
        )
        await off_timer.apply(period_seconds=15.0, duty_ratio=0.0)
        assert off_outputs == [(False, 0.0)]
        assert off_timer._task is None
        assert off_timer._timing_snapshot is None
        assert off_timer._output_mode == "off"

        on_outputs: list[tuple[bool, float]] = []

        async def on_output(is_on: bool, duty_percent: float) -> None:
            on_outputs.append((is_on, duty_percent))

        on_timer = pwm_timer.SoftwarePWMTimer(
            set_output=on_output,
            create_task=forbidden_create_task,
        )
        await on_timer.apply(period_seconds=15.0, duty_ratio=1.0)
        assert on_outputs == [(True, 100.0)]
        assert on_timer._task is None
        assert on_timer._timing_snapshot is None
        assert on_timer._output_mode == "on"

    _run(scenario())
