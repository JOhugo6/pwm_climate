from __future__ import annotations

import asyncio
import importlib
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypeVar

import pytest

output_adapter = importlib.import_module("custom_components.pwm_climate.output_adapter")

AdapterType = output_adapter.PWMOutputAdapter
ServiceBehavior = Callable[[str, str, dict[str, Any], bool], Awaitable[None]]
AdapterInvoker = Callable[[AdapterType], Coroutine[Any, Any, None]]
TemperatureProvider = Callable[[], float | None]
ResultT = TypeVar("ResultT")


@dataclass(frozen=True, slots=True)
class RecordedCall:
    domain: str
    service: str
    data: dict[str, Any]
    blocking: bool


@dataclass(frozen=True, slots=True)
class CallerScenario:
    name: str
    entity_id: str
    invoke: AdapterInvoker
    expected_call: RecordedCall
    temperature_provider: TemperatureProvider | None = None
    expected_last_state: bool | None = None
    expected_last_value: float | None = None


class FakeServiceRegistry:
    def __init__(self, behavior: ServiceBehavior) -> None:
        self._behavior = behavior
        self.calls: list[RecordedCall] = []

    def has_service(self, domain: str, service: str) -> bool:
        return True

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict[str, Any],
        *,
        blocking: bool,
    ) -> None:
        self.calls.append(
            RecordedCall(
                domain=domain,
                service=service,
                data=dict(data),
                blocking=blocking,
            )
        )
        await self._behavior(domain, service, data, blocking)


class FakeStateMachine:
    def __init__(self, existing_entities: set[str]) -> None:
        self._existing_entities = existing_entities

    def get(self, entity_id: str) -> object | None:
        if entity_id in self._existing_entities:
            return object()
        return None


@dataclass(slots=True)
class FakeHass:
    services: FakeServiceRegistry
    states: FakeStateMachine


@dataclass(slots=True)
class FakeClock:
    now: float = 0.0

    def monotonic(self) -> float:
        return self.now


class LateServiceRegistry(FakeServiceRegistry):
    def __init__(self, behavior: ServiceBehavior, *, clock: FakeClock, available_after: float) -> None:
        super().__init__(behavior)
        self._clock = clock
        self._available_after = available_after

    def has_service(self, domain: str, service: str) -> bool:
        del domain, service
        return self._clock.now >= self._available_after


class LateStateMachine(FakeStateMachine):
    def __init__(self, *, clock: FakeClock, entity_id: str, available_after: float) -> None:
        super().__init__(set())
        self._clock = clock
        self._entity_id = entity_id
        self._available_after = available_after

    def get(self, entity_id: str) -> object | None:
        if entity_id == self._entity_id and self._clock.now >= self._available_after:
            return object()
        return None


async def _complete_call(
    domain: str,
    service: str,
    data: dict[str, Any],
    blocking: bool,
) -> None:
    del domain, service, data, blocking


async def _hang_call(
    domain: str,
    service: str,
    data: dict[str, Any],
    blocking: bool,
) -> None:
    del domain, service, data, blocking
    await asyncio.Event().wait()


async def _raise_recoverable_failure(
    domain: str,
    service: str,
    data: dict[str, Any],
    blocking: bool,
) -> None:
    del domain, service, data, blocking
    raise output_adapter.HomeAssistantError("service call failed")


async def _raise_unexpected_failure(
    domain: str,
    service: str,
    data: dict[str, Any],
    blocking: bool,
) -> None:
    del domain, service, data, blocking
    raise RuntimeError("unexpected service failure")


async def _raise_cancelled(
    domain: str,
    service: str,
    data: dict[str, Any],
    blocking: bool,
) -> None:
    del domain, service, data, blocking
    raise asyncio.CancelledError


def _run(coroutine: Coroutine[Any, Any, ResultT]) -> ResultT:
    return asyncio.run(coroutine)


def _build_adapter(
    entity_id: str,
    behavior: ServiceBehavior,
    *,
    temperature_provider: TemperatureProvider | None = None,
) -> tuple[AdapterType, FakeServiceRegistry]:
    services = FakeServiceRegistry(behavior)
    hass = FakeHass(
        services=services,
        states=FakeStateMachine({entity_id}),
    )
    adapter = AdapterType(
        hass,
        entity_id=entity_id,
        get_climate_temperature=temperature_provider,
    )
    return adapter, services


async def _invoke_binary(adapter: AdapterType) -> None:
    await adapter.async_set_pwm_output(True, 100.0)


async def _invoke_number(adapter: AdapterType) -> None:
    await adapter.async_set_pwm_output(True, 37.5)


async def _invoke_climate(adapter: AdapterType) -> None:
    await adapter.async_set_pwm_output(True, 100.0)


def _climate_temperature() -> float:
    return 21.5


