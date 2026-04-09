# WI-63 Output Adapter Exception Handling

## Status

- `CLOSED`
- Workflow result: `READY_FOR_FINAL`
- Closed date: `2026-04-09`

## Source Work Item

- GitHub issue: [#63 Overly broad except Exception in output_adapter.py](https://github.com/JOhugo6/pwm_climate/issues/63)
- Selection date: `2026-04-09`
- Priority rationale: selected as the highest-priority currently open WI because, as of
  `2026-04-09`, it is one of two open issues marked `Vysoka` and it affects the shared
  `_async_call_service()` runtime path used by every PWM output mode. Open issue `#62`
  is narrower because it is limited to humidity listener event payload handling.

## Artifacts

- Implementation assignment: [WI-63_Implementation_Assignment.md](WI-63_Implementation_Assignment.md)
- Traceability matrix: [WI-63_TraceMatrix.md](WI-63_TraceMatrix.md)
- Code review report: [WI-63_CR-01_20260409.md](WI-63_CR-01_20260409.md)
- Test report: [WI-63_TR-01_20260409.md](WI-63_TR-01_20260409.md)
- Orchestration state: [WI-63_orchestration_state.json](WI-63_orchestration_state.json)
- Process report: [WI-63_process_report.json](WI-63_process_report.json)

## Scope Summary

- Replace blanket exception swallowing in the shared output-adapter service-call path with
  explicit recoverable-failure handling.
- Preserve the timeout and availability behavior already introduced for WI `#61`.
- Keep config flow, options flow, translations, and unrelated PWM runtime refactors out of
  scope.

## Implemented Changes

- Replaced blanket `except Exception` handling in
  `custom_components/pwm_climate/output_adapter.py` with explicit handling for timeout,
  cancellation, and recoverable `HomeAssistantError` failures.
- Preserved timeout logging and `False` return semantics for recoverable service-call
  failures, while allowing unexpected exceptions to propagate instead of being silently
  downgraded to normal output misses.
- Extended `tests/test_output_adapter.py` coverage for recoverable failures, unexpected
  exception propagation, `asyncio.CancelledError` propagation, timeout non-regression,
  and caller cache-update behavior across binary, number, and climate outputs.

## Validation Summary

- Code review result: `APPROVED`
- QA result: `COMPLETE`
- Repo-local pytest:
  - `.venv\Scripts\python.exe -m pytest tests\test_output_adapter.py -q`
  - `.venv\Scripts\python.exe -m pytest -q`
- Docker validation:
  - `docker compose restart homeassistant`
  - `http://localhost:8124` returned `HTTP 200` before and after restart
  - persisted `pwm_climate` entry remained present and no new startup errors were found in
    Home Assistant logs
