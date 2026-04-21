"""Software PWM timer helper."""

from __future__ import annotations

import asyncio
import logging
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class _PWMTimingSnapshot:
    """Coherent timing snapshot consumed by the PWM loop."""

    ratio: float
    duty_percent: float
    period_seconds: float
    on_seconds: float
    off_seconds: float
    cycle_start: float


class SoftwarePWMTimer:
    """Async software PWM timer that drives PWM state and duty percent via a callback."""

    def __init__(
        self,
        *,
        set_output: Callable[[bool, float], Awaitable[None]],
        name: str | None = None,
        create_task: Callable[[Awaitable[None]], asyncio.Task] | None = None,
    ) -> None:
        # External callback used to drive the actual output entity.
        self._set_output = set_output
        # Allow injection of task factory for easier testing.
        self._create_task = create_task or asyncio.create_task
        self._name = name or "PWM"

        # Internal state for PWM task and timing.
        self._task: asyncio.Task | None = None
        self._update_event = asyncio.Event()
        self._enabled = False
        self._timing_snapshot: _PWMTimingSnapshot | None = None
        self._phase: str | None = None
        self._output_mode: str | None = None

    def set_name(self, name: str | None) -> None:
        # Update friendly name used in logs.
        if name:
            self._name = name

    async def stop(self, *, reason: str | None = None) -> None:
        # Cancel any running PWM task and reset internal timing state.
        if self._task is None:
            self._enabled = False
            return

        if reason:
            _LOGGER.info("Stopping PWM for %s (%s)", self._name, reason)
        else:
            _LOGGER.info("Stopping PWM for %s", self._name)

        task = self._task
        self._task = None
        self._timing_snapshot = None
        self._phase = None
        self._enabled = False
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        except Exception:
            _LOGGER.debug("PWM task ended with error for %s", self._name, exc_info=True)

    async def apply(
        self,
        *,
        period_seconds: float,
        duty_ratio: float,
        force_restart: bool = False,
        restart_reason: str | None = None,
        off_reason: str | None = None,
        on_reason: str | None = None,
    ) -> None:
        # Normalize inputs and short-circuit for fully off/on duty cycles.
        if self._task is not None and self._task.done():
            self._task = None
            self._enabled = False

        period_seconds = float(max(period_seconds, 1))
        duty_ratio = max(0.0, min(1.0, duty_ratio))
        duty_percent = duty_ratio * 100.0
        on_seconds = period_seconds * duty_ratio
        off_seconds = period_seconds - on_seconds
        _LOGGER.debug(
            "PWM timing for %s (period=%.1fs duty=%.1f%% on=%.1fs off=%.1fs)",
            self._name,
            period_seconds,
            duty_ratio * 100.0,
            on_seconds,
            off_seconds,
        )

        # Duty cycle 0% means fixed OFF (no PWM loop).
        if duty_ratio <= 0.0:
            await self.stop(reason="off_or_zero")
            await self._async_set_stable_output(
                False,
                duty_percent,
                "off",
                off_reason or "duty=0%",
            )
            return

        # Duty cycle 100% means fixed ON (no PWM loop).
        if duty_ratio >= 1.0:
            await self.stop(reason="full_duty")
            await self._async_set_stable_output(
                True,
                duty_percent,
                "on",
                on_reason or "duty=100%",
            )
            return

        same_period = False
        same_ratio = False
        if self._task is not None:
            previous = self._timing_snapshot
            previous_ratio = previous.ratio if previous is not None else None
            same_period = previous is not None and math.isclose(
                previous.period_seconds,
                period_seconds,
                rel_tol=0.0,
                abs_tol=0.01,
            )
            same_ratio = (
                previous is not None
                and math.isclose(previous.ratio, duty_ratio, rel_tol=0.0, abs_tol=1e-6)
            )
            if same_period and same_ratio and not force_restart:
                return

            if not same_ratio:
                previous_percent = (previous_ratio or 0.0) * 100.0
                _LOGGER.debug(
                    "PWM duty change for %s: %.1f%% -> %.1f%%",
                    self._name,
                    previous_percent,
                    duty_ratio * 100.0,
                )

        is_initial_start = self._task is None
        restart_cause: str | None = None
        if force_restart:
            restart_cause = restart_reason or "force_restart"
        elif not is_initial_start and not same_ratio:
            restart_cause = "duty_change"
        elif not is_initial_start and not same_period:
            restart_cause = "period_change"

        should_log_restart = restart_cause is not None and not is_initial_start

        if is_initial_start or restart_cause is not None:
            cycle_start = asyncio.get_running_loop().time()
            if should_log_restart:
                _LOGGER.debug(
                    "Restarting PWM cycle for %s (reason=%s)",
                    self._name,
                    restart_cause,
                )
        else:
            cycle_start = (
                self._timing_snapshot.cycle_start
                if self._timing_snapshot is not None
                else asyncio.get_running_loop().time()
            )

        self._enabled = True
        self._timing_snapshot = _PWMTimingSnapshot(
            ratio=duty_ratio,
            duty_percent=duty_percent,
            period_seconds=period_seconds,
            on_seconds=on_seconds,
            off_seconds=off_seconds,
            cycle_start=cycle_start,
        )
        if restart_cause is not None:
            self._phase = None

        if self._task is None:
            # First-time start of the PWM loop.
            _LOGGER.info(
                "Starting PWM for %s (period=%.1fs duty=%.1f%% on=%.1fs off=%.1fs)",
                self._name,
                period_seconds,
                duty_ratio * 100.0,
                on_seconds,
                off_seconds,
            )
            self._phase = None
            self._output_mode = "pwm"
            self._task = self._create_task(self._async_pwm_loop())
        elif not (same_period and same_ratio):
            _LOGGER.debug(
                "PWM update for %s (period=%.1fs duty=%.1f%% on=%.1fs off=%.1fs)",
                self._name,
                period_seconds,
                duty_ratio * 100.0,
                on_seconds,
                off_seconds,
            )

        self._output_mode = "pwm"
        self._update_event.set()

    async def _async_pwm_loop(self) -> None:
        # Main PWM loop: toggles output on/off based on period and duty.
        loop = asyncio.get_running_loop()
        try:
            while self._enabled:
                self._update_event.clear()
                timing = self._timing_snapshot
                if timing is None or timing.period_seconds <= 0.0:
                    await self._update_event.wait()
                    continue

                period_seconds = timing.period_seconds
                duty_percent = timing.duty_percent
                on_seconds = timing.on_seconds
                cycle_start = timing.cycle_start

                # Determine whether we are currently in the on or off phase.
                now = loop.time()
                position = (max(0.0, now - cycle_start)) % period_seconds
                desired_phase = "on" if position < on_seconds else "off"

                if desired_phase != self._phase:
                    self._phase = desired_phase
                    if desired_phase == "on":
                        _LOGGER.debug(
                            "PWM output ON for %s (power=%.1f%%)",
                            self._name,
                            duty_percent,
                        )
                    else:
                        _LOGGER.debug(
                            "PWM output OFF for %s (power=%.1f%%)",
                            self._name,
                            duty_percent,
                        )
                    await self._async_call_output(desired_phase == "on", duty_percent)

                # Wait until the next phase boundary or an update request.
                if desired_phase == "on":
                    remaining = on_seconds - position
                else:
                    remaining = period_seconds - position

                if remaining <= 0.0:
                    remaining = 0.05

                await self._async_wait_for_update(remaining)
        except asyncio.CancelledError:
            pass

    async def _async_wait_for_update(self, delay: float) -> None:
        # Sleep until delay elapses or configuration changes.
        if delay <= 0.0:
            await asyncio.sleep(0)
            return

        sleep_task = asyncio.create_task(asyncio.sleep(delay))
        update_task = asyncio.create_task(self._update_event.wait())
        tasks = {sleep_task, update_task}
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            for task in tasks:
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    async def _async_set_stable_output(
        self,
        is_on: bool,
        duty_percent: float,
        mode: str,
        reason: str,
    ) -> None:
        # Switch to a fixed output (no PWM loop).
        if mode != self._output_mode:
            if mode == "off":
                _LOGGER.info("PWM output fixed OFF for %s (%s)", self._name, reason)
            elif mode == "on":
                _LOGGER.info("PWM output fixed ON for %s (%s)", self._name, reason)
        self._output_mode = mode
        self._enabled = False
        self._phase = None
        self._timing_snapshot = None
        _LOGGER.debug(
            "PWM output stable %s for %s (power=%.1f%% reason=%s)",
            mode,
            self._name,
            duty_percent,
            reason,
        )
        await self._async_call_output(is_on, duty_percent)

    async def _async_call_output(self, is_on: bool, duty_percent: float) -> None:
        # Delegate output change to injected callback and log errors.
        try:
            await self._set_output(is_on, duty_percent)
        except Exception:
            _LOGGER.exception("PWM output callback failed for %s", self._name)