CALLER_SCENARIOS: tuple[CallerScenario, ...] = (
    CallerScenario(
        name="binary",
        entity_id="switch.study",
        invoke=_invoke_binary,
        expected_call=RecordedCall(
            domain="switch",
            service="turn_on",
            data={"entity_id": "switch.study"},
            blocking=True,
        ),
        expected_last_state=True,
    ),
    CallerScenario(
        name="number",
        entity_id="number.valve",
        invoke=_invoke_number,
        expected_call=RecordedCall(
            domain="number",
            service="set_value",
            data={"entity_id": "number.valve", "value": 37.5},
            blocking=True,
        ),
        expected_last_value=37.5,
    ),
    CallerScenario(
        name="climate",
        entity_id="climate.living_room",
        invoke=_invoke_climate,
        expected_call=RecordedCall(
            domain="climate",
            service="set_temperature",
            data={
                "entity_id": "climate.living_room",
                output_adapter.ATTR_TEMPERATURE: 21.5,
            },
            blocking=True,
        ),
        temperature_provider=_climate_temperature,
        expected_last_state=True,
        expected_last_value=21.5,
    ),
)


@pytest.mark.parametrize(
    ("scenario", "expected_last_state", "expected_last_value"),
    [
        pytest.param(
            CALLER_SCENARIOS[0],
            True,
            4.2,
            id="binary",
        ),
        pytest.param(
            CALLER_SCENARIOS[1],
            False,
            37.5,
            id="number",
        ),
    ],
)
def test_redundant_binary_and_number_writes_are_skipped_by_shared_output_path(
    scenario: CallerScenario,
    expected_last_state: bool,
    expected_last_value: float,
) -> None:
    adapter, services = _build_adapter(
        scenario.entity_id,
        _complete_call,
        temperature_provider=scenario.temperature_provider,
    )
    adapter._last_state = expected_last_state
    adapter._last_value = expected_last_value

    _run(scenario.invoke(adapter))

    assert services.calls == []
    assert adapter._last_state is expected_last_state
    assert adapter._last_value == expected_last_value


def test_async_call_service_returns_true_when_service_completes() -> None:
    adapter, services = _build_adapter("switch.study", _complete_call)

    result = _run(
        adapter._async_call_service(
            "switch",
            "turn_on",
            {"entity_id": "switch.study"},
        )
    )

    assert result is True
    assert services.calls == [
        RecordedCall(
            domain="switch",
            service="turn_on",
            data={"entity_id": "switch.study"},
            blocking=True,
        )
    ]


