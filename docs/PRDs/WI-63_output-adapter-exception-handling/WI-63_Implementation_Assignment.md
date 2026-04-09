# WI-63 Implementation Assignment

## Metadata

- PRD folder: `docs/PRDs/WI-63_output-adapter-exception-handling/`
- Source work item: [#63 Overly broad except Exception in output_adapter.py](https://github.com/JOhugo6/pwm_climate/issues/63)
- Target role: `SE`
- Repository domain: `pwm_climate`
- Status: `READY_FOR_IMPLEMENTATION`

## Context And Overview

The current PWM output adapter centralizes Home Assistant service writes in
[`custom_components/pwm_climate/output_adapter.py`](../../../custom_components/pwm_climate/output_adapter.py)
through `PWMOutputAdapter._async_call_service()`. After availability checks and the timeout
guard introduced for WI `#61`, the helper still ends with a blanket `except Exception`
handler. That handler logs the failure and converts every remaining exception into a normal
`False` result.

Because `_async_call_service()` is the shared runtime path for binary, number, and climate
outputs, overly broad exception swallowing can hide defects in the service-call path across
the entire integration. A recoverable output-write failure should remain controlled, but
task cancellation and unexpected programmer/runtime faults must not be silently downgraded
into an ordinary output miss.

The repository already contains focused tests in
[`tests/test_output_adapter.py`](../../../tests/test_output_adapter.py), so this WI should
extend that existing coverage instead of creating parallel test scaffolding.

## Goals

- Narrow exception handling in `_async_call_service()` to explicitly recoverable
  Home Assistant service-call failures.
- Preserve controlled `False` returns for expected runtime write failures.
- Ensure task cancellation and unexpected defects remain visible to the runtime instead of
  being silently treated as an ordinary output failure.
- Keep behavior consistent across binary, number, and climate output paths.

## Non-Goals

- No change to config flow, options flow, translations, or config-entry schema.
- No redesign of availability probing, timeout configuration, or PWM control logic.
- No broad cleanup of unrelated `except Exception` sites outside the output adapter.
- No new diagnostics entity attributes, repair flow, or reconfiguration flow for this WI.
- No bundled fix for WI `#62` or any lower-priority cleanup issue unless directly required
  to complete WI `#63`.

## Functional Requirements

- `FR-63-01`: `PWMOutputAdapter._async_call_service()` must no longer use a blanket
  `except Exception` branch that classifies every non-timeout failure as a recoverable
  output-write failure.
- `FR-63-02`: The implementation must distinguish between explicitly recoverable service
  execution failures and unexpected runtime/programmer faults. Only the approved
  recoverable failure set may be converted into a `False` return value.
- `FR-63-03`: `asyncio.CancelledError` or equivalent task-cancellation signals raised while
  the adapter is waiting on a Home Assistant service call must propagate to the caller and
  must not be logged as an ordinary service-call failure.
- `FR-63-04`: Timeout behavior introduced by WI `#61` must remain intact: a timed-out
  service call must log actionable context and return `False` without indefinite waiting.
- `FR-63-05`: When a recoverable service-call failure occurs, the adapter must emit a clear
  error record that identifies the target entity and the attempted `domain.service`.
- `FR-63-06`: Successful service calls must preserve the current success path, including the
  caller-level cache update behavior used by binary, number, and climate output modes.
- `FR-63-07`: Recoverable failure behavior must apply uniformly to every output mode that
  routes through `_async_call_service()`: `_async_set_binary_output()`,
  `_async_set_number_output()`, and `_async_set_climate_output()`.
- `FR-63-08`: No user-visible configuration behavior may change. Duplicate prevention in
  config flow remains unchanged, and no reconfiguration flow is required for this fix.

## Non-Functional Requirements

- `NFR-63-01`: The change set must stay narrowly scoped to
  [`custom_components/pwm_climate/output_adapter.py`](../../../custom_components/pwm_climate/output_adapter.py)
  and directly related tests unless a minimal adjacent change is required for correctness.
- `NFR-63-02`: The chosen exception taxonomy must be explicit and readable in code; the
  implementation must not rely on a generic catch-all branch for normal control flow.
- `NFR-63-03`: The fix must preserve Home Assistant async execution semantics and must not
  introduce blocking waits, retry loops, or hidden background tasks.
- `NFR-63-04`: Runtime cancellation behavior should align with the repository's existing PWM
  task handling pattern, where cancellation is treated separately from ordinary failures.
- `NFR-63-05`: The implementation must remain compatible with HACS packaging and the
  repository's Docker-based Home Assistant smoke environment.
- `NFR-63-06`: Logging added or retained by this WI must be actionable without creating
  duplicate stack traces for the same failure path.

## Interfaces And Runtime Behavior

- Primary implementation surface:
  [`custom_components/pwm_climate/output_adapter.py`](../../../custom_components/pwm_climate/output_adapter.py)
- Shared runtime call path: `PWMOutputAdapter._async_call_service()`
- Current callers:
  - `_async_set_binary_output()`
  - `_async_set_number_output()`
  - `_async_set_climate_output()`
- Primary test surface:
  [`tests/test_output_adapter.py`](../../../tests/test_output_adapter.py)
- Docker smoke artifact:
  [`docker-compose.yml`](../../../docker-compose.yml)

Required runtime behavior:

- Availability checks for missing services or missing entities must keep their current role
  as startup/runtime guards ahead of the actual service call.
- The explicit timeout wrapper already used around `hass.services.async_call(...,
  blocking=True)` must remain in place.
- Recoverable Home Assistant service-call exceptions must be logged and converted to
  `False`, so the PWM caller can continue operating and retry on later cycles.
- Unexpected exceptions outside the approved recoverable set must not be downgraded to
  `False`; they must surface to the caller/runtime.
- Cancellation raised during shutdown, reload, or task tear-down must propagate without
  being turned into a normal logged output failure.
- No config flow screens, commissioning steps, duplicate-prevention rules, or options-flow
  behavior are changed by this WI.
- No diagnostics payload expansion is required for this issue; actionable runtime logs are
  sufficient.

## Testing Requirements

- `TR-63-01`: Extend
  [`tests/test_output_adapter.py`](../../../tests/test_output_adapter.py) rather than
  creating a new ad hoc test module.
- `TR-63-02`: Add a test that simulates an explicitly recoverable service-call exception and
  verifies that `_async_call_service()` logs context and returns `False`.
- `TR-63-03`: Add a test that simulates an unexpected exception type and verifies that the
  exception is not swallowed by `_async_call_service()`.
- `TR-63-04`: Add a test that simulates `asyncio.CancelledError` during service execution
  and verifies that cancellation propagates rather than returning `False`.
- `TR-63-05`: Verify that caller-level cached state (`_last_state`, `_last_value`) is not
  updated when a recoverable failure occurs in any supported output mode.
- `TR-63-06`: Keep existing timeout coverage from WI `#61` passing to prove the new
  exception taxonomy does not regress timeout handling.
- `TR-63-07`: Execute a repository-local pytest validation and record the exact command in
  the SE handoff. The expected minimum scope is the output-adapter test module.
- `TR-63-08`: Run a Docker smoke validation using the repository's
  [`docker-compose.yml`](../../../docker-compose.yml) setup to confirm the integration still
  boots after the exception-handling change.

## Edge Cases

- A recoverable Home Assistant service exception occurs after service/entity availability
  checks already passed.
- The service call is cancelled during integration unload, Home Assistant shutdown, or task
  replacement.
- An unexpected programming defect raises a non-recoverable exception from the service-call
  path.
- Repeated recoverable failures occur across multiple PWM cycles for the same entity.
- Binary, number, and climate outputs all exercise the same helper but with different
  payload shapes and cache updates.

## Acceptance Criteria

- `AC-63-01`: The blanket `except Exception` handling in
  `PWMOutputAdapter._async_call_service()` is replaced by explicit recoverable-failure
  handling.
- `AC-63-02`: Recoverable service-call failures still produce an actionable log and a
  controlled `False` return to the caller.
- `AC-63-03`: Timeout handling from WI `#61` continues to behave as before and remains
  covered by automated tests.
- `AC-63-04`: Unexpected exception types are no longer silently swallowed as ordinary output
  failures.
- `AC-63-05`: `asyncio.CancelledError` propagates correctly during service-call
  cancellation.
- `AC-63-06`: Automated tests covering recoverable failures, unexpected exceptions, and
  cancellation are added and executed.
- `AC-63-07`: Docker smoke validation completes without introducing a new startup regression
  for the integration.

## Open Questions And Assumptions

- `ASSUMPTION-63-01`: GitHub issues are the intended WI source for this repository because
  the configured `origin` remote resolves to `JOhugo6/pwm_climate` and no separate Azure
  Boards mapping or local priority source is present in the worktree.
- `ASSUMPTION-63-02`: As of `2026-04-09`, WI `#63` is the highest-priority open issue to
  address next because it is one of the open issues marked `Vysoka` and it affects the
  shared output path used by all supported output modes, unlike WI `#62`, which is narrower
  and event-handler-specific.
- `ASSUMPTION-63-03`: The repository still does not contain the mandated
  `docs/templates/PRD_TEMPLATE.md`, so this assignment follows the PA mandatory structure
  directly.
- `ASSUMPTION-63-04`: The PA governance reference path `c:/vyvoj/h6/ha-core` is not present
  in the current environment, so Home Assistant-specific requirements are derived from the
  repository codebase, manifest, and existing tests.
- `OPEN-63-01`: The exact recoverable exception set available for Home Assistant
  `2024.1.0` should be confirmed during implementation and kept as narrow as possible for
  the `async_call()` path.