def test_async_call_service_times_out_and_logs_context(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter, _ = _build_adapter("switch.study", _hang_call)
    monkeypatch.setattr(output_adapter, "_DEFAULT_SERVICE_CALL_TIMEOUT", 0.05)
    caplog.set_level(logging.ERROR, logger=output_adapter.DOMAIN)

    started = time.perf_counter()
    result = _run(
        adapter._async_call_service(
            "switch",
            "turn_on",
            {"entity_id": "switch.study"},
        )
    )
    elapsed = time.perf_counter() - started

    assert result is False
    assert elapsed < 0.5
    assert any(
        "Timed out" in record.getMessage()
        and "switch.turn_on" in record.getMessage()
        and "switch.study" in record.getMessage()
        for record in caplog.records
    )


def test_async_call_service_returns_false_for_recoverable_failure_and_logs_context(
    caplog: pytest.LogCaptureFixture,
) -> None:
    adapter, _ = _build_adapter("switch.study", _raise_recoverable_failure)
    caplog.set_level(logging.ERROR, logger=output_adapter.DOMAIN)

    result = _run(
        adapter._async_call_service(
            "switch",
            "turn_on",
            {"entity_id": "switch.study"},
        )
    )

    assert result is False
    assert any(
        "Failed calling switch.turn_on for output entity switch.study: service call failed"
        in record.getMessage()
        for record in caplog.records
    )


def test_async_call_service_propagates_unexpected_exception() -> None:
    adapter, _ = _build_adapter("switch.study", _raise_unexpected_failure)

    with pytest.raises(RuntimeError, match="unexpected service failure"):
        _run(
            adapter._async_call_service(
                "switch",
                "turn_on",
                {"entity_id": "switch.study"},
            )
        )


def test_async_call_service_propagates_cancelled_error() -> None:
    adapter, _ = _build_adapter("switch.study", _raise_cancelled)

    with pytest.raises(asyncio.CancelledError):
        _run(
            adapter._async_call_service(
                "switch",
                "turn_on",
                {"entity_id": "switch.study"},
            )
        )


@pytest.mark.parametrize("scenario", CALLER_SCENARIOS, ids=lambda scenario: scenario.name)
def test_successful_caller_paths_update_cached_state_after_service_completion(
    scenario: CallerScenario,
) -> None:
    adapter, services = _build_adapter(
        scenario.entity_id,
        _complete_call,
        temperature_provider=scenario.temperature_provider,
    )

    _run(scenario.invoke(adapter))

    assert services.calls == [scenario.expected_call]
    assert adapter._last_state is scenario.expected_last_state
    assert adapter._last_value == scenario.expected_last_value


@pytest.mark.parametrize(
    ("scenario", "behavior"),
    [
        pytest.param(
            scenario,
            _raise_recoverable_failure,
            id=f"{scenario.name}-recoverable-failure",
        )
        for scenario in CALLER_SCENARIOS
    ]
    + [
        pytest.param(scenario, _hang_call, id=f"{scenario.name}-timeout")
        for scenario in CALLER_SCENARIOS
    ],
)
def test_failed_or_timed_out_calls_do_not_update_cached_state(
    scenario: CallerScenario,
    behavior: ServiceBehavior,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter, services = _build_adapter(
        scenario.entity_id,
        behavior,
        temperature_provider=scenario.temperature_provider,
    )
    if behavior is _hang_call:
        monkeypatch.setattr(output_adapter, "_DEFAULT_SERVICE_CALL_TIMEOUT", 0.05)

    _run(scenario.invoke(adapter))

    assert services.calls == [scenario.expected_call]
    assert adapter._last_state is None
    assert adapter._last_value is None


def _patch_availability_harness(
    monkeypatch: pytest.MonkeyPatch,
    *,
    clock: FakeClock,
    availability_timeout: float = 0.5,
    availability_interval: float = 0.1,
    availability_cooldown: float = 1.0,
) -> None:
    monkeypatch.setattr(output_adapter, "_DEFAULT_AVAILABILITY_TIMEOUT", availability_timeout)
    monkeypatch.setattr(output_adapter, "_DEFAULT_AVAILABILITY_INTERVAL", availability_interval)
    monkeypatch.setattr(output_adapter, "_DEFAULT_AVAILABILITY_COOLDOWN", availability_cooldown)
    monkeypatch.setattr(output_adapter.time, "monotonic", clock.monotonic)

    real_sleep = asyncio.sleep

    async def fake_sleep(delay: float) -> None:
        clock.now += delay
        await real_sleep(0)

    monkeypatch.setattr(output_adapter.asyncio, "sleep", fake_sleep)


def test_async_call_service_waits_for_late_service_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    _patch_availability_harness(monkeypatch, clock=clock)

    services = LateServiceRegistry(
        _complete_call,
        clock=clock,
        available_after=0.3,
    )
    hass = FakeHass(
        services=services,
        states=FakeStateMachine({"switch.study"}),
    )
    adapter = AdapterType(hass, entity_id="switch.study")

    result = _run(
        adapter._async_call_service(
            "switch",
            "turn_on",
            {"entity_id": "switch.study"},
        )
    )

    assert result is True
    assert clock.now == pytest.approx(0.3)
    assert services.calls == [
        RecordedCall(
            domain="switch",
            service="turn_on",
            data={"entity_id": "switch.study"},
            blocking=True,
        )
    ]


def test_async_call_service_waits_for_late_entity_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    _patch_availability_harness(monkeypatch, clock=clock)

    services = FakeServiceRegistry(_complete_call)
    hass = FakeHass(
        services=services,
        states=LateStateMachine(
            clock=clock,
            entity_id="switch.study",
            available_after=0.2,
        ),
    )
    adapter = AdapterType(hass, entity_id="switch.study")

    result = _run(
        adapter._async_call_service(
            "switch",
            "turn_on",
            {"entity_id": "switch.study"},
        )
    )

    assert result is True
    assert clock.now == pytest.approx(0.2)
    assert services.calls == [
        RecordedCall(
            domain="switch",
            service="turn_on",
            data={"entity_id": "switch.study"},
            blocking=True,
        )
    ]


def test_async_call_service_uses_availability_cooldown_to_skip_repeat_waits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    clock = FakeClock()
    _patch_availability_harness(monkeypatch, clock=clock, availability_timeout=0.5, availability_cooldown=1.0)

    services = LateServiceRegistry(
        _complete_call,
        clock=clock,
        available_after=99.0,
    )
    hass = FakeHass(
        services=services,
        states=FakeStateMachine({"switch.study"}),
    )
    adapter = AdapterType(hass, entity_id="switch.study")

    first = _run(
        adapter._async_call_service(
            "switch",
            "turn_on",
            {"entity_id": "switch.study"},
        )
    )

    assert first is False
    assert clock.now == pytest.approx(0.5)

    async def fail_if_wait_called(predicate: Callable[[], bool]) -> bool:
        del predicate
        raise AssertionError("_async_wait_for should not be called during cooldown/backoff")

    monkeypatch.setattr(adapter, "_async_wait_for", fail_if_wait_called)

    second = _run(
        adapter._async_call_service(
            "switch",
            "turn_on",
            {"entity_id": "switch.study"},
        )
    )

    assert second is False
    assert clock.now == pytest.approx(0.5)
